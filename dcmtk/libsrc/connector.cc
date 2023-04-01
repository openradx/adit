#include "connector.h"
#include "iostream"

const int ASCE_TIMEOUT = 30;
const int OUTPUT_RESPONSE_LIMIT = 101;
const int DIMSE_TIMEOUT = 0;
const bool SECURE_CONNECTION = false;
const bool ABORT_ASSOCIATION = false;
const int REPEAT_COUNT = 1;
const int CANCEL_AFTER_RESPONSES = 0;

DcmConnectorError::DcmConnectorError(const char *message) {
  message_ = message;
}

const char *DcmConnectorError::what() { return message_; }

DcmConnector::DcmConnector(DcmServer server) { server_ = server; }

static Uint8 findUncompressedPC(const OFString &sopClass, DcmSCU &scu) {
  Uint8 pc;
  pc = scu.findPresentationContextID(sopClass,
                                     UID_LittleEndianExplicitTransferSyntax);
  if (pc == 0)
    pc = scu.findPresentationContextID(sopClass,
                                       UID_BigEndianExplicitTransferSyntax);
  if (pc == 0)
    pc = scu.findPresentationContextID(sopClass,
                                       UID_LittleEndianImplicitTransferSyntax);
  return pc;
}

void DcmConnector::findPatients(const char *patientId, const char *patientName,
                                const char *patientBirthDate) {
  DcmConnectorSCU scu;
  scu.setAETitle(server_.ourAETitle);
  scu.setPeerHostName(server_.peerHostName);
  scu.setPeerPort(server_.peerPort);
  scu.setPeerAETitle(server_.peerAETitle);

  OFList<OFString> ts;
  ts.push_back(UID_LittleEndianExplicitTransferSyntax);
  ts.push_back(UID_BigEndianExplicitTransferSyntax);
  ts.push_back(UID_LittleEndianImplicitTransferSyntax);
  scu.addPresentationContext(UID_FINDPatientRootQueryRetrieveInformationModel,
                             ts);

  OFCondition result = scu.initNetwork();
  if (result.bad()) {
    OFString message = "Unable to init network: ";
    throw DcmConnectorError(message.append(result.text()).c_str());
  }

  result = scu.negotiateAssociation();
  if (result.bad()) {
    OFString message = "Unable to negotiate association: ";
    throw DcmConnectorError(message.append(result.text()).c_str());
  }

  DcmDataset req;
  req.putAndInsertOFStringArray(DCM_QueryRetrieveLevel, "PATIENT");
  req.putAndInsertOFStringArray(DCM_PatientID, patientId);
  req.putAndInsertOFStringArray(DCM_PatientName, patientName);
  req.putAndInsertOFStringArray(DCM_PatientBirthDate, patientBirthDate);

  OFList<QRResponse *> findResponses;

  T_ASC_PresentationContextID presId =
      findUncompressedPC(UID_FINDPatientRootQueryRetrieveInformationModel, scu);
  if (presId == 0) {
    throw DcmConnectorError(
        "There is no uncompressed presentation context for Patient Root FIND.");
  }

  result = scu.sendFINDRequest(presId, &req, &findResponses);
  if (result.bad()) {
    OFString message = "Error during Patient Root Find: ";
    throw DcmConnectorError(message.append(result.text()).c_str());
  }

  OFListIterator(QRResponse *) iterator = findResponses.begin();
  while (iterator != findResponses.end() && result.good()) {
    // be sure we are not in the last response which does not have a dataset
    if ((*iterator)->m_dataset != NULL) {
      OFString patientId;
      result = (*iterator)->m_dataset->findAndGetOFStringArray(DCM_PatientID,
                                                               patientId);
      std::cout << "Found something. " << patientId << std::endl;
    }
    iterator++;
  }

  if (result.bad()) {
    OFString message = "Unable to retrieve all patients: ";
    throw DcmConnectorError(message.append(result.text()).c_str());
  }

  while (!findResponses.empty()) {
    delete findResponses.front();
    findResponses.pop_front();
  }

  scu.closeAssociation(DCMSCU_RELEASE_ASSOCIATION);
}
