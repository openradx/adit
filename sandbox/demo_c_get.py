from pydicom.dataset import Dataset
from pynetdicom import AE, evt, build_role, debug_logger

from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet,
    EncapsulatedSTLStorage,
    EncapsulatedOBJStorage,
    EncapsulatedMTLStorage,
)

from pynetdicom import (
    StoragePresentationContexts,
)

debug_logger()


def handle_store(event):
    """Handle a C-STORE request event."""
    ds = event.dataset
    ds.file_meta = event.file_meta

    ds.save_as(ds.SOPInstanceUID, write_like_original=False)

    return 0x0000  # success


def main():
    handlers = [(evt.EVT_C_STORE, handle_store)]

    ae = AE(ae_title="ADIT1DEV")

    # See https://github.com/pydicom/pynetdicom/issues/459
    # and https://github.com/pydicom/pynetdicom/blob/master/pynetdicom/apps/getscu/getscu.py#L222

    # Exclude these SOP Classes
    _exclusion = [
        EncapsulatedSTLStorage,
        EncapsulatedOBJStorage,
        EncapsulatedMTLStorage,
    ]
    store_contexts = [
        cx for cx in StoragePresentationContexts if cx.abstract_syntax not in _exclusion
    ]

    ext_neg = []
    ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
    for cx in store_contexts:
        ae.add_requested_context(cx.abstract_syntax)
        # Add SCP/SCU Role Selection Negotiation to the extended negotiation
        # We want to act as a Storage SCP
        ext_neg.append(build_role(cx.abstract_syntax, scp_role=True))

    ds = Dataset()
    ds.QueryRetrieveLevel = "SERIES"
    ds.PatientID = "101"
    ds.StudyInstanceUID = "1.2.840.113845.11.1000000001951524609.20200705182951.2689481"
    # ds.SeriesInstanceUID = "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005512"
    ds.SeriesInstanceUID = (
        "1.2.840.113845.11.2000000001951524609.20200705191841.1919177"
    )

    # Associate with Orthanc1
    assoc = ae.associate("127.0.0.1", 7501, ext_neg=ext_neg, evt_handlers=handlers)

    if assoc.is_established:
        # Use the C-GET service to send the identifier
        responses = assoc.send_c_get(ds, PatientRootQueryRetrieveInformationModelGet)
        for (status, _) in responses:
            if status:
                print(f"C-GET query status: 0x{status.Status:04x}")
            else:
                print("Connection timed out, was aborted or received invalid response")

        assoc.release()
    else:
        print("Association rejected, aborted or never connected")


if __name__ == "__main__":
    main()
