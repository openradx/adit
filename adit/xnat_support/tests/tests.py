from django.test import TestCase
from datetime import datetime
import os
from pathlib import Path
import requests

from pydicom import dcmread

from adit.core.models import DicomServer, DicomNode, DicomFolder

from adit.batch_query.models import BatchQueryJob, BatchQueryTask
from adit.batch_query.factories import BatchQueryJobFactory
from adit.batch_query.tasks import ProcessBatchQueryTask

from adit.batch_transfer.models import BatchTransferJob, BatchTransferTask
from adit.batch_transfer.factories import BatchTransferJobFactory
from adit.batch_transfer.tasks import ProcessBatchTransferTask

from adit.rest_api.tests.tests import get_test_result

TOKEN = "555240a9fc96541d5109fd4a8447c60da10f669f"
BASE_URL = "http://localhost:8000/rest_api/"

XNAT_TEST_SERVER = DicomServer(
    ae_title="xnat",
    host="xnat-web",
    port=8104,
    store_scp_support=True,
    xnat_server=True,
    xnat_rest_source=True,
    xnat_root_url="http://localhost:80/",
    xnat_username="admin",
    xnat_password="admin",
)

XNAT_TEST_NODE = DicomNode(
    name="xnat_test_server",
    node_type="SV",
    source_active=True,
    destination_active=True,
    dicomserver=XNAT_TEST_SERVER,
)

DEST_TEST_FOLDER = DicomFolder(
    path="adit/xnat_support/tests/files",
)

DEST_TEST_NODE = DicomNode(
    name="test_folder",
    node_type="FO",
    source_active=False,
    destination_active=True,
    dicomfolder=DEST_TEST_FOLDER,
)

TEST_INSTANCE = {
    "xnat_project_id": "TP2",
    "study_uid": "1.2.840.113845.11.1000000001951524609.20200705182951.2689481", 
    "patient_id": "1001",
    "study_date_start": datetime.strptime("03062019", "%d%m%Y"),
    "study_date_end": datetime.strptime("05062019", "%d%m%Y"),
    "modalities": ["CT"],
    "NumberOfStudyRelatedInstances":11,
}


class BatchQueryTaskTestCase(TestCase):
    def test_batch_query_from_xnat(self):
        job: BatchQueryJob = BatchQueryJobFactory()
        job.source = XNAT_TEST_NODE
        job.xnat_project_id = TEST_INSTANCE["xnat_project_id"]
        job.urgent = True

        task = BatchQueryTask(
            job=job,
            task_id=1,
            patient_id=TEST_INSTANCE["patient_id"],
            study_date_start=TEST_INSTANCE["study_date_start"],
            study_date_end=TEST_INSTANCE["study_date_end"],
            modalities=TEST_INSTANCE["modalities"],
        )

        Processor = ProcessBatchQueryTask()
        Processor.handle_dicom_task(task)
        while task.status in ["PE", "IP", "CI"]:
            task.refresh_from_db()

        results = job.results.get()

        # test that correct study is retrieved
        self.assertEqual(
            TEST_INSTANCE["study_uid"], results.study_uid
        )

        # test image count reconstruction
        self.assertEqual(
            TEST_INSTANCE["NumberOfStudyRelatedInstances"], results.image_count
        )
    
    def test_date_range(self):
        job: BatchQueryJob = BatchQueryJobFactory()
        job.source = XNAT_TEST_NODE
        job.xnat_project_id = TEST_INSTANCE["xnat_project_id"]
        job.urgent = True

        task = BatchQueryTask(
            job=job,
            task_id=1,
            patient_id=TEST_INSTANCE["patient_id"],
            study_date_start=datetime.now(),
            study_date_end=datetime.now(),
            modalities=TEST_INSTANCE["modalities"],
        )

        Processor = ProcessBatchQueryTask()
        Processor.handle_dicom_task(task)
        while task.status in ["PE", "IP", "CI"]:
            task.refresh_from_db()

        self.assertEqual(task.status, "WA")


class DicomWebXnatTestCase(TestCase):
    def test_qido_from_adit_xnat(self):
        _, test_study_uid = get_test_result()
        response = requests.get(
            BASE_URL
            + "XNAT"
            + f"/qidors/studies/",
            headers={
                "Authorization": f"Token {TOKEN}",
            },
        )
        query_result = eval(response.text)
        result_study_uids = [
            eval(query_result[i])["0020000D"]["Value"][0] for i in range(len(query_result))
        ]
        self.assertTrue(test_study_uid in result_study_uids)
        

class BatchTransferTaskTestCase(TestCase):
    def test_batch_transfer_from_xnat(self):
        job: BatchTransferJob = BatchTransferJobFactory()
        job.source = XNAT_TEST_NODE
        job.destination = DEST_TEST_NODE
        job.xnat_source_project_id = TEST_INSTANCE["xnat_project_id"]
        job.urgent = True

        task = BatchTransferTask(
            job=job,
            task_id=1,
            patient_id=TEST_INSTANCE["patient_id"],
            study_uid=TEST_INSTANCE["study_uid"],
        )

        Processor = ProcessBatchTransferTask()
        Processor.handle_dicom_task(task)
        while task.status != "SU":
            task.refresh_from_db()

        path = Path(job.destination.dicomfolder.path)
        for subpath, subdirs, files in os.walk(path):
            for fname in files:
                fpath = os.path.join(subpath,fname)
                ds = dcmread(fpath)

                self.assertEqual(
                    TEST_INSTANCE["study_uid"], ds.StudyInstanceUID
                )

                self.assertEqual(
                    TEST_INSTANCE["patient_id"], ds.PatientID
                )





