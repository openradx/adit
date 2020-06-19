import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from dicom_operations import Config, DicomStore # pylint: disable-msg=import-error

config = Config(
    "W999999",
    "192.168.1.1",
    104,
    "SNYGO"
)
store = DicomStore(config)

results = store.send_c_store('V:\\ext02\\THOR-SchlampKai\\DICOM')
print(results)
