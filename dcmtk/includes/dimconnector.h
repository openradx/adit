class DimConnector {
public:
  DimConnector(const char *peer, unsigned int port, const char *ourTitle,
               const char *peerTitle);
  void findPatients();
  void findStudies();
  void findSeries();
  void fetchStudy(int argc, char *argv[]);
  void fetchSeries();
  void moveStudy();
  void moveSeries();
  void sendFolder();

private:
  const char *peer_;
  unsigned int port_;
  const char *ourTitle_;
  const char *peerTitle_;

  void cFind();
};
