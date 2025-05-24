from unittest.mock import AsyncMock, patch

import pytest
from rest_framework.exceptions import ValidationError

from adit.dicom_web.views import (
    RetrieveAPIView,
    RetrieveImageAPIView,
    RetrieveImageMetadataAPIView,
    RetrieveSeriesAPIView,
    RetrieveSeriesMetadataAPIView,
    RetrieveStudyAPIView,
    RetrieveStudyMetadataAPIView,
)

INVALID_PSEUDONYMS = [
    "Test\\Pseudonym1",  # Invalid due to backslash
    "Test\u0001Pseudonym2",  # Invalid due to control character
    "Test*Pseudonym3",  # Invalid due to wildcard character
    "T" * 65,  # Invalid due to exceeding character limit
]


@pytest.mark.django_db
class TestRetrieveAPIView:
    @pytest.fixture
    def mock_request(self):
        """Fixture to create a mock request object."""
        return AsyncMock()

    @pytest.fixture
    def retrieve_view(self):
        """Fixture to create an instance of RetrieveAPIView."""
        return RetrieveAPIView()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_pseudonym", INVALID_PSEUDONYMS)
    @patch("adit.dicom_web.views.validate_pseudonym")
    async def test_invalid_pseudonym_raises_validation_error(
        self, mock_validate_pseudonym, retrieve_view, mock_request, invalid_pseudonym
    ):
        """Test that an invalid pseudonym raises a ValidationError."""
        mock_validate_pseudonym.side_effect = ValidationError("Invalid pseudonym")
        mock_request.query_params = {"pseudonym": invalid_pseudonym}

        with pytest.raises(ValidationError, match="Invalid pseudonym"):
            await retrieve_view.validate_pseudonym(mock_request.query_params["pseudonym"])

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_pseudonym", INVALID_PSEUDONYMS)
    @patch("adit.dicom_web.views.validate_pseudonym")
    @patch("adit.dicom_web.views.RetrieveAPIView._get_dicom_server")
    async def test_retrieve_study_with_invalid_pseudonym(
        self,
        mock_get_dicom_server,
        mock_validate_pseudonym,
        mock_request,
        invalid_pseudonym,
    ):
        """Test that the retrieve study view handles invalid pseudonyms gracefully."""
        mock_get_dicom_server.return_value = AsyncMock()

        mock_validate_pseudonym.side_effect = ValidationError("Invalid pseudonym")

        mock_request.GET = {"pseudonym": invalid_pseudonym}
        retrieve_study = RetrieveStudyAPIView()

        with pytest.raises(ValidationError, match="Invalid pseudonym"):
            await retrieve_study.get(mock_request, "AE_TITLE", "STUDY_UID")

        mock_validate_pseudonym.assert_called_once_with(invalid_pseudonym)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_pseudonym", INVALID_PSEUDONYMS)
    @patch("adit.dicom_web.views.validate_pseudonym")
    @patch("adit.dicom_web.views.RetrieveAPIView._get_dicom_server")
    async def test_retrieve_study_metadata_with_invalid_pseudonym(
        self,
        mock_get_dicom_server,
        mock_validate_pseudonym,
        mock_request,
        invalid_pseudonym,
    ):
        """Test that the retrieve study metadata view handles invalid pseudonyms gracefully."""
        mock_get_dicom_server.return_value = AsyncMock()

        mock_validate_pseudonym.side_effect = ValidationError("Invalid pseudonym")

        mock_request.GET = {"pseudonym": invalid_pseudonym}
        retrieve_study_metadata = RetrieveStudyMetadataAPIView()

        with pytest.raises(ValidationError, match="Invalid pseudonym"):
            await retrieve_study_metadata.get(mock_request, "AE_TITLE", "STUDY_UID")

        mock_validate_pseudonym.assert_called_once_with(invalid_pseudonym)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_pseudonym", INVALID_PSEUDONYMS)
    @patch("adit.dicom_web.views.validate_pseudonym")
    @patch("adit.dicom_web.views.RetrieveAPIView._get_dicom_server")
    async def test_retrieve_series_with_invalid_pseudonym(
        self,
        mock_get_dicom_server,
        mock_validate_pseudonym,
        mock_request,
        invalid_pseudonym,
    ):
        """Test that the retrieve series view handles invalid pseudonyms gracefully."""
        mock_get_dicom_server.return_value = AsyncMock()

        mock_validate_pseudonym.side_effect = ValidationError("Invalid pseudonym")

        mock_request.GET = {"pseudonym": invalid_pseudonym}
        retrieve_series = RetrieveSeriesAPIView()

        with pytest.raises(ValidationError, match="Invalid pseudonym"):
            await retrieve_series.get(mock_request, "AE_TITLE", "STUDY_UID", "SERIES_UID")

        mock_validate_pseudonym.assert_called_once_with(invalid_pseudonym)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_pseudonym", INVALID_PSEUDONYMS)
    @patch("adit.dicom_web.views.validate_pseudonym")
    @patch("adit.dicom_web.views.RetrieveAPIView._get_dicom_server")
    async def test_retrieve_series_metadata_with_invalid_pseudonym(
        self,
        mock_get_dicom_server,
        mock_validate_pseudonym,
        mock_request,
        invalid_pseudonym,
    ):
        """Test that the retrieve series metadata view handles invalid pseudonyms gracefully."""
        mock_get_dicom_server.return_value = AsyncMock()

        mock_validate_pseudonym.side_effect = ValidationError("Invalid pseudonym")

        mock_request.GET = {"pseudonym": invalid_pseudonym}
        retrieve_series_metadata = RetrieveSeriesMetadataAPIView()

        with pytest.raises(ValidationError, match="Invalid pseudonym"):
            await retrieve_series_metadata.get(mock_request, "AE_TITLE", "STUDY_UID", "SERIES_UID")

        mock_validate_pseudonym.assert_called_once_with(invalid_pseudonym)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_pseudonym", INVALID_PSEUDONYMS)
    @patch("adit.dicom_web.views.validate_pseudonym")
    @patch("adit.dicom_web.views.RetrieveAPIView._get_dicom_server")
    async def test_retrieve_image_with_invalid_pseudonym(
        self,
        mock_get_dicom_server,
        mock_validate_pseudonym,
        mock_request,
        invalid_pseudonym,
    ):
        """Test that the retrieve image view handles invalid pseudonyms gracefully."""
        mock_get_dicom_server.return_value = AsyncMock()

        mock_validate_pseudonym.side_effect = ValidationError("Invalid pseudonym")

        mock_request.GET = {"pseudonym": invalid_pseudonym}
        retrieve_image = RetrieveImageAPIView()

        with pytest.raises(ValidationError, match="Invalid pseudonym"):
            await retrieve_image.get(
                mock_request, "AE_TITLE", "STUDY_UID", "SERIES_UID", "IMAGE_UID"
            )

        mock_validate_pseudonym.assert_called_once_with(invalid_pseudonym)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_pseudonym", INVALID_PSEUDONYMS)
    @patch("adit.dicom_web.views.validate_pseudonym")
    @patch("adit.dicom_web.views.RetrieveAPIView._get_dicom_server")
    async def test_retrieve_image_metadata_with_invalid_pseudonym(
        self,
        mock_get_dicom_server,
        mock_validate_pseudonym,
        mock_request,
        invalid_pseudonym,
    ):
        """Test that the retrieve image view handles invalid pseudonyms gracefully."""
        mock_get_dicom_server.return_value = AsyncMock()

        mock_validate_pseudonym.side_effect = ValidationError("Invalid pseudonym")

        mock_request.GET = {"pseudonym": invalid_pseudonym}
        retrieve_image_metadata = RetrieveImageMetadataAPIView()

        with pytest.raises(ValidationError, match="Invalid pseudonym"):
            await retrieve_image_metadata.get(
                mock_request, "AE_TITLE", "STUDY_UID", "SERIES_UID", "IMAGE_UID"
            )

        mock_validate_pseudonym.assert_called_once_with(invalid_pseudonym)
