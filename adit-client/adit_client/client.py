import importlib.metadata
import os
from io import BytesIO
from typing import Iterator, Union

from dicomweb_client import DICOMwebClient, session_utils
from pydicom import Dataset


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

    def retrieve_nifti_study(self, ae_title: str, study_uid: str) -> list[tuple[str, BytesIO]]:
        """Retrieve NIfTI files for a study."""
        url = f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/nifti"
        dicomweb_client = self._create_dicom_web_client(ae_title)
        response = dicomweb_client._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
            stream=True,
        )
        return list(self._iter_multipart_response(response, stream=False))

    def iter_nifti_study(self, ae_title: str, study_uid: str) -> Iterator[tuple[str, BytesIO]]:
        """Iterate over NIfTI files for a study."""
        url = f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/nifti"
        dicomweb_client = self._create_dicom_web_client(ae_title)
        response = dicomweb_client._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
            stream=True,
        )
        yield from self._iter_multipart_response(response, stream=True)

    def retrieve_nifti_series(
        self, ae_title: str, study_uid: str, series_uid: str
    ) -> list[tuple[str, BytesIO]]:
        """Retrieve NIfTI files for a series."""
        url = (
            f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/"
            f"series/{series_uid}/nifti"
        )
        dicomweb_client = self._create_dicom_web_client(ae_title)
        response = dicomweb_client._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
            stream=True,
        )
        return list(self._iter_multipart_response(response, stream=False))

    def iter_nifti_series(
        self, ae_title: str, study_uid: str, series_uid: str
    ) -> Iterator[tuple[str, BytesIO]]:
        """Iterate over NIfTI files for a series."""
        url = (
            f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/"
            f"series/{series_uid}/nifti"
        )
        dicomweb_client = self._create_dicom_web_client(ae_title)
        response = dicomweb_client._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
            stream=True,
        )
        yield from self._iter_multipart_response(response, stream=True)

    def retrieve_nifti_image(
        self, ae_title: str, study_uid: str, series_uid: str, image_uid: str
    ) -> list[tuple[str, BytesIO]]:
        """Retrieve NIfTI files for a single image."""
        url = (
            f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/"
            f"series/{series_uid}/instances/{image_uid}/nifti"
        )
        dicomweb_client = self._create_dicom_web_client(ae_title)
        response = dicomweb_client._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
            stream=True,
        )
        return list(self._iter_multipart_response(response, stream=False))

    def iter_nifti_image(
        self, ae_title: str, study_uid: str, series_uid: str, image_uid: str
    ) -> Iterator[tuple[str, BytesIO]]:
        """Iterate over NIfTI files for a single image."""
        url = (
            f"{self.server_url}/api/dicom-web/{ae_title}/wadors/studies/{study_uid}/"
            f"series/{series_uid}/instances/{image_uid}/nifti"
        )
        dicomweb_client = self._create_dicom_web_client(ae_title)
        response = dicomweb_client._http_get(
            url,
            headers={"Accept": "multipart/related; type=application/octet-stream"},
            stream=True,
        )
        yield from self._iter_multipart_response(response, stream=True)

    def _extract_filename(self, content_disposition: str | None) -> str:
        """Extract filename from Content-Disposition header."""
        if not content_disposition or "filename=" not in content_disposition:
            raise ValueError("No filename found in Content-Disposition header")
        filename = content_disposition.split("filename=")[1].strip('"')
        return os.path.basename(filename)

    def _extract_part_content_with_headers(self, part: bytes) -> Union[bytes, None]:
        """Extract content from a multipart part, keeping headers intact.

        Used to patch DICOMwebClient's _extract_part_content to allow access
        to per-part headers (especially Content-Disposition for filenames).
        """
        if part in (b"", b"--", b"\r\n") or part.startswith(b"--\r\n"):
            return None
        return part

    def _iter_multipart_response(self, response, stream=False) -> Iterator[tuple[str, BytesIO]]:
        """Parse a multipart response, yielding (filename, content) tuples."""
        dicomweb_client = self._create_dicom_web_client("")
        original_extract_method = dicomweb_client._extract_part_content

        try:
            dicomweb_client._extract_part_content = self._extract_part_content_with_headers

            for part in dicomweb_client._decode_multipart_message(response, stream=stream):
                headers = {}
                content = part

                idx = part.find(b"\r\n\r\n")
                if idx > -1:
                    headers_bytes = part[:idx]
                    content = part[idx + 4 :]

                    for header_line in headers_bytes.split(b"\r\n"):
                        if header_line and b":" in header_line:
                            name, value = header_line.split(b":", 1)
                            headers[name.decode("utf-8").strip()] = value.decode("utf-8").strip()

                content_disposition = headers.get("Content-Disposition")
                if content_disposition:
                    filename = self._extract_filename(content_disposition)
                else:
                    for header, value in response.headers.items():
                        if header.lower() == "content-disposition":
                            filename = self._extract_filename(value)
                            break
                    else:
                        raise ValueError("No Content-Disposition header found in response")

                yield (filename, BytesIO(content))
        finally:
            dicomweb_client._extract_part_content = original_extract_method

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
