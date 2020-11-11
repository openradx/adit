from pydicom.dataset import Dataset

from pynetdicom import (
    AE,
    debug_logger,
    build_context,
    build_role,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
)
from pynetdicom.sop_class import (  # pylint: disable=no-name-in-module
    PatientRootQueryRetrieveInformationModelFind,
)
from pynetdicom.status import code_to_category

# debug_logger()

ae = AE(ae_title="ADIT1")
# ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
cx = list(QueryRetrievePresentationContexts)
nr_pc = len(QueryRetrievePresentationContexts)
cx += StoragePresentationContexts[: 128 - nr_pc]
ae.requested_contexts = cx
negotiation_items = []
for context in StoragePresentationContexts[: 128 - nr_pc]:
    role = build_role(context.abstract_syntax, scp_role=True)
    negotiation_items.append(role)

ds = Dataset()
ds.QueryRetrieveLevel = "SERIES"
ds.PatientID = "10005"
ds.StudyInstanceUID = "1.2.840.113845.11.1000000001951524609.20200705150256.2689458"
ds.SeriesInstanceUID = "1.3.12.2.1107.5.2.18.41369.2020070515244568288101946.0.0.0"
ds.SeriesDescription = ""

assoc = ae.associate("127.0.0.1", 7501)
if assoc.is_established:
    for accepted_context in assoc.accepted_contexts:
        if (
            accepted_context.abstract_syntax
            == PatientRootQueryRetrieveInformationModelFind
        ):
            print(f"Accepted context ID: {accepted_context.context_id}")
    responses = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)
    for (status, identifier) in responses:
        if status:
            print("C-FIND query status: 0x{0:04X}".format(status.Status))
        else:
            print("Connection timed out, was aborted or received invalid response")

    assoc.release()
else:
    print("Association rejected, aborted or never connected")
