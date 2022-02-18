from pydicom.dataset import Dataset
from pynetdicom import AE, evt, build_role, debug_logger

# pylint: disable=no-name-in-module
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet,
    CTImageStorage,
)

debug_logger()


def handle_store(event):
    """Handle a C-STORE request event."""
    ds = event.dataset
    ds.file_meta = event.file_meta

    ds.save_as(ds.SOPInstanceUID, write_like_original=False)

    return 0x0000  # success


handlers = [(evt.EVT_C_STORE, handle_store)]

ae = AE(ae_title="ADIT1DEV")

ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
ae.add_requested_context(CTImageStorage)

role = build_role(CTImageStorage, scp_role=True)

ds = Dataset()
ds.QueryRetrieveLevel = "SERIES"
ds.PatientID = "101"
ds.StudyInstanceUID = "1.2.840.113845.11.1000000001951524609.20200705182951.2689481"
ds.SeriesInstanceUID = "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005512"
# ds.SeriesInstanceUID = "1.2.840.113845.11.2000000001951524609.20200705191841.1919177"

# Associate with Orthanc1
assoc = ae.associate("127.0.0.1", 7501, ext_neg=[role], evt_handlers=handlers)

if assoc.is_established:
    # Use the C-GET service to send the identifier
    responses = assoc.send_c_get(ds, PatientRootQueryRetrieveInformationModelGet)
    for (status, identifier) in responses:
        if status:
            print("C-GET query status: 0x{0:04x}".format(status.Status))
        else:
            print("Connection timed out, was aborted or received invalid response")

    assoc.release()
else:
    print("Association rejected, aborted or never connected")
