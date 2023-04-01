#include "findcollector.h"
#include "dcmtk/dcmdata/dcdatset.h"
#include "dcmtk/ofstd/oflist.h"

void FindCollector::callback(T_DIMSE_C_FindRQ *request, int responseCount,
                             T_DIMSE_C_FindRSP *rsp, DcmDataset *rspMessage) {
  results_.push_back(rspMessage);
}

OFList<DcmDataset *> FindCollector::getResults() { return results_; }