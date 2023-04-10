#include "connector.h"
#include <iostream>

using namespace std;

int main(int argc, char *argv[]) {
  Server server;
  server.ourAETitle = "ADIT1DEV";
  server.peerHostName = "127.0.0.1";
  server.peerPort = 7501;
  server.peerAETitle = "ORTHANC1";
  Connector connector = Connector(server);
  connector.findPatients("1005", "", "");

  return 0;
}