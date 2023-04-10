#include <boost/asio.hpp>

namespace io = boost::asio;
using boost::asio::ip::tcp;

class Client {
public:
  Client();
  void subscribe(const char *topic,
                 std::function<void(std::vector<char> buffer)> hdl);

private:
  void do_connect(tcp::resolver::results_type &endpoints, const char *topic);
  void send_topic(const char *topic);
  void receive_file();
  void receive_file_chunk(std::ofstream &file, char *buffer,
                          std::size_t remaining);

  io::io_context io_context_;
  tcp::socket socket_;
};