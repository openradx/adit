from pydicom.dataset import Dataset
from pynetdicom import (
    AE,
    evt,
    build_role,
    debug_logger,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
)
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet,
    MRImageStorage,
)

debug_logger()


def handle_store(event):
    data = event.dataset
    data.file_meta = event.file_meta
    print("----------------------------------------")
    print(data)
    print("----------------------------------------")
    data.save_as(data.SOPInstanceUID, write_like_original=False)
    return 0x0000


handlers = [(evt.EVT_C_STORE, handle_store)]

ae = AE(ae_title="ADIT")

# Test Case (works)
# cx = list(QueryRetrievePresentationContexts)
# nr_pc = len(QueryRetrievePresentationContexts)
# cx += StoragePresentationContexts[: 128 - nr_pc]
# ae.requested_contexts = cx
# negotiation_items = []
# for context in StoragePresentationContexts[: 128 - nr_pc]:
#     role = build_role(context.abstract_syntax, scp_role=True)
#     negotiation_items.append(role)

# Test Case (works)
ae.requested_contexts = QueryRetrievePresentationContexts
ae.add_requested_context(MRImageStorage)
role = build_role(MRImageStorage, scp_role=True, scu_role=True)

ds = Dataset()
ds.QueryRetrieveLevel = "SERIES"
ds.PatientID = "10005"
ds.StudyInstanceUID = "1.2.840.113845.11.1000000001951524609.20200705150256.2689458"
ds.SeriesInstanceUID = "1.3.12.2.1107.5.2.18.41369.2020070515244568288101946.0.0.0"
# ds.SOPIntanceUID = "1.3.12.2.1107.5.2.18.41369.2020070515244557481001938"

assoc = ae.associate("127.0.0.1", 7501, ext_neg=[role], evt_handlers=handlers)

if assoc.is_established:
    responses = assoc.send_c_get(ds, PatientRootQueryRetrieveInformationModelGet)
    for (status, identifier) in responses:
        if status:
            print("C-GET query status: 0x{0:04x}".format(status.Status))
        else:
            print("Connection timed out, was aborted or received invalid response")

    assoc.release()
else:
    print("Association rejected, aborted or never connected")
