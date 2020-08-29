from pydicom.dataset import Dataset

from pynetdicom import AE, debug_logger
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelFind
from pynetdicom.status import code_to_category

# debug_logger()

ae = AE(ae_title="ADIT")
ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)

ds = Dataset()
ds.QueryRetrieveLevel = "SERIES"
ds.PatientID = "10005"
ds.StudyInstanceUID = "1.2.840.113845.11.1000000001951524609.20200705150256.2689458"
ds.SeriesInstanceUID = "1.3.12.2.1107.5.2.18.41369.2020070515244568288101946.0.0.0"
ds.SeriesDescription = ""

assoc = ae.associate("127.0.0.1", 7501)
if assoc.is_established:
    responses = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)
    for (status, identifier) in responses:
        print(code_to_category(status.Status))
        if status:
            print("C-FIND query status: 0x{0:04X}".format(status.Status))
        else:
            print("Connection timed out, was aborted or received invalid response")

    assoc.release()
else:
    print("Association rejected, aborted or never connected")
