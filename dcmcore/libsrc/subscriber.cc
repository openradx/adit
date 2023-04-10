#include "subscriber.h"
#include <fstream>
#include <iostream>

static const short SOCKET_PORT = 8000;

Client::Client() : io_context_(), socket_(io_context_) {}

void Client::subscribe(const char *topic,
                       std::function<void(std::vector<char>)> hdl) {
  tcp::resolver resolver(io_context_);
  auto endpoints = resolver.resolve("127.0.0.1", std::to_string(SOCKET_PORT));
  do_connect(endpoints, topic);
}

void Client::do_connect(tcp::resolver::results_type &endpoints,
                        const char *topic) {
  io::async_connect(socket_, endpoints,
                    [&, this](boost::system::error_code ec, tcp::endpoint) {
                      if (!ec) {
                        std::cout << "Connected" << std::endl;
                        send_topic(topic);
                        receive_file();
                      }
                    });
}

void Client::send_topic(const char *topic) {
  const std::string data = std::string(topic) + "\n";
  io::async_write(socket_, boost::asio::buffer(data, data.length()),
                  [this](boost::system::error_code ec, std::size_t length) {
                    if (!ec) {
                      std::cout << "Wrote " << length << " bytes" << std::endl;
                    }
                  });
}

void Client::receive_file() {
  const char *filename = "./test.txt";
  std::ofstream file(filename, std::ios::binary);
  if (!file) {
    // TODO: Handle error
    std::cerr << "Failed to create file " << filename << std::endl;
    return;
  }

  std::size_t file_size;
  io::async_read(socket_, boost::asio::buffer(&file_size, sizeof(file_size)),
                 [this](boost::system::error_code ec, std::size_t length) {
                   if (!ec) {
                   }
                 });
}

void Client::receive_file_chunk(std::ofstream &file, char *buffer,
                                std::size_t remaining_bytes) {
  if (remaining_bytes == 0) {
    std::cout << "File fully received" << std::endl;
    receive_file();
  }

  std::size_t bytes_to_receive = std::min(remaining_bytes, sizeof(buffer));
  io::async_read(socket_, boost::asio::buffer(buffer, bytes_to_receive),
                 [&, this](boost::system::error_code error,
                           std::size_t bytes_transferred) {
                   if (error) {
                     std::cerr << "Failed to to receive file chunk"
                               << std::endl;
                     return;
                   }

                   remaining_bytes -= bytes_transferred;
                   receive_file_chunk(file, buffer, remaining_bytes);
                 });
}
