#include "dcmtk/dcmnet/scu.h"

struct Server {
  const char *ourAETitle;
  const char *peerHostName;
  unsigned int peerPort;
  const char *peerAETitle;
};

struct Patient {
  OFString patientId;
  OFString patientName;
  OFString patientBirthDate;
};

struct StudyBase : public Patient {
  OFString studyInstanceUID;
  OFString accessionNumber;
  OFString studyDescription;
  OFString studyDate;
  OFString studyTime;
};

struct Study : public Patient {
  OFString numberOfStudyRelatedInstances;
  OFString numberOfStudyRelatedSeries;
  OFList<const char *> modalitiesInStudy;
};

struct Series : public StudyBase {
  OFString seriesInstanceUID;
  OFString seriesDescription;
  OFString modality;
  OFString seriesNumber;
};

class ConnectorError : public std::exception {
public:
  ConnectorError(const char *message);
  const char *what();

private:
  const char *message_;
};

class FindSCU : public DcmSCU {};

class Connector {
public:
  Connector(Server server);
  OFList<Patient> findPatients(const char *patientId, const char *patientName,
                               const char *patientBirthDate);
  OFList<Study> findStudies(const char *patientId, const char *patientName,
                            const char *patientBirthDate,
                            const char *studyInstanceUID,
                            const char *accessionNumber, const char *studyDate,
                            const char *modalitiesInStudy);
  void findSeries();
  void fetchStudy();
  void fetchSeries();
  void moveStudy();
  void moveSeries();
  void storeFolder();

private:
  Server server_;
};
