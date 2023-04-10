#include <boost/asio.hpp>
#include <set>

namespace io = boost::asio;
using boost::asio::ip::tcp;
using error_handler = std::function<void()>;

class Session : public std::enable_shared_from_this<Session> {
public:
  Session(tcp::socket socket);
  void start(error_handler &&onError);
  std::string get_topic();
  void send_file(const std::string &filename);

private:
  void receive_topic();
  void send_file_chunk(std::ifstream &file, char *buffer, std::size_t length);

  tcp::socket socket_;
  io::streambuf buffer_;
  std::string topic_;
  error_handler on_error_;
};

class Server {
public:
  Server();
  void start();
  void publish_file(const char *topic, const char *file_path);

private:
  void do_accept();

  io::io_context io_context_;
  tcp::acceptor acceptor_;
  std::set<std::shared_ptr<Session>> sessions_;
};
