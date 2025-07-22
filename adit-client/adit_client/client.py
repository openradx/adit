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
            filename = self._extract_filename(content_disposition)
            files.append((filename, BytesIO(part.content)))

        return files

    def _extract_filename(self, content_disposition: str) -> str:
        """Extract filename from Content-Disposition header."""
        if not content_disposition or "filename=" not in content_disposition:
            return "unknown.nii.gz"

        filename = content_disposition.split("filename=")[1].strip('"')
        return filename

    def _iter_multipart_response(self, response) -> Iterator[tuple[str, BytesIO]]:
        """
        Process a multipart response in chunks, yielding files as they are received.

        Args:
            response: The streaming response object from requests.

        Yields:
            Tuples containing the filename and file content as they are received.
        """
        # Get content type to determine boundary
        content_type = response.headers.get("Content-Type", "")
        if not content_type:
            raise ValueError("Response does not have a Content-Type header")

        # Extract the boundary from the content type
        try:
            boundary = content_type.split("boundary=")[1].strip()
        except (IndexError, AttributeError):
            raise ValueError(f"Invalid Content-Type header: {content_type}")

        boundary_bytes = f"--{boundary}".encode()
        end_boundary_bytes = f"--{boundary}--".encode()

        buffer = bytearray()

        # Process the response in chunks - 512KB chunk size
        for chunk in response.iter_content(chunk_size=524288):  # 512 * 1024 = 512KB
            if chunk:
                buffer.extend(chunk)

                # Process any complete parts in the buffer
                while True:
                    # Check for part boundary
                    boundary_index = buffer.find(boundary_bytes)

                    if boundary_index >= 0:
                        # Extract the part data (excluding the boundary)
                        part_data = bytes(buffer[:boundary_index])

                        # Remove the processed part and boundary from buffer
                        buffer = buffer[boundary_index + len(boundary_bytes) :]

                        # Only process parts that have Content-Disposition
                        #  (skip the first empty one)
                        if part_data and b"Content-Disposition" in part_data:
                            # Split headers and content
                            headers_end = part_data.find(b"\r\n\r\n")
                            if headers_end > 0:
                                headers_text = part_data[:headers_end].decode("utf-8")
                                content = part_data[headers_end + 4 :]

                                # Extract filename from Content-Disposition header
                                filename = None
                                for line in headers_text.split("\r\n"):
                                    if (
                                        line.startswith("Content-Disposition:")
                                        and "filename=" in line
                                    ):
                                        filename = line.split("filename=")[1].strip('"')
                                        break

                                if filename:
                                    # Yield the file immediately as we process it
                                    yield (filename, BytesIO(content))
                    else:
                        # If no complete part found, check for end boundary
                        if end_boundary_bytes in buffer:
                            # We've reached the end of the response
                            break
                        # No complete part and no end boundary, wait for more data
                        break

        # Process any remaining data in the buffer
        remaining_data = bytes(buffer)
        if remaining_data and b"Content-Disposition" in remaining_data:
            headers_end = remaining_data.find(b"\r\n\r\n")
            if headers_end > 0:
                headers_text = remaining_data[:headers_end].decode("utf-8")
                content = remaining_data[headers_end + 4 :]

                filename = None
                for line in headers_text.split("\r\n"):
                    if line.startswith("Content-Disposition:") and "filename=" in line:
                        filename = line.split("filename=")[1].strip('"')
                        break

                if filename:
                    yield (filename, BytesIO(content))

    def iter_nifti_study(self, ae_title: str, study_uid: str) -> Iterator[tuple[str, BytesIO]]:
        """
        Iterate over NIfTI files from the API for a specific study.

        Args:
            ae_title: The AE title of the server.
            study_uid: The study instance UID.

        Yields:
            Tuples containing the filename and file content as they are received from the API.
        """
        # Construct the full URL
        url = f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/nifti"

        # Create client and set up the streaming request
        dicomweb_client = self._create_dicom_web_client(ae_title)
        response = dicomweb_client._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
            stream=True,
        )

        yield from self._iter_multipart_response(response)

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
            filename = self._extract_filename(content_disposition)
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
            Tuples containing the filename and file content as they are received from the API.
        """
        # Construct the full URL
        url = (
            f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/"
            f"series/{series_uid}/nifti"
        )

        # Create client and set up the streaming request
        dicomweb_client = self._create_dicom_web_client(ae_title)
        response = dicomweb_client._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
            stream=True,
        )

        yield from self._iter_multipart_response(response)

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
            filename = self._extract_filename(content_disposition)
            files.append((filename, BytesIO(part.content)))

        return files

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
