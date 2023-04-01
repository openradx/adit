cmake_minimum_required(VERSION 3.16)

project(connector)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_library(connector SHARED libsrc/connector.cc)
target_include_directories(connector PUBLIC /workspace/dcmtk-3.6.7-install/usr/local/include includes)
target_link_directories(connector PUBLIC /workspace/dcmtk-3.6.7-install/usr/local/lib)
target_link_libraries(connector dcmect dcmpmap dcmtract dcmseg dcmfg dcmiod dcmrt dcmpstat dcmqrdb dcmwlm dcmdsig cmr dcmsr dcmnet dcmtls dcmtkcharls dcmjpls ijg16 ijg12 ijg8 dcmjpeg dcmimage dcmimgle i2d dcmdata oflog ofstd z icuuc pthread wrap)

add_executable(demo demo/demo.cc)
target_link_libraries(demo connector)
 