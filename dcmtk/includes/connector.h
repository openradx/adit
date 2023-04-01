#include "dcmtk/dcmnet/scu.h"
#include <exception>

struct DcmServer {
  const char *ourAETitle;
  const char *peerHostName;
  unsigned int peerPort;
  const char *peerAETitle;
};

struct DcmPatient {
  const char *patientId;
  const char *patientName;
  const char *patientBirthDate;
};

// struct DcmSeries {
//   const char *seriesInstanceUID;
//   const char *seriesDescription;
//   const char *modality;
//   const char *seriesNumber;
// };

// struct DcmStudy {
//   DcmPatient patient;
//   const char *studyInstanceUID;
//   const char *studyDescription;
//   OFList<const char *> modalitiesInStudy;
//   OFList<DcmSeries> series;
// };

class DcmConnectorError : public std::exception {
public:
  DcmConnectorError(const char *message);
  const char *what();

private:
  const char *message_;
};

class DcmConnectorSCU : public DcmSCU {};

class DcmConnector {
public:
  DcmConnector(DcmServer server);
  void findPatients(const char *patientId, const char *patientName,
                    const char *patientBirthDate);
  void findStudies(const char *patientId, const char *patientName,
                   const char *patientBirthDate, const char *accessionNumber,
                   const char *studyDate, const char *modality,
                   const char *studyInstanceUID);
  void findSeries();
  void fetchStudy();
  void fetchSeries();
  void moveStudy();
  void moveSeries();
  void sendFolder();

private:
  DcmServer server_;

  void cFind();
};
