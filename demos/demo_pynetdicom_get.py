from functools import partial
from pydicom.dataset import Dataset
from pynetdicom import (
    AE,
    evt,
    build_role,
    debug_logger,
)
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet,
    CTImageStorage,
)

debug_logger()


def _handle_store(foo, event):
    print(foo)
    print(event)
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    foo["x"] += 1
    event.assoc.abort()

    return 0xA702


ae = AE(ae_title="ADIT1")

ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
ae.add_requested_context(CTImageStorage)
role = build_role(CTImageStorage, scp_role=True, scu_role=True)

ds = Dataset()
ds.QueryRetrieveLevel = "STUDY"
ds.PatientID = "10001"
ds.StudyInstanceUID = "1.2.840.113845.11.1000000001951524609.20200705182951.2689481"
# ds.SeriesInstanceUID = "1.3.12.2.1107.5.1.4.66002.30000020070513455668000000609"

assoc = ae.associate("127.0.0.1", 7501, ext_neg=[role])

if assoc.is_established:
    errors = {"x": 0}
    handle_store = partial(_handle_store, errors)
    assoc.bind(evt.EVT_C_STORE, handle_store)

    responses = assoc.send_c_get(
        ds,
        PatientRootQueryRetrieveInformationModelGet,
        msg_id=9999,
    )

    for (status, identifier) in responses:
        print(status)
        if status:
            print("C-GET query status: 0x{0:04x}".format(status.Status))
        else:
            print("Connection timed out, was aborted or received invalid response")

    assoc.unbind(evt.EVT_C_STORE, _handle_store)
    print(errors)
    assoc.release()
else:
    print("Association rejected, aborted or never connected")
