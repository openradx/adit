from pydicom.dataset import Dataset

from pynetdicom import AE, evt, StoragePresentationContexts, debug_logger
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove
from pynetdicom.status import code_to_category, code_to_status, STATUS_FAILURE

# debug_logger()

print(STATUS_FAILURE)


def handle_store(event):
    print(event)
    return 0x0000


handlers = [(evt.EVT_C_STORE, handle_store)]

ae = AE(ae_title="ADIT")
ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
ae.supported_contexts = StoragePresentationContexts

scp = ae.start_server(("", 7900), block=False, evt_handlers=handlers)

# Create out identifier (query) dataset
ds = Dataset()
ds.QueryRetrieveLevel = "SERIES"
ds.PatientID = "10005"
ds.StudyInstanceUID = "1.2.840.113845.11.1000000001951524609.20200705150256.2689458"
ds.SeriesInstanceUID = "1.3.12.2.1107.5.2.18.41369.2020070515244568288101946.0.0.0"

assoc = ae.associate("127.0.0.1", 7501)

if assoc.is_established:
    responses = assoc.send_c_move(
        ds, "ADIT", PatientRootQueryRetrieveInformationModelMove
    )

    for (status, identifier) in responses:
        print(status)
        print("--")
        print(dir(status))
        print(status.to_json())
        print(status.Status)
        print(code_to_category(status.Status))
        print(code_to_status(status.Status))
        print(identifier)
        if status:
            print("C-MOVE query status: 0x{0:04x}".format(status.Status))
        else:
            print("Connection timed out, was aborted or received invalid response")
    assoc.release()
else:
    print("Association rejected, aborted or never connected")

scp.shutdown()
