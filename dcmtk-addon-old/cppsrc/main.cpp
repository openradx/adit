#include "connector.h"
#include <napi.h>

Napi::Object InitAll(Napi::Env env, Napi::Object exports) {
  DcmServer server;
  server.ourAETitle = "ADIT1DEV";
  server.peerHostName = "127.0.0.1";
  server.peerPort = 7501;
  server.peerAETitle = "ORTHANC1";
  DcmConnector connector = DcmConnector(server);
  connector.findPatients("1005", "", "");

  return exports;
}

NODE_API_MODULE(testaddon, InitAll)
