#include <exception>
class ConnectorError : public std::exception {
public:
  ConnectorError(const char *message);
  const char *what();

private:
  const char *message_;
};