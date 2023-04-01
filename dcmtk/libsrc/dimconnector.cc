#include "dimconnector.h"
#include "dcmtk/config/osconfig.h"
#include "dcmtk/dcmdata/dctk.h"
#include "dcmtk/dcmnet/dfindscu.h"
#include "dcmtk/ofstd/ofcond.h"
#include "errors.h"
#include <iostream>

using namespace std;

const int ASCE_TIMEOUT = 30;
const int OUTPUT_RESPONSE_LIMIT = 101;
const int DIMSE_TIMEOUT = 0;
const bool SECURE_CONNECTION = false;
const bool ABORT_ASSOCIATION = false;
const int REPEAT_COUNT = 1;
const int CANCEL_AFTER_RESPONSES = 0;

DimConnector::DimConnector(const char *peer, unsigned int port,
                           const char *ourTitle, const char *peerTitle) {
  peer_ = peer;
  port_ = port;
  ourTitle_ = ourTitle;
  peerTitle_ = peerTitle;
}

void DimConnector::cFind() {}

void DimConnector::findPatients() {
  DcmFindSCU findscu;
  OFCondition cond = findscu.initializeNetwork(ASCE_TIMEOUT);
  if (cond.bad()) {
    throw ConnectorError(cond.text());
  }
  findscu.setOutputResponseLimit(OUTPUT_RESPONSE_LIMIT);
  // findscu.performQuery(peer_, port_, ourTitle_, peerTitle_,
  //                      UID_FINDModalityWorklistInformationModel, EXS_Unknown,
  //                      DIMSE_BLOCKING, DIMSE_TIMEOUT, ASC_DEFAULTMAXPDU,
  //                      SECURE_CONNECTION, ABORT_ASSOCIATION, REPEAT_COUNT,
  //                      FEM_none, CANCEL_AFTER_RESPONSES,
  //                      OFList<OFString> * overrideKeys)
}

void DimConnector::fetchStudy(int argc, char *argv[]) {
  /* iterate over all command line parameters */
  for (int i = 1; i < argc; i++) {
    /* load the specified DICOM file */
    DcmFileFormat dicomFile;
    if (dicomFile.loadFile(argv[i]).good()) {
      /* and dump its content to the console */
      cout << "DICOM file: " << argv[i] << OFendl;
      dicomFile.print(cout);
      cout << OFendl;
    }
  }
}