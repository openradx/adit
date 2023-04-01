#include "dcmtk/dcmdata/dcdatset.h"
#include "dcmtk/dcmnet/dfindscu.h"

class FindCollector : public DcmFindSCUCallback {
public:
  void callback(T_DIMSE_C_FindRQ *request, int responseCount,
                T_DIMSE_C_FindRSP *rsp, DcmDataset *rspMessage);

  OFList<DcmDataset *> getResults();

private:
  OFList<DcmDataset *> results_;
};