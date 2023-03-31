cmake_minimum_required(VERSION 3.16)

project(dimconnector)

add_library(dimconnector libsrc/dimconnector.cc)
target_include_directories(dimconnector PUBLIC /workspace/dcmtk-3.6.7-install/usr/local/include includes)
target_link_directories(dimconnector PUBLIC /workspace/dcmtk-3.6.7-install/usr/local/lib)
target_link_libraries(dimconnector dcmect dcmpmap dcmtract dcmseg dcmfg dcmiod dcmrt dcmpstat dcmqrdb dcmwlm dcmdsig cmr dcmsr dcmnet dcmtls dcmtkcharls dcmjpls ijg16 ijg12 ijg8 dcmjpeg dcmimage dcmimgle i2d dcmdata oflog ofstd z icuuc pthread)

add_executable(demo demo/demo.cc)
target_link_libraries(demo dimconnector)
 