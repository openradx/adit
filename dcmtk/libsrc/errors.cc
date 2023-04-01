#include "errors.h"

ConnectorError::ConnectorError(const char *message) { message_ = message; }

const char *ConnectorError::what() { return message_; }