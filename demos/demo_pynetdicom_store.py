from pathlib import Path
from pydicom import dcmread
from pydicom.uid import JPEGLSLossless, ExplicitVRLittleEndian
from pynetdicom import (
    AE,
    debug_logger,
    build_role,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
)
from pynetdicom.sop_class import MRImageStorage
from pynetdicom import DEFAULT_TRANSFER_SYNTAXES, ALL_TRANSFER_SYNTAXES

debug_logger()

ae = AE(ae_title="ADIT")

# adit_root_path = Path(__file__).parent.parent.resolve()
# dicom_file_path = (
#     adit_root_path
#     / "samples"
#     / "dicoms"
#     / "10005"
#     / "20200705_152021_MR"
#     / "t2_tse_tra 5mm"
#     / "0000018B"
# )
# ds = dcmread(dicom_file_path)
ds = dcmread("1.3.12.2.1107.5.2.18.41369.2020070515244557481001938")

ae = AE(ae_title="ADIT")

# Test Case
# cx = list(QueryRetrievePresentationContexts)
# nr_pc = len(QueryRetrievePresentationContexts)
# cx += StoragePresentationContexts[: 128 - nr_pc]
# ae.requested_contexts = cx
# negotiation_items = []
# for context in StoragePresentationContexts[: 128 - nr_pc]:
#     role = build_role(context.abstract_syntax, scp_role=True)
#     negotiation_items.append(role)

# Test Case
ae.add_requested_context(MRImageStorage)
role = build_role(MRImageStorage, scp_role=True, scu_role=True)


# Test Case
# negotiation_items = None
# ae.add_requested_context(MRImageStorage)

assoc = ae.associate("127.0.0.1", 7502, ext_neg=[role])
if assoc.is_established:
    status = assoc.send_c_store(ds)

    if status:
        print("C-STORE request status: 0x{0:04x}".format(status.Status))
    else:
        print("Connection timed out, was aborted or received invalid response")

    assoc.release()
else:
    print("Association rejected, aborted or never connected")
