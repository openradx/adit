"""Tests for DimseConnector retry behavior and connection management."""

from unittest.mock import MagicMock, patch

import pytest

from adit.core.errors import RetriableDicomError
from adit.core.factories import DicomServerFactory
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dimse_connector import DimseConnector
from adit.core.utils.testing_helpers import DicomTestHelper, create_association_mock


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
