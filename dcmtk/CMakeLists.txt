project(demo)
cmake_minimum_required(VERSION 3.16)
include_directories(/workspace/dcmtk-3.6.7-install/usr/local/include ./includes)
link_directories(/workspace/dcmtk-3.6.7-install/usr/local/lib)
add_executable(demo libsrc/demo.cc libsrc/dimconnector.cc)
target_link_libraries(demo dcmect dcmpmap dcmtract dcmseg dcmfg dcmiod dcmrt dcmpstat dcmqrdb dcmwlm dcmdsig cmr dcmsr dcmnet dcmtls dcmtkcharls dcmjpls ijg16 ijg12 ijg8 dcmjpeg dcmimage dcmimgle i2d dcmdata oflog ofstd z icuuc pthread)
 