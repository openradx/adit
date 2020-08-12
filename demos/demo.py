import sys, os

root_folder = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)
sys.path.append(root_folder)

from batch_transfer.utils.batch_handler import BatchHandler

tmp_folder = os.path.join(root_folder, "_tmp")

config = BatchHandler.Config(
    username="kai",
    client_ae_title="ADIT",
    source_ae_title="OTRTHANC1",
    source_ip="127.0.0.1",
    source_port=7501,
    destination_folder="/tmp/adit_download_folder",
)

transferrer = BatchHandler(config)

from datetime import datetime

result = transferrer.find_patients("patient1", "", "")
result = transferrer.find_studies(
    patient_id="patient1", study_date=datetime(2008, 7, 23)
)
study_uid = "1.2.840.113619.2.176.3596.10293044.8073.1216822352.891"
result = transferrer.find_series("patient1", study_uid, ["MR"])
series_uid = "1.2.840.113619.2.176.3596.10293044.8073.1216822352.894"
# transferrer.download_series('patient1', study_uid, series_uid, tmp_folder)
# transferrer.download_study('patient1', study_uid, tmp_folder, create_series_folders=False)
transferrer.download_patient("patient1", tmp_folder)

