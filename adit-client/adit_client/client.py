from dicomweb_client import DICOMwebClient
from pydicom import Dataset


class AditClient:
    def __init__(self, server_url: str, auth_token: str) -> None:
        self.server_url = server_url
        self.auth_token = auth_token

    def search_for_studies(self, ae_title: str, filters: dict[str, str]) -> list[Dataset]:
        results = self._create_dicom_web_client(ae_title).search_for_studies(search_filters=filters)
        return [Dataset.from_json(result) for result in results]

    def search_for_series(
        self, ae_title: str, study_instance_uid: str, filters: dict[str, str]
    ) -> list[Dataset]:
        results = self._create_dicom_web_client(ae_title).search_for_series(
            study_instance_uid, search_filters=filters
        )
        return [Dataset.from_json(result) for result in results]

    def retrieve_study(self, ae_title: str, study_instance_uid: str) -> list[Dataset]:
        if not study_instance_uid:
            raise ValueError("Study instance UID must be provided to retrieve study.")

        results = self._create_dicom_web_client(ae_title).retrieve_study(study_instance_uid)
        return [Dataset.from_json(result) for result in results]

    def retrieve_series(
        self,
        ae_title: str,
        study_instance_uid: str,
        series_instance_uid: str,
    ) -> list[Dataset]:
        if not study_instance_uid:
            raise ValueError("Study instance UID must be provided to retrieve series.")

        if not series_instance_uid:
            raise ValueError("Series instance UID must be provided to retrieve series.")

        results = self._create_dicom_web_client(ae_title).retrieve_series(
            study_instance_uid, series_instance_uid=series_instance_uid
        )
        return [Dataset.from_json(result) for result in results]

    def store_instances(self, ae_title: str, instances: list[Dataset]) -> None:
        self._create_dicom_web_client(ae_title).store_instances(instances)

    def _create_dicom_web_client(self, ae_title: str) -> DICOMwebClient:
        return DICOMwebClient(
            url=f"{self.server_url}/dicom-web/{ae_title}",
            qido_url_prefix="qidors",
            wado_url_prefix="wadors",
            stow_url_prefix="stowrs",
            headers={"Authorization": self.auth_token},
        )
