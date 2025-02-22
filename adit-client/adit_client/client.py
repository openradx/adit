import importlib.metadata
from typing import Iterator

from dicognito.anonymizer import Anonymizer
from dicognito.value_keeper import ValueKeeper
from dicomweb_client import DICOMwebClient, session_utils
from pydicom import Dataset

DEFAULT_SKIP_ELEMENTS_ANONYMIZATION = [
    "AcquisitionDate",
    "AcquisitionDateTime",
    "AcquisitionTime",
    "ContentDate",
    "ContentTime",
    "SeriesDate",
    "SeriesTime",
    "StudyDate",
    "StudyTime",
]


class AditClient:
    def __init__(
        self,
        server_url: str,
        auth_token: str,
        verify: str | bool = True,
        trial_protocol_id: str | None = None,
        trial_protocol_name: str | None = None,
        skip_elements_anonymization: list[str] | None = None,
    ) -> None:
        self.server_url = server_url
        self.auth_token = auth_token
        self.verify = verify
        self.trial_protocol_id = trial_protocol_id
        self.trial_protocol_name = trial_protocol_name
        self.__version__ = importlib.metadata.version("adit-client")

        if skip_elements_anonymization is None:
            self.skip_elements_anonymization = DEFAULT_SKIP_ELEMENTS_ANONYMIZATION
        else:
            self.skip_elements_anonymization = skip_elements_anonymization

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
        images = self._create_dicom_web_client(ae_title).retrieve_study(study_uid)

        anonymizer: Anonymizer | None = None
        if pseudonym is not None:
            anonymizer = self._setup_anonymizer()

        return [self._handle_dataset(image, anonymizer, pseudonym) for image in images]

    def iter_study(
        self, ae_title: str, study_uid: str, pseudonym: str | None = None
    ) -> Iterator[Dataset]:
        """Iterate over all instances of a study."""
        images = self._create_dicom_web_client(ae_title).iter_study(study_uid)

        anonymizer: Anonymizer | None = None
        if pseudonym is not None:
            anonymizer = self._setup_anonymizer()

        for image in images:
            yield self._handle_dataset(image, anonymizer, pseudonym)

    def retrieve_series(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        pseudonym: str | None = None,
    ) -> list[Dataset]:
        """Retrieve all instances of a series."""
        images = self._create_dicom_web_client(ae_title).retrieve_series(
            study_uid, series_instance_uid=series_uid
        )

        anonymizer: Anonymizer | None = None
        if pseudonym is not None:
            anonymizer = self._setup_anonymizer()

        return [self._handle_dataset(image, anonymizer, pseudonym) for image in images]

    def iter_series(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        pseudonym: str | None = None,
    ) -> Iterator[Dataset]:
        """Iterate over all instances of a series."""
        images = self._create_dicom_web_client(ae_title).iter_series(
            study_uid, series_instance_uid=series_uid
        )

        anonymizer: Anonymizer | None = None
        if pseudonym is not None:
            anonymizer = self._setup_anonymizer()

        for image in images:
            yield self._handle_dataset(image, anonymizer, pseudonym)

    def retrieve_image(
        self,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        image_uid: str,
        pseudonym: str | None = None,
    ) -> Dataset:
        """Retrieve an image."""
        image = self._create_dicom_web_client(ae_title).retrieve_instance(
            study_uid, series_uid, image_uid
        )

        anonymizer: Anonymizer | None = None
        if pseudonym is not None:
            anonymizer = self._setup_anonymizer()

        return self._handle_dataset(image, anonymizer, pseudonym)

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

    def _setup_anonymizer(self) -> Anonymizer:
        anonymizer = Anonymizer()
        for element in self.skip_elements_anonymization:
            anonymizer.add_element_handler(ValueKeeper(element))
        return anonymizer

    def _handle_dataset(
        self, ds: Dataset, anonymizer: Anonymizer | None, pseudonym: str | None
    ) -> Dataset:
        # Similar to what ADIT does in core/processors.py

        if self.trial_protocol_id is not None:
            ds.ClinicalTrialProtocolID = self.trial_protocol_id

        if self.trial_protocol_name is not None:
            ds.ClinicalTrialProtocolName = self.trial_protocol_name

        if pseudonym is not None:
            assert anonymizer is not None
            anonymizer.anonymize(ds)
            ds.PatientID = pseudonym
            ds.PatientName = pseudonym

        if pseudonym and self.trial_protocol_id:
            session_id = f"{ds.StudyDate}-{ds.StudyTime}"
            ds.PatientComments = (
                f"Project:{self.trial_protocol_id} Subject:{pseudonym} "
                f"Session:{pseudonym}_{session_id}"
            )

        return ds
