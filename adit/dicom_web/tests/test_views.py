"""Handler-body tests for the DICOMweb REST API views (`adit/dicom_web/views.py`).

These complement ``test_authorization.py`` (which exercises only the auth/permission
layer). Here we drive the *bodies* of the QIDO-RS / WADO-RS / STOW-RS handlers: the
query-parameter extraction, result serialization, content negotiation, the streaming
WADO response, the STOW store loop (success / failed / study-uid filtering), and the
error responses (validation errors, unsupported media type).

No live PACS is needed: the DICOM network boundary helpers
(``qido_find`` / ``wado_retrieve`` / ``stow_store`` / ``parse_request_in_chunks``)
are stubbed at the ``adit.dicom_web.views`` module level with realistic return values,
so execution reaches and runs the handler bodies. The factory servers point at
unroutable hosts, which is irrelevant because we never call the real helpers.

The views are async (adrf ``AsyncApiView``) and must be driven with Django's
``AsyncClient`` + ``django_db(transaction=True)`` (see the docstring in
``test_authorization.py`` for why).
"""

from collections.abc import AsyncIterator
from typing import cast
from unittest.mock import patch

import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group
from adit_radis_shared.token_authentication.models import Token
from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from django.test import AsyncClient
from django.urls import reverse
from pydicom import Dataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from adit.core.factories import DicomServerFactory, DicomWebServerFactory
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.dicom_dataset import ResultDataset

STUDY_UID = "1.2.840.113619.2.55.3.604688.1"
SERIES_UID = "1.2.840.113619.2.55.3.604688.2"
IMAGE_UID = "1.2.840.113619.2.55.3.604688.3"
SOP_CLASS_UID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage

WADO_DICOM_ACCEPT = "multipart/related; type=application/dicom"
WADO_JSON_ACCEPT = "application/dicom+json"


def _auth(token_string: str) -> dict:
    return {"authorization": f"Token {token_string}"}


# --- async-safe ORM setup helpers -------------------------------------------


@sync_to_async
def setup_user_and_server(*, web: bool = False, source: bool = True, destination: bool = False):
    """Create a user with a token + a server the user's group can access."""
    user = UserFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    _, token_string = Token.objects.create_token(user, "", None)
    if web:
        server = DicomWebServerFactory.create()
    else:
        server = DicomServerFactory.create()
    grant_access(group, server, source=source, destination=destination)
    return token_string, server


def make_result(**attrs) -> ResultDataset:
    ds = Dataset()
    for key, value in attrs.items():
        setattr(ds, key, value)
    return ResultDataset(ds)


def make_image(**attrs) -> Dataset:
    ds = Dataset()
    for key, value in attrs.items():
        setattr(ds, key, value)
    return ds


def make_storable_image(**attrs) -> Dataset:
    """A dataset with file_meta + transfer syntax so it serializes to real DICOM bytes
    (exercises the WADO multipart renderer's normal, non-error path)."""
    ds = make_image(**attrs)
    ds.ensure_file_meta()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = attrs.get("SOPClassUID", CTImageStorage)
    ds.file_meta.MediaStorageSOPInstanceUID = attrs.get("SOPInstanceUID", generate_uid())
    return ds


# ---------------------------------------------------------------------------
# QIDO-RS: query handler bodies
# ---------------------------------------------------------------------------


class TestQueryStudies:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_returns_serialized_study_results(self):
        token, server = await setup_user_and_server()

        results = [
            make_result(StudyInstanceUID=STUDY_UID, PatientID="PAT001"),
            make_result(StudyInstanceUID="1.2.3.9", PatientID="PAT002"),
        ]

        async def fake_qido_find(src, query_ds, limit, level):
            assert level == "STUDY"
            return results

        with patch("adit.dicom_web.views.qido_find", new=fake_qido_find):
            response = await AsyncClient().get(
                reverse("qido_rs-studies", args=[server.ae_title]), headers=_auth(token)
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        # to_json_dict serializes by DICOM tag; StudyInstanceUID == (0020,000D)
        assert data[0]["0020000D"]["Value"] == [STUDY_UID]

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_passes_limit_and_includefield_params(self):
        token, server = await setup_user_and_server()
        captured = {}

        async def fake_qido_find(src, query_ds, limit, level):
            captured["limit"] = limit
            # ensure_elements() adds the includefield as an (empty) element, so it is
            # present on the underlying dataset even though .has() (non-empty check)
            # would report False.
            captured["has_modalities"] = "ModalitiesInStudy" in query_ds.dataset
            captured["patient_id"] = query_ds.get("PatientID", None)
            return []

        url = reverse("qido_rs-studies", args=[server.ae_title])
        with patch("adit.dicom_web.views.qido_find", new=fake_qido_find):
            response = await AsyncClient().get(
                f"{url}?limit=7&includefield=ModalitiesInStudy&PatientID=PAT001",
                headers=_auth(token),
            )

        assert response.status_code == 200
        # The "limit" param is popped and parsed to an int (views.py:121).
        assert captured["limit"] == 7
        # "includefield" is ensured on the query dataset (views.py:124).
        assert captured["has_modalities"] is True
        # Ordinary GET params land in the query (views.py:111).
        assert captured["patient_id"] == "PAT001"

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_value_error_becomes_400(self):
        token, server = await setup_user_and_server()

        async def fake_qido_find(src, query_ds, limit, level):
            raise ValueError("bad query")

        with patch("adit.dicom_web.views.qido_find", new=fake_qido_find):
            response = await AsyncClient().get(
                reverse("qido_rs-studies", args=[server.ae_title]), headers=_auth(token)
            )

        # ValueError -> ValidationError -> HTTP 400 (views.py:140-142).
        assert response.status_code == 400


class TestQuerySeries:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_injects_study_uid_and_serializes(self):
        token, server = await setup_user_and_server()
        captured = {}

        async def fake_qido_find(src, query_ds, limit, level):
            captured["level"] = level
            captured["study_uid"] = query_ds.get("StudyInstanceUID", None)
            return [make_result(SeriesInstanceUID=SERIES_UID)]

        url = reverse("qido_rs-series_with_study_uid", args=[server.ae_title, STUDY_UID])
        with patch("adit.dicom_web.views.qido_find", new=fake_qido_find):
            response = await AsyncClient().get(url, headers=_auth(token))

        assert response.status_code == 200
        assert captured["level"] == "SERIES"
        # The study_uid from the URL is injected into the query (views.py:114).
        assert captured["study_uid"] == STUDY_UID
        assert response.json()[0]["0020000E"]["Value"] == [SERIES_UID]

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_value_error_becomes_400(self):
        token, server = await setup_user_and_server()

        async def fake_qido_find(src, query_ds, limit, level):
            raise ValueError("bad series query")

        url = reverse("qido_rs-series_with_study_uid", args=[server.ae_title, STUDY_UID])
        with patch("adit.dicom_web.views.qido_find", new=fake_qido_find):
            response = await AsyncClient().get(url, headers=_auth(token))

        assert response.status_code == 400


class TestQueryImages:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_injects_study_and_series_uid_and_serializes(self):
        token, server = await setup_user_and_server()
        captured = {}

        async def fake_qido_find(src, query_ds, limit, level):
            captured["level"] = level
            captured["study_uid"] = query_ds.get("StudyInstanceUID", None)
            captured["series_uid"] = query_ds.get("SeriesInstanceUID", None)
            return [make_result(SOPInstanceUID=IMAGE_UID)]

        url = reverse(
            "qido_rs-images_with_study_uid_and_series_uid",
            args=[server.ae_title, STUDY_UID, SERIES_UID],
        )
        with patch("adit.dicom_web.views.qido_find", new=fake_qido_find):
            response = await AsyncClient().get(url, headers=_auth(token))

        assert response.status_code == 200
        assert captured["level"] == "IMAGE"
        # Both study_uid and series_uid injected (views.py:114, 117).
        assert captured["study_uid"] == STUDY_UID
        assert captured["series_uid"] == SERIES_UID
        assert response.json()[0]["00080018"]["Value"] == [IMAGE_UID]

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_value_error_becomes_400(self):
        token, server = await setup_user_and_server()

        async def fake_qido_find(src, query_ds, limit, level):
            raise ValueError("bad image query")

        url = reverse(
            "qido_rs-images_with_study_uid_and_series_uid",
            args=[server.ae_title, STUDY_UID, SERIES_UID],
        )
        with patch("adit.dicom_web.views.qido_find", new=fake_qido_find):
            response = await AsyncClient().get(url, headers=_auth(token))

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# WADO-RS: retrieve handler bodies (streaming + metadata)
# ---------------------------------------------------------------------------


def _patch_wado(images: list[Dataset]):
    """Patch wado_retrieve to yield the given images as an async iterator."""

    async def fake_wado_retrieve(*args, **kwargs):
        for image in images:
            yield image

    return patch("adit.dicom_web.views.wado_retrieve", new=fake_wado_retrieve)


class TestRetrieveStudyStreaming:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_streams_multipart_dicom(self):
        token, server = await setup_user_and_server(web=True)
        image = make_storable_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
            PatientID="PAT001",
        )

        url = reverse("wado_rs-study_with_study_uid", args=[server.ae_title, STUDY_UID])
        headers = {**_auth(token), "accept": WADO_DICOM_ACCEPT}
        with _patch_wado([image]):
            response = await AsyncClient().get(url, headers=headers)

        assert response.status_code == 200
        assert response["Content-Type"].startswith("multipart/related")
        body = b"".join(
            [
                chunk
                async for chunk in cast(
                    AsyncIterator[bytes], cast(StreamingHttpResponse, response).streaming_content
                )
            ]
        )
        # The multipart body must contain a boundary and the DICOM part header.
        assert b"adit-boundary" in body
        assert b"application/dicom" in body
        # A serialized DICOM instance includes the DICM magic preamble marker.
        assert b"DICM" in body

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_passes_pseudonym_and_trial_params(self):
        token, server = await setup_user_and_server(web=True)
        captured = {}

        async def fake_wado_retrieve(src, query, level, **kwargs):
            captured.update(kwargs)
            captured["level"] = level
            captured["study_uid"] = query["StudyInstanceUID"]
            return
            yield  # pragma: no cover

        url = reverse("wado_rs-study_with_study_uid", args=[server.ae_title, STUDY_UID])
        headers = {**_auth(token), "accept": WADO_DICOM_ACCEPT}
        full_url = f"{url}?pseudonym=PSEUDO1&trial_protocol_id=TRIAL1&trial_protocol_name=NAME1"
        with patch("adit.dicom_web.views.wado_retrieve", new=fake_wado_retrieve):
            response = await AsyncClient().get(full_url, headers=headers)
            # Consume the stream so the view body runs to completion.
            [
                chunk
                async for chunk in cast(
                    AsyncIterator[bytes], cast(StreamingHttpResponse, response).streaming_content
                )
            ]

        assert response.status_code == 200
        assert captured["level"] == "STUDY"
        assert captured["study_uid"] == STUDY_UID
        assert captured["pseudonym"] == "PSEUDO1"
        assert captured["trial_protocol_id"] == "TRIAL1"
        assert captured["trial_protocol_name"] == "NAME1"

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_invalid_pseudonym_returns_400(self):
        token, server = await setup_user_and_server(web=True)

        url = reverse("wado_rs-study_with_study_uid", args=[server.ae_title, STUDY_UID])
        headers = {**_auth(token), "accept": WADO_DICOM_ACCEPT}
        # Backslash makes the pseudonym invalid -> ParseError (views.py:251-255).
        with _patch_wado([]):
            response = await AsyncClient().get(f"{url}?pseudonym=bad%5Cvalue", headers=headers)

        assert response.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_invalid_trial_protocol_id_returns_400(self):
        token, server = await setup_user_and_server(web=True)

        url = reverse("wado_rs-study_with_study_uid", args=[server.ae_title, STUDY_UID])
        headers = {**_auth(token), "accept": WADO_DICOM_ACCEPT}
        with _patch_wado([]):
            response = await AsyncClient().get(
                f"{url}?trial_protocol_id=bad%5Cvalue", headers=headers
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_invalid_trial_protocol_name_returns_400(self):
        token, server = await setup_user_and_server(web=True)

        url = reverse("wado_rs-study_with_study_uid", args=[server.ae_title, STUDY_UID])
        headers = {**_auth(token), "accept": WADO_DICOM_ACCEPT}
        # Backslash makes the trial protocol name invalid -> ParseError (views.py:271-272).
        with _patch_wado([]):
            response = await AsyncClient().get(
                f"{url}?trial_protocol_name=bad%5Cvalue", headers=headers
            )

        assert response.status_code == 400


class TestRetrieveStudyMetadata:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_returns_metadata_json_without_pixeldata(self):
        token, server = await setup_user_and_server(web=True)
        image = make_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
            PatientID="PAT001",
        )
        image.PixelData = b"\x00\x01\x02\x03"

        url = reverse("wado_rs-study_metadata_with_study_uid", args=[server.ae_title, STUDY_UID])
        headers = {**_auth(token), "accept": WADO_JSON_ACCEPT}
        with _patch_wado([image]):
            response = await AsyncClient().get(url, headers=headers)

        assert response.status_code == 200
        metadata = response.json()
        # extract_metadata returns a list of json dicts (one per image), with
        # PixelData stripped (views.py:242-246).
        assert isinstance(metadata, list)
        assert len(metadata) == 1
        assert "7FE00010" not in metadata[0]  # PixelData tag removed
        assert metadata[0]["00080018"]["Value"] == [IMAGE_UID]


class TestRetrieveSeries:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_streams_series(self):
        token, server = await setup_user_and_server(web=True)
        image = make_storable_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
        )
        captured = {}

        async def fake_wado_retrieve(src, query, level, **kwargs):
            captured["level"] = level
            captured["series_uid"] = query["SeriesInstanceUID"]
            yield image

        url = reverse(
            "wado_rs-series_with_study_uid_and_series_uid",
            args=[server.ae_title, STUDY_UID, SERIES_UID],
        )
        headers = {**_auth(token), "accept": WADO_DICOM_ACCEPT}
        with patch("adit.dicom_web.views.wado_retrieve", new=fake_wado_retrieve):
            response = await AsyncClient().get(url, headers=headers)
            body = b"".join(
                [
                    chunk
                    async for chunk in cast(
                        AsyncIterator[bytes],
                        cast(StreamingHttpResponse, response).streaming_content,
                    )
                ]
            )

        assert response.status_code == 200
        assert captured["level"] == "SERIES"
        assert captured["series_uid"] == SERIES_UID
        assert b"adit-boundary" in body

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_series_metadata_json(self):
        token, server = await setup_user_and_server(web=True)
        image = make_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
        )

        url = reverse(
            "wado_rs-series_metadata_with_study_uid_and_series_uid",
            args=[server.ae_title, STUDY_UID, SERIES_UID],
        )
        headers = {**_auth(token), "accept": WADO_JSON_ACCEPT}
        with _patch_wado([image]):
            response = await AsyncClient().get(url, headers=headers)

        assert response.status_code == 200
        assert response.json()[0]["00080018"]["Value"] == [IMAGE_UID]


class TestRetrieveImage:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_streams_single_image(self):
        token, server = await setup_user_and_server(web=True)
        image = make_storable_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
        )
        captured = {}

        async def fake_wado_retrieve(src, query, level, **kwargs):
            captured["level"] = level
            captured["sop_uid"] = query["SOPInstanceUID"]
            yield image

        url = reverse(
            "wado_rs-image_with_study_uid_and_series_uid_and_image_uid",
            args=[server.ae_title, STUDY_UID, SERIES_UID, IMAGE_UID],
        )
        headers = {**_auth(token), "accept": WADO_DICOM_ACCEPT}
        with patch("adit.dicom_web.views.wado_retrieve", new=fake_wado_retrieve):
            response = await AsyncClient().get(url, headers=headers)
            body = b"".join(
                [
                    chunk
                    async for chunk in cast(
                        AsyncIterator[bytes],
                        cast(StreamingHttpResponse, response).streaming_content,
                    )
                ]
            )

        assert response.status_code == 200
        assert captured["level"] == "IMAGE"
        assert captured["sop_uid"] == IMAGE_UID
        assert b"adit-boundary" in body

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_image_metadata_json(self):
        token, server = await setup_user_and_server(web=True)
        image = make_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
        )

        url = reverse(
            "wado_rs-image_metadata_with_study_uid_and_series_uid_and_image_uid",
            args=[server.ae_title, STUDY_UID, SERIES_UID, IMAGE_UID],
        )
        headers = {**_auth(token), "accept": WADO_JSON_ACCEPT}
        with _patch_wado([image]):
            response = await AsyncClient().get(url, headers=headers)

        assert response.status_code == 200
        assert response.json()[0]["00080018"]["Value"] == [IMAGE_UID]


class TestRetrieveServerSupport:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_non_wado_capable_server_returns_400(self):
        """A plain DIMSE server lacking GET/MOVE/WADO support is rejected (views.py:216)."""
        from adit.core.models import DicomServer

        @sync_to_async
        def setup():
            user = UserFactory.create()
            group = GroupFactory.create()
            add_user_to_group(user, group)
            _, token_string = Token.objects.create_token(user, "", None)
            # Build a server with NO retrieve capabilities at all.
            server = DicomServerFactory.create(
                study_root_get_support=False,
                study_root_move_support=False,
                patient_root_get_support=False,
                patient_root_move_support=False,
                dicomweb_wado_support=False,
            )
            grant_access(group, server, source=True)
            # Sanity: ensure flags really are all off.
            fresh = DicomServer.objects.get(pk=server.pk)
            assert not (
                fresh.study_root_get_support
                or fresh.study_root_move_support
                or fresh.dicomweb_wado_support
            )
            return token_string, server

        token, server = await setup()
        url = reverse("wado_rs-study_with_study_uid", args=[server.ae_title, STUDY_UID])
        headers = {**_auth(token), "accept": WADO_DICOM_ACCEPT}
        with _patch_wado([]):
            response = await AsyncClient().get(url, headers=headers)

        # ParseError -> HTTP 400.
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# STOW-RS: store handler body
# ---------------------------------------------------------------------------

STOW_CONTENT_TYPE = "multipart/related; type=application/dicom; boundary=adittest"


def _patch_parse(datasets: list[Dataset | None]):
    async def fake_parse(request):
        for ds in datasets:
            yield ds

    return patch("adit.dicom_web.views.parse_request_in_chunks", new=fake_parse)


def _stow_result(ds: Dataset) -> Dataset:
    result = Dataset()
    result.SOPClassUID = ds.SOPClassUID
    result.SOPInstanceUID = ds.SOPInstanceUID
    return result


class TestStoreImages:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_unsupported_media_type_returns_415(self):
        token, server = await setup_user_and_server(source=False, destination=True)

        url = reverse("stow_rs-series", args=[server.ae_title])
        # Wrong content type -> UnsupportedMediaType (views.py:515).
        response = await AsyncClient().post(
            url, data=b"x", content_type="application/json", headers=_auth(token)
        )
        assert response.status_code == 415

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_successful_store_collects_referenced_sop(self):
        token, server = await setup_user_and_server(source=False, destination=True)
        ds = make_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
        )

        async def fake_stow_store(dest, instance):
            return _stow_result(instance), False  # not failed

        url = reverse("stow_rs-series", args=[server.ae_title])
        with _patch_parse([ds]), patch("adit.dicom_web.views.stow_store", new=fake_stow_store):
            response = await AsyncClient().post(
                url, data=b"body", content_type=STOW_CONTENT_TYPE, headers=_auth(token)
            )

        assert response.status_code == 200
        result = response.json()
        # The stored SOP lands in ReferencedSOPSequence (views.py:546).
        assert "00081199" in result  # ReferencedSOPSequence
        assert len(result["00081199"]["Value"]) == 1
        # FailedSOPSequence (0008,1198) is initialized empty up front (views.py:521),
        # so it is present but must carry no failures for a successful store.
        assert result["00081198"]["Value"] == []

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_failed_store_collects_failed_sop(self):
        token, server = await setup_user_and_server(source=False, destination=True)
        ds = make_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
        )

        async def fake_stow_store(dest, instance):
            result = _stow_result(instance)
            result.FailureReason = "0110"
            return result, True  # failed

        url = reverse("stow_rs-series", args=[server.ae_title])
        with _patch_parse([ds]), patch("adit.dicom_web.views.stow_store", new=fake_stow_store):
            response = await AsyncClient().post(
                url, data=b"body", content_type=STOW_CONTENT_TYPE, headers=_auth(token)
            )

        assert response.status_code == 200
        result = response.json()
        # The failed SOP lands in FailedSOPSequence (views.py:544).
        assert "00081198" in result  # FailedSOPSequence

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_study_uid_filter_skips_mismatched_instance(self):
        """With a study_uid in the URL, instances of other studies are skipped
        and a RetrieveURL is set (views.py:529-535)."""
        token, server = await setup_user_and_server(source=False, destination=True)
        # This instance belongs to a DIFFERENT study than the URL study_uid.
        ds = make_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID="9.9.9.9",
            SeriesInstanceUID=SERIES_UID,
        )
        store_calls = []

        async def fake_stow_store(dest, instance):
            store_calls.append(instance)
            return _stow_result(instance), False

        url = reverse("stow_rs-series_with_study_uid", args=[server.ae_title, STUDY_UID])
        with _patch_parse([ds]), patch("adit.dicom_web.views.stow_store", new=fake_stow_store):
            response = await AsyncClient().post(
                url, data=b"body", content_type=STOW_CONTENT_TYPE, headers=_auth(token)
            )

        assert response.status_code == 200
        # The mismatched instance must be skipped (stow_store never called).
        assert store_calls == []
        result = response.json()
        # RetrieveURL is still set on the results (views.py:530).
        assert "00081190" in result  # RetrieveURL

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_study_uid_filter_stores_matching_instance(self):
        token, server = await setup_user_and_server(source=False, destination=True)
        ds = make_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,  # matches the URL study_uid
            SeriesInstanceUID=SERIES_UID,
        )
        store_calls = []

        async def fake_stow_store(dest, instance):
            store_calls.append(instance)
            return _stow_result(instance), False

        url = reverse("stow_rs-series_with_study_uid", args=[server.ae_title, STUDY_UID])
        with _patch_parse([ds]), patch("adit.dicom_web.views.stow_store", new=fake_stow_store):
            response = await AsyncClient().post(
                url, data=b"body", content_type=STOW_CONTENT_TYPE, headers=_auth(token)
            )

        assert response.status_code == 200
        # The matching instance must be stored.
        assert len(store_calls) == 1
        result = response.json()
        assert "00081199" in result  # ReferencedSOPSequence

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_none_dataset_is_skipped(self):
        """parse_request_in_chunks may yield None for boundary noise; the loop
        must skip it (views.py:524-525)."""
        token, server = await setup_user_and_server(source=False, destination=True)
        ds = make_image(
            SOPInstanceUID=IMAGE_UID,
            SOPClassUID=SOP_CLASS_UID,
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
        )
        store_calls = []

        async def fake_stow_store(dest, instance):
            store_calls.append(instance)
            return _stow_result(instance), False

        url = reverse("stow_rs-series", args=[server.ae_title])
        # Yield a None followed by a real dataset.
        with (
            _patch_parse([None, ds]),
            patch("adit.dicom_web.views.stow_store", new=fake_stow_store),
        ):
            response = await AsyncClient().post(
                url, data=b"body", content_type=STOW_CONTENT_TYPE, headers=_auth(token)
            )

        assert response.status_code == 200
        # Only the real dataset reaches stow_store; the None is skipped.
        assert len(store_calls) == 1
