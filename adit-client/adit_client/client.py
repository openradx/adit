import importlib.metadata
from io import BytesIO
from typing import Iterator

from dicomweb_client import DICOMwebClient, session_utils
from pydicom import Dataset
from requests_toolbelt.multipart.decoder import MultipartDecoder


class AditClient:
    def __init__(
        self,
        server_url: str,
        auth_token: str,
        verify: str | bool = True,
        trial_protocol_id: str | None = None,
        trial_protocol_name: str | None = None,
    ) -> None:
        self.server_url = server_url
        self.auth_token = auth_token
        self.verify = verify
        self.trial_protocol_id = trial_protocol_id
        self.trial_protocol_name = trial_protocol_name
        self.__version__ = importlib.metadata.version("adit-client")

    def search_for_studies(
        self, ae_title: str, query: dict[str, str] | None = None
    ) -> list[Dataset]:
        """Search for studies."""
        results = self._create_dicom_web_client(ae_title).search_for_studies(search_filters=query)
        return [Dataset.from_json(result) for result in results]

    def search_for_series(
        self, ae_title: str, study_uid: str, query: dict[str, str] | None = None
    ) -> list[Dataset]:
        """Search for series."""
        results = self._create_dicom_web_client(ae_title).search_for_series(
            study_uid, search_filters=query
        )
        return [Dataset.from_json(result) for result in results]

    def search_for_images(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        query: dict[str, str] | None = None,
    ) -> list[Dataset]:
        """Search for images."""
        results = self._create_dicom_web_client(ae_title).search_for_instances(
            study_uid, series_uid, search_filters=query
        )
        return [Dataset.from_json(result) for result in results]

    def retrieve_study(
        self, ae_title: str, study_uid: str, pseudonym: str | None = None
    ) -> list[Dataset]:
        """Retrieve all instances of a study."""
        additional_params = {}
        if pseudonym:
            additional_params["pseudonym"] = pseudonym
        if self.trial_protocol_id:
            additional_params["trial_protocol_id"] = self.trial_protocol_id
        if self.trial_protocol_name:
            additional_params["trial_protocol_name"] = self.trial_protocol_name

        return self._create_dicom_web_client(ae_title).retrieve_study(
            study_uid,
            additional_params=additional_params,
        )

    def retrieve_nifti_study(self, ae_title: str, study_uid: str) -> list[tuple[str, BytesIO]]:
        """
        Retrieve NIfTI files from the API for a specific study.

        Args:
            ae_title: The AE title of the server.
            study_uid: The study instance UID.

        Returns:
            A list of tuples containing the filename and file content.
        """
        # Construct the full URL
        url = f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/nifti"

        # Call the API
        response = self._create_dicom_web_client(ae_title)._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
        )

        # Create a decoder for the multipart response
        decoder = MultipartDecoder.from_response(response)
        files = []

        # Process each part in the multipart response
        for part in decoder.parts:
            content_disposition = part.headers.get(b"Content-Disposition", b"").decode("utf-8")  # type: ignore
            filename = self._extract_filename(content_disposition, len(files))
            files.append((filename, BytesIO(part.content)))

        return files

    def iter_nifti_study(self, ae_title: str, study_uid: str) -> Iterator[tuple[str, BytesIO]]:
        """
        Iterate over NIfTI files from the API for a specific study.

        Args:
            ae_title: The AE title of the server.
            study_uid: The study instance UID.

        Yields:
            Tuples containing the filename and file content.
        """
        # Construct the full URL
        url = f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/nifti"

        # Call the API
        response = self._create_dicom_web_client(ae_title)._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
        )

        # Create a decoder for the multipart response
        decoder = MultipartDecoder.from_response(response)

        # Process each part in the multipart response
        for i, part in enumerate(decoder.parts):
            content_disposition = part.headers.get(b"Content-Disposition", b"").decode("utf-8")  # type: ignore
            filename = self._extract_filename(content_disposition, i)
            yield (filename, BytesIO(part.content))

    def retrieve_nifti_series(
        self, ae_title: str, study_uid: str, series_uid: str
    ) -> list[tuple[str, BytesIO]]:
        """
        Retrieve NIfTI files from the API for a specific series.

        Args:
            ae_title: The AE title of the server.
            study_uid: The study instance UID.
            series_uid: The series instance UID.

        Returns:
            A list of tuples containing the filename and file content.
        """
        # Construct the full URL
        url = (
            f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/"
            f"series/{series_uid}/nifti"
        )

        # Call the API
        response = self._create_dicom_web_client(ae_title)._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
        )

        # Create a decoder for the multipart response
        decoder = MultipartDecoder.from_response(response)
        files = []

        # Process each part in the multipart response
        for part in decoder.parts:
            content_disposition = part.headers.get(b"Content-Disposition", b"").decode("utf-8")  # type: ignore
            filename = self._extract_filename(content_disposition, len(files))
            files.append((filename, BytesIO(part.content)))

        return files

    def iter_nifti_series(
        self, ae_title: str, study_uid: str, series_uid: str
    ) -> Iterator[tuple[str, BytesIO]]:
        """
        Iterate over NIfTI files from the API for a specific series.

        Args:
            ae_title: The AE title of the server.
            study_uid: The study instance UID.
            series_uid: The series instance UID.

        Yields:
            Tuples containing the filename and file content.
        """
        # Construct the full URL
        url = (
            f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/"
            f"series/{series_uid}/nifti"
        )

        # Call the API
        response = self._create_dicom_web_client(ae_title)._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
        )

        # Create a decoder for the multipart response
        decoder = MultipartDecoder.from_response(response)

        # Process each part in the multipart response
        for i, part in enumerate(decoder.parts):
            content_disposition = part.headers.get(b"Content-Disposition", b"").decode("utf-8")  # type: ignore
            filename = self._extract_filename(content_disposition, i)
            yield (filename, BytesIO(part.content))

    def retrieve_nifti_image(
        self, ae_title: str, study_uid: str, series_uid: str, image_uid: str
    ) -> list[tuple[str, BytesIO]]:
        """
        Retrieve NIfTI files from the API for a specific image.

        Args:
            ae_title: The AE title of the server.
            study_uid: The study instance UID.
            series_uid: The series instance UID.
            image_uid: The SOP instance UID.

        Returns:
            A list of tuples containing the filename and file content.
        """
        # Construct the full URL
        url = (
            f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/"
            f"series/{series_uid}/instances/{image_uid}/nifti"
        )

        # Call the API
        response = self._create_dicom_web_client(ae_title)._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
        )

        # Create a decoder for the multipart response
        decoder = MultipartDecoder.from_response(response)
        files = []

        # Process each part in the multipart response
        for part in decoder.parts:
            content_disposition = part.headers.get(b"Content-Disposition", b"").decode("utf-8")  # type: ignore
            filename = self._extract_filename(content_disposition, len(files))
            files.append((filename, BytesIO(part.content)))

        return files

    def _extract_filename(self, content_disposition: str, default_index: int) -> str:
        """
        Extract filename from Content-Disposition header.

        Args:
            content_disposition: The Content-Disposition header value
            default_index: Index to use for default filename if none found

        Returns:
            The extracted filename

        Raises:
            ValueError: If no filename can be extracted from the Content-Disposition header
        """
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[1].strip('"')
            return filename

        raise ValueError(
            f"Could not extract filename from Content-Disposition header: {content_disposition}"
        )

    def retrieve_study_metadata(
        self, ae_title: str, study_uid: str, pseudonym: str | None = None
    ) -> list[dict[str, dict]]:
        """Retrieve the metadata for all instances of a study."""
        additional_params = {}
        if pseudonym:
            additional_params["pseudonym"] = pseudonym
        if self.trial_protocol_id:
            additional_params["trial_protocol_id"] = self.trial_protocol_id
        if self.trial_protocol_name:
            additional_params["trial_protocol_name"] = self.trial_protocol_name

        return self._create_dicom_web_client(ae_title).retrieve_study_metadata(
            study_uid, additional_params=additional_params
        )

    def iter_study(
        self, ae_title: str, study_uid: str, pseudonym: str | None = None
    ) -> Iterator[Dataset]:
        """Iterate over all instances of a study."""
        for image in self._create_dicom_web_client(ae_title).iter_study(study_uid):
            yield image

    def retrieve_series(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        pseudonym: str | None = None,
    ) -> list[Dataset]:
        """Retrieve all instances of a series."""
        additional_params = {}
        if pseudonym:
            additional_params["pseudonym"] = pseudonym
        if self.trial_protocol_id:
            additional_params["trial_protocol_id"] = self.trial_protocol_id
        if self.trial_protocol_name:
            additional_params["trial_protocol_name"] = self.trial_protocol_name

        return self._create_dicom_web_client(ae_title).retrieve_series(
            study_uid, series_instance_uid=series_uid, additional_params=additional_params
        )

    def retrieve_series_metadata(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        pseudonym: str | None = None,
    ) -> list[dict[str, dict]]:
        """Retrieve the metadata for all instances of a series."""
        additional_params = {}
        if pseudonym:
            additional_params["pseudonym"] = pseudonym
        if self.trial_protocol_id:
            additional_params["trial_protocol_id"] = self.trial_protocol_id
        if self.trial_protocol_name:
            additional_params["trial_protocol_name"] = self.trial_protocol_name

        return self._create_dicom_web_client(ae_title).retrieve_series_metadata(
            study_uid, series_instance_uid=series_uid, additional_params=additional_params
        )

    def iter_series(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        pseudonym: str | None = None,
    ) -> Iterator[Dataset]:
        """Iterate over all instances of a series."""
        for image in self._create_dicom_web_client(ae_title).iter_series(
            study_uid, series_instance_uid=series_uid
        ):
            yield image

    def retrieve_image(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        image_uid: str,
        pseudonym: str | None = None,
    ) -> Dataset:
        """Retrieve an image."""
        additional_params = {}
        if pseudonym:
            additional_params["pseudonym"] = pseudonym
        if self.trial_protocol_id:
            additional_params["trial_protocol_id"] = self.trial_protocol_id
        if self.trial_protocol_name:
            additional_params["trial_protocol_name"] = self.trial_protocol_name

        return self._create_dicom_web_client(ae_title).retrieve_instance(
            study_uid, series_uid, image_uid, additional_params=additional_params
        )

    def retrieve_image_metadata(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        image_uid: str,
        pseudonym: str | None = None,
    ) -> dict[str, dict]:
        """Retrieve the metadata for an image."""
        additional_params = {}
        if pseudonym:
            additional_params["pseudonym"] = pseudonym
        if self.trial_protocol_id:
            additional_params["trial_protocol_id"] = self.trial_protocol_id
        if self.trial_protocol_name:
            additional_params["trial_protocol_name"] = self.trial_protocol_name

        return self._create_dicom_web_client(ae_title).retrieve_instance_metadata(
            study_uid, series_uid, image_uid, additional_params=additional_params
        )

    def store_images(self, ae_title: str, images: list[Dataset]) -> Dataset:
        """Store images."""
        return self._create_dicom_web_client(ae_title).store_instances(images)

    def _create_dicom_web_client(self, ae_title: str) -> DICOMwebClient:
        session = session_utils.create_session()

        if isinstance(self.verify, bool):
            session.verify = self.verify
        else:
            session = session_utils.add_certs_to_session(session=session, ca_bundle=self.verify)

        return DICOMwebClient(
            session=session,
            url=f"{self.server_url}/api/dicom-web/{ae_title}",
            qido_url_prefix="qidors",
            wado_url_prefix="wadors",
            stow_url_prefix="stowrs",
            headers={
                "Authorization": f"Token {self.auth_token}",
                "User-Agent": f"python-adit_client/{self.__version__}",
            },
        )
