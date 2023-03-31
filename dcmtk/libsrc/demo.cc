#include "dcmtk/config/osconfig.h"
#include "dcmtk/dcmdata/dctk.h"
#include "dimconnector.h"
#include <iostream>

using namespace std;

int main(int argc, char *argv[]) {
  DimConnector dimConnector;
  dimConnector.findPatients();

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

  return 0;
}