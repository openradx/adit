#include "dimconnector.h"
#include "dcmtk/config/osconfig.h"
#include "dcmtk/dcmdata/dctk.h"
#include <iostream>

using namespace std;

void DimConnector::findPatients() { cout << "in find patients"; }

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