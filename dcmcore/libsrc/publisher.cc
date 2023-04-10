#include "publisher.h"
#include <fstream>
#include <iostream>

static const short SOCKET_PORT = 8000;

Session::Session(tcp::socket socket) : socket_(std::move(socket)), buffer_() {}

void Session::start(error_handler &&onError) {
  this->on_error_ = std::move(onError);
  receive_topic();
}

std::string Session::get_topic() { return topic_; }

void Session::send_file(const std::string &filename) {
  std::cout << "Sending file" << std::endl;
  std::ifstream file(filename, std::ios::binary);

  // Get length of file
  file.seekg(0, file.end);
  std::size_t file_size = file.tellg();
  file.seekg(0, file.beg);

  // Send the file size
  io::async_write(
      socket_, io::buffer(&file_size, sizeof(file_size)),
      [&, this](boost::system::error_code ec, std::size_t /*length*/) {
        if (!ec) {
          char buffer[1024];
          send_file_chunk(file, buffer, file_size);
        } else {
          std::cout << "Error while sending file size: " << ec.message()
                    << std::endl;
          on_error_();
        }
      });
}

void Session::receive_topic() {
  auto self(shared_from_this());
  io::async_read_until(
      socket_, buffer_, "\n",
      [this, self](boost::system::error_code ec, std::size_t length) {
        if (!ec) {
          std::istream is(&buffer_);
          std::getline(is, topic_);
          std::cout << "New subscription to topic: " << topic_ << std::endl;
          receive_topic();
        } else {
          std::cout << "Error while sending file chunk: " << ec.message()
                    << std::endl;
          on_error_();
        }
      });
}

void Session::send_file_chunk(std::ifstream &file, char *buffer,
                              std::size_t remaining_bytes) {
  if (remaining_bytes == 0) {
    return;
  }

  std::size_t chunk_size = std::min(remaining_bytes, sizeof(buffer));
  file.read(buffer, chunk_size);
  io::async_write(socket_, io::buffer(buffer, chunk_size),
                  [&, this](boost::system::error_code error,
                            std::size_t bytes_transferred) {
                    if (error) {
                      std::cout << "Error: " << error.message() << std::endl;
                      on_error_();
                      return;
                    }

                    remaining_bytes -= bytes_transferred;
                    send_file_chunk(file, buffer, remaining_bytes);
                  });
}

Server::Server()
    : io_context_(),
      acceptor_(io_context_, tcp::endpoint(tcp::v4(), SOCKET_PORT)) {}

void Server::start() {
  do_accept();
  io_context_.run();
}

void Server::publish_file(const char *topic, const char *file_path) {
  for (auto &session : sessions_) {
    if (session->get_topic() == topic) {
      session->send_file(file_path);
    }
  }
}

void Server::do_accept() {
  acceptor_.async_accept(
      [this](boost::system::error_code ec, tcp::socket socket) {
        if (!ec) {
          auto session = std::make_shared<Session>(std::move(socket));
          sessions_.insert(session);
          session->start([&, weak = std::weak_ptr<Session>(session)] {
            auto shared = weak.lock();
            if (shared) {
              sessions_.erase(shared);
            }
          });
        }

        do_accept();
      });
}
