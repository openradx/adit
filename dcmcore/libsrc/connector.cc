#include "connector.h"
#include "iostream"
#include <dcmtk/dcmdata/dcdatset.h>
#include <dcmtk/dcmdata/dcdeftag.h>
#include <dcmtk/ofstd/oflist.h>

const int ASCE_TIMEOUT = 30;
const int OUTPUT_RESPONSE_LIMIT = 101;
const int DIMSE_TIMEOUT = 0;
const bool SECURE_CONNECTION = false;
const bool ABORT_ASSOCIATION = false;
const int REPEAT_COUNT = 1;
const int CANCEL_AFTER_RESPONSES = 0;

ConnectorError::ConnectorError(const char *message) { message_ = message; }

const char *ConnectorError::what() { return message_; }

Connector::Connector(Server server) { server_ = server; }

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

OFList<Patient> Connector::findPatients(const char *patientId,
                                        const char *patientName,
                                        const char *patientBirthDate) {
  FindSCU scu;
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
  scu.addPresentationContext(UID_VerificationSOPClass, ts);

  OFCondition result = scu.initNetwork();
  if (result.bad()) {
    OFString message = "Unable to init network: ";
    throw ConnectorError(message.append(result.text()).c_str());
  }

  result = scu.negotiateAssociation();
  if (result.bad()) {
    OFString message = "Unable to negotiate association: ";
    throw ConnectorError(message.append(result.text()).c_str());
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
    throw ConnectorError(
        "There is no uncompressed presentation context for Patient Root FIND.");
  }

  result = scu.sendFINDRequest(presId, &req, &findResponses);
  if (result.bad()) {
    OFString message = "Error during Patient Root Find: ";
    throw ConnectorError(message.append(result.text()).c_str());
  }

  OFList<Patient> patients;

  OFListIterator(QRResponse *) iterator = findResponses.begin();
  while (iterator != findResponses.end() && result.good()) {
    // be sure we are not in the last response which does not have a dataset
    if ((*iterator)->m_dataset != NULL) {
      DcmDataset *dataset = (*iterator)->m_dataset;
      Patient patient;
      // TODO: evaluate result (also in while condition)
      result =
          dataset->findAndGetOFStringArray(DCM_PatientID, patient.patientId);
      result = dataset->findAndGetOFStringArray(DCM_PatientName,
                                                patient.patientName);
      result = dataset->findAndGetOFStringArray(DCM_PatientBirthDate,
                                                patient.patientBirthDate);
      patients.push_back(patient);
    }
    iterator++;
  }

  if (result.bad()) {
    OFString message = "Unable to retrieve all patients: ";
    throw ConnectorError(message.append(result.text()).c_str());
  }

  while (!findResponses.empty()) {
    delete findResponses.front();
    findResponses.pop_front();
  }

  scu.closeAssociation(DCMSCU_RELEASE_ASSOCIATION);

  return patients;
}

// OFList<Study> Connector::findStudies(const char *patientId,
//                                      const char *patientName,
//                                      const char *patientBirthDate,
//                                      const char *studyInstanceUID,
//                                      const char *accessionNumber,
//                                      const char *studyDate,
//                                      const char *modalitiesInStudy) {
//   DcmDataset req;
//   req.putAndInsertOFStringArray(DCM_QueryRetrieveLevel, "STUDY");
//   req.putAndInsertOFStringArray(DCM_PatientID, patientId);
//   req.putAndInsertOFStringArray(DCM_PatientName, patientName);
//   req.putAndInsertOFStringArray(DCM_PatientBirthDate, patientBirthDate);
//   req.putAndInsertOFStringArray(DCM_StudyInstanceUID, studyInstanceUID);
//   req.putAndInsertOFStringArray(DCM_AccessionNumber, accessionNumber);
//   req.putAndInsertOFStringArray(DCM_StudyDate, studyDate);
//   req.putAndInsertOFStringArray(DCM_ModalitiesInStudy, "");

//   // TODO: filter studies by modality programmatically
// }