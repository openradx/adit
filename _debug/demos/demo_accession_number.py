from pathlib import Path
import sys, os
adit_root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(adit_root_path.as_posix())

from main.utils.dicom_handler import DicomHandler

config = DicomHandler.Config(
    username='Vader',
    client_ae_title='ADIT',
    source_ae_title='ORTHANC1',
    source_ip='127.0.0.1',
    source_port=7501
)

handler = DicomHandler(config)

result = handler.find_study('0062115936')
print(result)