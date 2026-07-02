"""Tests for DimseConnector retry behavior and connection management."""

import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from pydicom import Dataset
from pynetdicom.status import Status

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.factories import DicomMoveServerFactory, DicomServerFactory
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dimse_connector import DimseConnector
from adit.core.utils.testing_helpers import DicomTestHelper, create_association_mock


def _status(code: int, **kwargs) -> Dataset:
    ds = Dataset()
    ds.Status = code
    for key, value in kwargs.items():
        setattr(ds, key, value)
    return ds


@pytest.mark.django_db
class TestDimseConnectorRetry:
    """Test retry behavior and connection cleanup in DimseConnector."""

    @patch("adit.core.utils.retry_config.settings.ENABLE_STAMINA_RETRY", True)
    def test_abort_connection_resets_assoc_allowing_retry(self, mocker):
        """Test that abort_connection resets self.assoc allowing retries to work.

        This test verifies the fix where:
        1. First attempt fails and calls abort_connection()
        2. abort_connection() aborts the connection AND sets self.assoc = None
        3. Retry attempt successfully opens a new connection
        4. Operation succeeds on retry
        """
        # Arrange
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=True)

        # Track association creation attempts
        association_mocks = []

        # Track which attempt we're on
        call_count = 0

        def side_effect_c_get(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails - this will trigger abort_connection
                raise RetriableDicomError("Simulated network failure")
            else:
                # Subsequent calls succeed
                return DicomTestHelper.create_successful_c_get_response()

        def create_new_association(*_args, **_kwargs):
            association_mock = create_association_mock()

            # Make is_alive() return False after abort() is called
            def abort_side_effect():
                association_mock.is_alive.return_value = False

            association_mock.abort.side_effect = abort_side_effect
            association_mock.is_alive.return_value = True  # Initially alive

            # Set the send_c_get side effect
            association_mock.send_c_get.side_effect = side_effect_c_get

            association_mocks.append(association_mock)
            return association_mock

        associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
        associate_mock.side_effect = create_new_association

        # Create a query that will trigger C-GET
        query = QueryDataset.create(
            PatientID="12345",
            StudyInstanceUID="1.2.3.4.5",
        )

        # Mock store handler
        store_handler = MagicMock()
        store_errors = []

        # Act
        # With the fix, retry should work properly
        connector.send_c_get(query, store_handler, store_errors)

        # Assert
        # Should have 2 association attempts (initial + retry)
        assert len(association_mocks) == 2
        # First association aborted
        assert association_mocks[0].abort.called
        # Second association succeeded and was released
        assert association_mocks[1].release.called
        # Final state should have no connection
        assert connector.assoc is None
        # Operation should have succeeded on retry
        assert call_count == 2

    @patch("adit.core.utils.retry_config.settings.ENABLE_STAMINA_RETRY", True)
    def test_close_connection_properly_resets_assoc(self, mocker):
        """Test that close_connection properly resets self.assoc to None.

        This test verifies that the normal close path works correctly.
        It should pass even before the bug fix.
        """
        # Arrange
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=True)

        # Mock the AE.associate to return a mock association
        associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
        association_mock = create_association_mock()
        associate_mock.return_value = association_mock

        # Create a query
        query = QueryDataset.create(
            PatientID="12345",
            StudyInstanceUID="1.2.3.4.5",
        )

        # Mock send_c_get to succeed
        association_mock.send_c_get.return_value = (
            DicomTestHelper.create_successful_c_get_response()
        )

        # Mock store handler
        store_handler = MagicMock()
        store_errors = []

        # Act
        connector.send_c_get(query, store_handler, store_errors)

        # Assert
        # After successful operation with auto_connect, connection should be closed
        # and self.assoc should be None
        assert connector.assoc is None
        assert association_mock.release.called


@pytest.mark.django_db
class TestDimseConnectorConnectionLifecycle:
    """Test connection lifecycle management."""

    def test_open_connection_fails_if_previous_not_closed(self):
        """Test that open_connection raises AssertionError if self.assoc is not None."""
        # Arrange
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=False)

        # Manually set assoc to simulate a connection that wasn't closed
        connector.assoc = MagicMock()

        # Act & Assert
        with pytest.raises(AssertionError, match="A former connection was not closed properly"):
            connector.open_connection("C-FIND")

    def test_abort_connection_with_no_connection(self):
        """Test that abort_connection handles case when there's no active connection."""
        # Arrange
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=False)

        # Act - Should not raise any error
        connector.abort_connection()

        # Assert
        assert connector.assoc is None

    def test_service_switch_closes_and_reopens_connection(self, mocker):
        """Test that switching services (e.g. C-FIND -> C-GET) closes the old connection
        and opens a new one with the correct presentation contexts."""
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=True)

        associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")

        # First association for C-FIND
        find_assoc = create_association_mock()
        find_assoc.is_alive.return_value = True
        find_assoc.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
            [{"PatientID": "12345", "QueryRetrieveLevel": "STUDY"}]
        )

        # Second association for C-GET
        get_assoc = create_association_mock()
        get_assoc.is_alive.return_value = True
        get_assoc.send_c_get.return_value = DicomTestHelper.create_successful_c_get_response()

        associate_mock.side_effect = [find_assoc, get_assoc]

        # Act: perform a C-FIND
        query = QueryDataset.create(
            PatientID="12345",
            StudyInstanceUID="1.2.3.4.5",
            QueryRetrieveLevel="STUDY",
        )
        list(connector.send_c_find(query))

        # After C-FIND with auto_close, connection is closed
        assert connector.assoc is None

        # Now open a persistent connection for C-FIND, then switch to C-GET
        connector.auto_close = False

        # Reset the mock for the persistent connections
        find_assoc2 = create_association_mock()
        find_assoc2.is_alive.return_value = True
        find_assoc2.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
            [{"PatientID": "12345", "QueryRetrieveLevel": "STUDY"}]
        )

        get_assoc2 = create_association_mock()
        get_assoc2.is_alive.return_value = True
        get_assoc2.send_c_get.return_value = DicomTestHelper.create_successful_c_get_response()

        associate_mock.side_effect = [find_assoc2, get_assoc2]

        # C-FIND with auto_close=False keeps connection open
        list(connector.send_c_find(query))
        assert connector.assoc is find_assoc2
        assert connector._current_service == "C-FIND"

        # C-GET should close the C-FIND connection and open a new one
        store_handler = MagicMock()
        store_errors = []
        connector.send_c_get(query, store_handler, store_errors)

        # The C-FIND association should have been released (closed)
        assert find_assoc2.release.called
        # The connector should now be on the C-GET association
        assert connector.assoc is get_assoc2
        assert connector._current_service == "C-GET"


@pytest.mark.django_db
class TestHandleGetAndMoveResponses:
    """Directly exercise the C-GET/C-MOVE response handling state machine."""

    def _connector(self) -> DimseConnector:
        return DimseConnector(DicomServerFactory.create(), auto_connect=False)

    def test_success_with_completed_suboperations(self):
        connector = self._connector()
        responses = iter(
            [(_status(Status.SUCCESS, NumberOfCompletedSuboperations=3), None)]
        )
        # Should not raise and should not log warnings
        connector._handle_get_and_move_responses(responses, "C-GET")
        assert connector.logs == []

    def test_all_suboperations_failed_raises(self):
        connector = self._connector()
        responses = iter(
            [
                (
                    _status(
                        Status.SUCCESS,
                        NumberOfCompletedSuboperations=0,
                        NumberOfFailedSuboperations=5,
                    ),
                    None,
                )
            ]
        )
        with pytest.raises(RetriableDicomError, match="All sub-operations failed"):
            connector._handle_get_and_move_responses(responses, "C-MOVE")

    def test_partial_failure_logs_warning(self):
        connector = self._connector()
        responses = iter(
            [
                (
                    _status(
                        Status.SUCCESS,
                        NumberOfCompletedSuboperations=3,
                        NumberOfFailedSuboperations=2,
                    ),
                    None,
                )
            ]
        )
        connector._handle_get_and_move_responses(responses, "C-GET")
        assert any("failed sub-operations" in log["title"].lower() for log in connector.logs)

    def test_warning_suboperations_logged(self):
        connector = self._connector()
        responses = iter(
            [
                (
                    _status(
                        Status.SUCCESS,
                        NumberOfCompletedSuboperations=3,
                        NumberOfWarningSuboperations=1,
                    ),
                    None,
                )
            ]
        )
        connector._handle_get_and_move_responses(responses, "C-GET")
        assert any("warning" in log["title"].lower() for log in connector.logs)

    def test_unknown_warning_status_logged(self):
        connector = self._connector()
        # WARNING category with no suboperation counts -> "Unexpected warnings"
        responses = iter([(_status(0xB000), None)])
        connector._handle_get_and_move_responses(responses, "C-MOVE")
        assert any("unexpected warnings" in log["title"].lower() for log in connector.logs)

    def test_silent_empty_success_does_not_raise(self):
        connector = self._connector()
        responses = iter(
            [
                (
                    _status(
                        Status.SUCCESS,
                        NumberOfCompletedSuboperations=0,
                        NumberOfFailedSuboperations=0,
                        NumberOfWarningSuboperations=0,
                    ),
                    None,
                )
            ]
        )
        # Should not raise (caller handles retry of silent-empty responses)
        connector._handle_get_and_move_responses(responses, "C-GET")

    def test_failure_with_failed_image_uids_raises(self):
        connector = self._connector()
        identifier = Dataset()
        identifier.FailedSOPInstanceUIDList = ["1.2.3", "1.2.4"]
        # 0xA700 ("Out of resources") maps to the STATUS_FAILURE category
        responses = iter([(_status(0xA700), identifier)])
        with pytest.raises(RetriableDicomError, match="Failed to transfer several images"):
            connector._handle_get_and_move_responses(responses, "C-GET")

    def test_failure_with_single_image_uid_string_raises(self):
        connector = self._connector()
        identifier = Dataset()
        identifier.FailedSOPInstanceUIDList = "1.2.3"
        responses = iter([(_status(0xA700), identifier)])
        with pytest.raises(RetriableDicomError, match="Failed to transfer several images"):
            connector._handle_get_and_move_responses(responses, "C-MOVE")

    def test_failure_without_identifier_raises(self):
        connector = self._connector()
        responses = iter([(_status(0xA700), None)])
        with pytest.raises(RetriableDicomError, match="Unexpected error during C-GET"):
            connector._handle_get_and_move_responses(responses, "C-GET")

    def test_missing_status_raises(self):
        connector = self._connector()
        # A missing status (None) models a timed-out C-MOVE; cast because the
        # method is typed for real status Datasets but must handle this edge.
        responses = cast(Iterator[tuple[Dataset, Dataset | None]], iter([(None, None)]))
        with pytest.raises(RetriableDicomError, match="Connection timed out"):
            connector._handle_get_and_move_responses(responses, "C-MOVE")


@pytest.mark.django_db
class TestSendCFind:
    """Cover C-FIND query model selection, limits and error branches."""

    def test_missing_query_retrieve_level_raises(self, mocker):
        connector = DimseConnector(DicomServerFactory.create(), auto_connect=False)
        # No QueryRetrieveLevel set on the query
        with pytest.raises(DicomError, match="Missing QueryRetrieveLevel"):
            list(connector.send_c_find(QueryDataset.create(PatientID="1")))

    def test_no_valid_query_model_raises(self, mocker):
        server = DicomServerFactory.create()
        server.study_root_find_support = False
        server.patient_root_find_support = False
        connector = DimseConnector(server, auto_connect=False)
        query = QueryDataset.create(QueryRetrieveLevel="STUDY", PatientID="1")
        with pytest.raises(DicomError, match="No valid Query/Retrieve Information Model"):
            list(connector.send_c_find(query))

    def test_limit_results_aborts_after_limit(self, mocker):
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=True)

        associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
        association_mock = create_association_mock()
        association_mock.is_alive.return_value = True
        associate_mock.return_value = association_mock
        association_mock.send_c_find.return_value = (
            DicomTestHelper.create_successful_c_find_responses(
                [
                    {"PatientID": "1", "QueryRetrieveLevel": "STUDY"},
                    {"PatientID": "2", "QueryRetrieveLevel": "STUDY"},
                    {"PatientID": "3", "QueryRetrieveLevel": "STUDY"},
                ]
            )
        )

        query = QueryDataset.create(QueryRetrieveLevel="STUDY", PatientID="1")
        results = list(connector.send_c_find(query, limit_results=2))

        # Only 2 results yielded, then abort_connection is called
        assert len(results) == 2
        assert association_mock.abort.called


@pytest.mark.django_db
class TestSendCGetMoveModelSelection:
    def test_c_get_no_valid_model_raises(self):
        server = DicomMoveServerFactory.create()  # get support disabled
        connector = DimseConnector(server, auto_connect=False)
        # No study uid -> can't pick a model
        query = QueryDataset.create(PatientID="1")
        with pytest.raises(DicomError, match="No valid Query/Retrieve Information Model for C-GET"):
            connector.send_c_get(query, MagicMock(), [])

    def test_c_move_no_valid_model_raises(self):
        server = DicomServerFactory.create()
        server.study_root_move_support = False
        server.patient_root_move_support = False
        connector = DimseConnector(server, auto_connect=False)
        query = QueryDataset.create(PatientID="1", StudyInstanceUID="1.123")
        with pytest.raises(
            DicomError, match="No valid Query/Retrieve Information Model for C-MOVE"
        ):
            connector.send_c_move(query, "DEST_AE")


@pytest.mark.django_db
class TestSendCStore:
    """Cover C-STORE success, warnings and the non-retriable error branches."""

    def _connector_with_assoc(self, mocker, status_code: int = Status.SUCCESS):
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=True)
        associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
        association_mock = create_association_mock()
        association_mock.is_alive.return_value = True
        association_mock.send_c_store.return_value = _status(status_code)
        associate_mock.return_value = association_mock
        return connector, association_mock

    def test_store_list_of_datasets_success(self, mocker):
        connector, association_mock = self._connector_with_assoc(mocker)
        ds = Dataset()
        ds.SOPInstanceUID = "1.2.3"
        ds.StudyInstanceUID = "1.123"

        connector.send_c_store([ds])

        association_mock.send_c_store.assert_called_once()

    def test_store_applies_modifier(self, mocker):
        connector, association_mock = self._connector_with_assoc(mocker)
        ds = Dataset()
        ds.SOPInstanceUID = "1.2.3"
        ds.StudyInstanceUID = "1.123"

        def modifier(dataset: Dataset) -> None:
            dataset.PatientID = "MODIFIED"

        connector.send_c_store([ds], modifier=modifier)

        stored = association_mock.send_c_store.call_args.args[0]
        assert stored.PatientID == "MODIFIED"

    def test_store_warning_status_recorded(self, mocker):
        # 0xB000 maps to STATUS_WARNING; should not raise
        connector, association_mock = self._connector_with_assoc(mocker, status_code=0xB007)
        ds = Dataset()
        ds.SOPInstanceUID = "1.2.3"
        ds.StudyInstanceUID = "1.123"

        connector.send_c_store([ds])

        association_mock.send_c_store.assert_called_once()

    def test_store_unsupported_server_raises(self, mocker):
        server = DicomServerFactory.create()
        server.store_scp_support = False
        connector = DimseConnector(server, auto_connect=False)
        with pytest.raises(DicomError, match="C-STORE operation not supported"):
            connector.send_c_store([Dataset()])

    def test_store_folder_not_a_directory_raises(self, mocker):
        connector, _ = self._connector_with_assoc(mocker)
        with tempfile.NamedTemporaryFile() as tmp:
            with pytest.raises(DicomError, match="not a valid folder"):
                connector.send_c_store(Path(tmp.name))

    def test_store_empty_folder_succeeds(self, mocker):
        connector, association_mock = self._connector_with_assoc(mocker)
        with tempfile.TemporaryDirectory() as tmp_dir:
            # An empty folder: nothing to store, no error
            connector.send_c_store(Path(tmp_dir))
        association_mock.send_c_store.assert_not_called()


@pytest.mark.django_db
class TestOpenCloseConnection:
    def test_open_connection_cleans_dead_assoc(self, mocker):
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=False)

        # Simulate a stale, dead association
        dead_assoc = MagicMock()
        dead_assoc.is_alive.return_value = False
        connector.assoc = dead_assoc

        associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
        new_assoc = create_association_mock()
        new_assoc.is_established = True
        associate_mock.return_value = new_assoc

        connector.open_connection("C-FIND")

        assert connector.assoc is new_assoc
        assert connector._current_service == "C-FIND"

    def test_associate_raises_when_not_established(self, mocker):
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=False)

        associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
        failed_assoc = create_association_mock()
        failed_assoc.is_established = False
        associate_mock.return_value = failed_assoc

        # _associate raises RetriableDicomError; stamina retries are configured at
        # import-time, so disable them for this connect attempt to keep the test fast.
        mocker.patch(
            "adit.core.utils.dimse_connector.DimseConnector._associate",
            side_effect=RetriableDicomError("Could not connect"),
        )

        with pytest.raises(RetriableDicomError, match="Could not connect"):
            connector.open_connection("C-FIND")

    def test_close_connection_releases_and_resets(self, mocker):
        server = DicomServerFactory.create()
        connector = DimseConnector(server, auto_connect=False)
        assoc = create_association_mock()
        connector.assoc = assoc
        connector._current_service = "C-FIND"

        connector.close_connection()

        assoc.release.assert_called_once()
        assert connector.assoc is None
        assert connector._current_service is None
