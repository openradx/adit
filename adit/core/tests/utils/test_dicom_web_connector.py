"""Unit tests for DicomWebConnector (DICOMweb egress connector).

These tests are intentionally NON-DB: they build an *unsaved* ``DicomServer``
model instance (only in-memory attributes are read by the connector) and patch
the underlying ``dicomweb_client.DICOMwebClient`` so no network or real client
construction happens.

The connector methods are wrapped by stamina retry decorators (see
``adit.core.utils.retry_config``). Retriable errors would otherwise be retried
several times with backoff, which both slows the suite down and inflates the
client call counts we assert on. The module-level ``_disable_stamina`` autouse
fixture turns retries off via ``stamina.set_active(False)`` so every method runs
exactly once, letting us assert call counts and observe the *first* raised
exception directly.
"""

from unittest.mock import MagicMock, patch

import pytest
import stamina
from pydicom import Dataset
from requests import HTTPError

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_web_connector import DicomWebConnector

PATCH_TARGET = "adit.core.utils.dicom_web_connector.DICOMwebClient"


@pytest.fixture(autouse=True)
def _disable_stamina():
    """Disable stamina retries so wrapped methods run exactly once."""
    stamina.set_active(False)
    yield
    stamina.set_active(True)


def make_server(**overrides) -> DicomServer:
    """Build an *unsaved* DicomServer with DICOMweb support enabled.

    The connector only reads attributes (no DB access), so we never call
    ``.save()``; this keeps the tests DB-free.
    """
    defaults = dict(
        ae_title="WEBPACS",
        dicomweb_root_url="http://pacs.example.com/dicomweb",
        dicomweb_qido_support=True,
        dicomweb_wado_support=True,
        dicomweb_stow_support=True,
    )
    defaults.update(overrides)
    return DicomServer(**defaults)


def http_error(status_code: int) -> HTTPError:
    """Build a requests.HTTPError whose response has the given status code."""
    response = MagicMock()
    response.status_code = status_code
    return HTTPError(response=response)


def make_dataset(sop_instance_uid: str = "1.2.3.4.5.6.7") -> Dataset:
    ds = Dataset()
    ds.PatientID = "PID"
    ds.StudyInstanceUID = "1.2.3.4.5"
    ds.SeriesInstanceUID = "1.2.3.4.5.6"
    ds.SOPInstanceUID = sop_instance_uid
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    return ds


def patch_client(fake_client: MagicMock):
    """Patch DICOMwebClient so the connector receives ``fake_client``."""
    return patch(PATCH_TARGET, return_value=fake_client)


# ---------------------------------------------------------------------------
# Client construction / connection lifecycle
# ---------------------------------------------------------------------------


class TestClientSetup:
    def test_client_constructed_with_server_config(self):
        """The connector builds DICOMwebClient from the server's config."""
        server = make_server(
            dicomweb_qido_prefix="qido",
            dicomweb_wado_prefix="wado",
            dicomweb_stow_prefix="stow",
            dicomweb_authorization_header="Bearer secret-token",
        )
        connector = DicomWebConnector(server)

        fake_client = MagicMock()
        fake_client.search_for_studies.return_value = []
        with patch(PATCH_TARGET, return_value=fake_client) as client_cls:
            connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))

        kwargs = client_cls.call_args.kwargs
        assert kwargs["url"] == "http://pacs.example.com/dicomweb"
        assert kwargs["qido_url_prefix"] == "qido"
        assert kwargs["wado_url_prefix"] == "wado"
        assert kwargs["stow_url_prefix"] == "stow"
        assert kwargs["headers"] == {"Authorization": "Bearer secret-token"}

    def test_empty_prefixes_passed_as_none(self):
        """Blank prefix fields are normalized to None for the client."""
        server = make_server()  # prefixes default to "" (blank CharField)
        connector = DicomWebConnector(server)

        fake_client = MagicMock()
        fake_client.search_for_studies.return_value = []
        with patch(PATCH_TARGET, return_value=fake_client) as client_cls:
            connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))

        kwargs = client_cls.call_args.kwargs
        assert kwargs["qido_url_prefix"] is None
        assert kwargs["wado_url_prefix"] is None
        assert kwargs["stow_url_prefix"] is None
        # No auth header configured -> empty headers dict.
        assert kwargs["headers"] == {}

    def test_missing_root_url_raises_dicom_error(self):
        """A server without a DICOMweb root url cannot connect."""
        server = make_server(dicomweb_root_url="")
        connector = DicomWebConnector(server)

        with patch(PATCH_TARGET) as client_cls:
            with pytest.raises(DicomError, match="Missing DICOMweb root url"):
                connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))

        # The client should never be constructed if the url is missing.
        client_cls.assert_not_called()

    def test_client_reset_to_none_after_call(self):
        """The connector clears self.dicomweb_client when the method finishes."""
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.search_for_studies.return_value = []
        with patch_client(fake_client):
            connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))

        assert connector.dicomweb_client is None


# ---------------------------------------------------------------------------
# QIDO-RS (search)
# ---------------------------------------------------------------------------


class TestSendQidoRs:
    def test_study_level_calls_search_for_studies(self):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.search_for_studies.return_value = [
            {"00100020": {"vr": "LO", "Value": ["PAT-1"]}}
        ]
        with patch_client(fake_client):
            query = QueryDataset.create(QueryRetrieveLevel="STUDY", PatientID="PAT-1")
            results = connector.send_qido_rs(query, limit_results=5)

        # Returns ResultDataset objects parsed from the JSON the client returned.
        assert len(results) == 1
        assert results[0].PatientID == "PAT-1"

        fake_client.search_for_studies.assert_called_once()
        kwargs = fake_client.search_for_studies.call_args.kwargs
        assert kwargs["limit"] == 5
        # QueryRetrieveLevel is popped from the search filters but kept as a field.
        assert "QueryRetrieveLevel" not in kwargs["search_filters"]
        assert kwargs["search_filters"] == {"PatientID": "PAT-1"}
        assert "PatientID" in kwargs["fields"]

    def test_series_level_passes_study_uid_positionally(self):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.search_for_series.return_value = []
        with patch_client(fake_client):
            query = QueryDataset.create(
                QueryRetrieveLevel="SERIES", StudyInstanceUID="1.2.3"
            )
            connector.send_qido_rs(query)

        # StudyInstanceUID is popped from filters and passed as the first arg.
        args, kwargs = fake_client.search_for_series.call_args
        assert args[0] == "1.2.3"
        assert "StudyInstanceUID" not in kwargs["search_filters"]

    def test_image_level_passes_study_and_series_uid_positionally(self):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.search_for_instances.return_value = []
        with patch_client(fake_client):
            query = QueryDataset.create(
                QueryRetrieveLevel="IMAGE",
                StudyInstanceUID="1.2.3",
                SeriesInstanceUID="1.2.3.4",
            )
            connector.send_qido_rs(query)

        args, kwargs = fake_client.search_for_instances.call_args
        assert args[0] == "1.2.3"
        assert args[1] == "1.2.3.4"
        assert "StudyInstanceUID" not in kwargs["search_filters"]
        assert "SeriesInstanceUID" not in kwargs["search_filters"]

    def test_missing_query_retrieve_level_raises(self):
        connector = DicomWebConnector(make_server())
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="Missing QueryRetrieveLevel"):
                connector.send_qido_rs(QueryDataset.create(PatientID="X"))

    def test_qido_unsupported_raises_dicom_error(self):
        connector = DicomWebConnector(make_server(dicomweb_qido_support=False))
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="QIDO-RS is not supported"):
                connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))

    def test_retriable_http_error_mapped_to_retriable_dicom_error(self):
        """A 503 from the client becomes a RetriableDicomError (single call)."""
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.search_for_studies.side_effect = http_error(503)
        with patch_client(fake_client):
            with pytest.raises(RetriableDicomError) as exc_info:
                connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))

        assert "QIDO-RS" in str(exc_info.value)
        # With stamina disabled the client is hit exactly once.
        assert fake_client.search_for_studies.call_count == 1

    def test_non_retriable_http_error_reraised(self):
        """A 404 is permanent and re-raised as the original HTTPError."""
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.search_for_studies.side_effect = http_error(404)
        with patch_client(fake_client):
            with pytest.raises(HTTPError) as exc_info:
                connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))

        assert exc_info.value.response is not None
        assert exc_info.value.response.status_code == 404


# ---------------------------------------------------------------------------
# WADO-RS (retrieve)
# ---------------------------------------------------------------------------


class TestSendWadoRs:
    def test_study_level_iterates_study(self):
        connector = DicomWebConnector(make_server())
        ds = make_dataset()
        fake_client = MagicMock()
        fake_client.iter_study.return_value = iter([ds])
        with patch_client(fake_client):
            query = QueryDataset.create(
                QueryRetrieveLevel="STUDY", StudyInstanceUID="1.2.3"
            )
            results = list(connector.send_wado_rs(query))

        assert results == [ds]
        fake_client.iter_study.assert_called_once_with("1.2.3")

    def test_series_level_iterates_series(self):
        connector = DicomWebConnector(make_server())
        ds = make_dataset()
        fake_client = MagicMock()
        fake_client.iter_series.return_value = iter([ds])
        with patch_client(fake_client):
            query = QueryDataset.create(
                QueryRetrieveLevel="SERIES",
                StudyInstanceUID="1.2.3",
                SeriesInstanceUID="1.2.3.4",
            )
            results = list(connector.send_wado_rs(query))

        assert results == [ds]
        fake_client.iter_series.assert_called_once_with("1.2.3", "1.2.3.4")

    def test_image_level_retrieves_single_instance(self):
        connector = DicomWebConnector(make_server())
        ds = make_dataset()
        fake_client = MagicMock()
        fake_client.retrieve_instance.return_value = ds
        with patch_client(fake_client):
            query = QueryDataset.create(
                QueryRetrieveLevel="IMAGE",
                StudyInstanceUID="1.2.3",
                SeriesInstanceUID="1.2.3.4",
                SOPInstanceUID="1.2.3.4.5",
            )
            results = list(connector.send_wado_rs(query))

        assert results == [ds]
        fake_client.retrieve_instance.assert_called_once_with(
            "1.2.3", "1.2.3.4", "1.2.3.4.5"
        )

    def test_missing_query_retrieve_level_raises(self):
        connector = DicomWebConnector(make_server())
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="Missing QueryRetrieveLevel"):
                list(connector.send_wado_rs(QueryDataset.create(StudyInstanceUID="1.2.3")))

    def test_wado_unsupported_raises_dicom_error(self):
        connector = DicomWebConnector(make_server(dicomweb_wado_support=False))
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="WADO-RS is not supported"):
                list(
                    connector.send_wado_rs(
                        QueryDataset.create(
                            QueryRetrieveLevel="STUDY", StudyInstanceUID="1.2.3"
                        )
                    )
                )

    def test_series_level_missing_study_uid_raises(self):
        connector = DicomWebConnector(make_server())
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="Missing StudyInstanceUID"):
                list(
                    connector.send_wado_rs(
                        QueryDataset.create(
                            QueryRetrieveLevel="SERIES", SeriesInstanceUID="1.2.3.4"
                        )
                    )
                )

    def test_series_level_missing_series_uid_raises(self):
        connector = DicomWebConnector(make_server())
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="Missing SeriesInstanceUID"):
                list(
                    connector.send_wado_rs(
                        QueryDataset.create(
                            QueryRetrieveLevel="SERIES", StudyInstanceUID="1.2.3"
                        )
                    )
                )

    def test_image_level_missing_sop_uid_raises(self):
        connector = DicomWebConnector(make_server())
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="Missing SOPInstanceUID"):
                list(
                    connector.send_wado_rs(
                        QueryDataset.create(
                            QueryRetrieveLevel="IMAGE",
                            StudyInstanceUID="1.2.3",
                            SeriesInstanceUID="1.2.3.4",
                        )
                    )
                )

    def test_retriable_http_error_mapped_to_retriable_dicom_error(self):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.iter_study.side_effect = http_error(503)
        with patch_client(fake_client):
            query = QueryDataset.create(
                QueryRetrieveLevel="STUDY", StudyInstanceUID="1.2.3"
            )
            with pytest.raises(RetriableDicomError) as exc_info:
                list(connector.send_wado_rs(query))

        assert "WADO-RS" in str(exc_info.value)

    def test_non_retriable_http_error_reraised(self):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.iter_study.side_effect = http_error(404)
        with patch_client(fake_client):
            query = QueryDataset.create(
                QueryRetrieveLevel="STUDY", StudyInstanceUID="1.2.3"
            )
            with pytest.raises(HTTPError) as exc_info:
                list(connector.send_wado_rs(query))

        assert exc_info.value.response is not None
        assert exc_info.value.response.status_code == 404


# ---------------------------------------------------------------------------
# STOW-RS (store)
# ---------------------------------------------------------------------------


class TestSendStowRs:
    def test_stores_each_dataset(self):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        ds1 = make_dataset("1.1")
        ds2 = make_dataset("2.2")
        with patch_client(fake_client):
            connector.send_stow_rs([ds1, ds2])

        assert fake_client.store_instances.call_count == 2
        # Each call stores a single-element list with the right dataset.
        stored = [call.args[0][0] for call in fake_client.store_instances.call_args_list]
        assert stored == [ds1, ds2]

    def test_modifier_applied_before_store(self):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        ds = make_dataset("1.1")

        def modifier(dataset: Dataset) -> None:
            dataset.PatientID = "MODIFIED"

        with patch_client(fake_client):
            connector.send_stow_rs([ds], modifier=modifier)

        assert ds.PatientID == "MODIFIED"
        stored_ds = fake_client.store_instances.call_args.args[0][0]
        assert stored_ds.PatientID == "MODIFIED"

    def test_stow_unsupported_raises_dicom_error(self):
        connector = DicomWebConnector(make_server(dicomweb_stow_support=False))
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="STOW-RS is not supported"):
                connector.send_stow_rs([make_dataset()])

    def test_invalid_folder_raises_dicom_error(self, tmp_path):
        connector = DicomWebConnector(make_server())
        missing = tmp_path / "does-not-exist"
        with patch_client(MagicMock()):
            with pytest.raises(DicomError, match="not a valid folder"):
                connector.send_stow_rs(missing)

    def test_retriable_failure_raises_retriable_dicom_error(self):
        """A retriable per-instance failure (503) is collected and surfaced.

        The connector swallows the individual retriable HTTPError, records the
        SOPInstanceUID, and raises a single RetriableDicomError after the batch.
        """
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.store_instances.side_effect = http_error(503)
        with patch_client(fake_client):
            with pytest.raises(RetriableDicomError, match="STOW-RS operation"):
                connector.send_stow_rs([make_dataset("1.1")])

        # Still attempted exactly once (stamina disabled, no inner retry).
        assert fake_client.store_instances.call_count == 1

    def test_non_retriable_failure_reraised(self):
        """A permanent per-instance failure (400) re-raises the HTTPError."""
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.store_instances.side_effect = http_error(400)
        with patch_client(fake_client):
            with pytest.raises(HTTPError) as exc_info:
                connector.send_stow_rs([make_dataset("1.1")])

        assert exc_info.value.response is not None
        assert exc_info.value.response.status_code == 400


# ---------------------------------------------------------------------------
# Error mapping helper (_handle_dicomweb_error) via the public surface
# ---------------------------------------------------------------------------


class TestErrorMapping:
    @pytest.mark.parametrize("status_code", [408, 409, 429, 500, 503, 504])
    def test_all_retriable_statuses_map_to_retriable_dicom_error(self, status_code):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.search_for_studies.side_effect = http_error(status_code)
        with patch_client(fake_client):
            with pytest.raises(RetriableDicomError):
                connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
    def test_permanent_statuses_reraise_http_error(self, status_code):
        connector = DicomWebConnector(make_server())
        fake_client = MagicMock()
        fake_client.search_for_studies.side_effect = http_error(status_code)
        with patch_client(fake_client):
            with pytest.raises(HTTPError):
                connector.send_qido_rs(QueryDataset.create(QueryRetrieveLevel="STUDY"))
