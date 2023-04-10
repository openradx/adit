cmake_minimum_required(VERSION 3.16)

project(dcmcore)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

file(GLOB sources libsrc/*.cc)
add_library(${PROJECT_NAME} SHARED ${sources})
target_include_directories(${PROJECT_NAME} PUBLIC include)
target_link_libraries(${PROJECT_NAME} dcmect dcmpmap dcmtract dcmseg dcmfg dcmiod dcmrt dcmpstat dcmqrdb dcmwlm dcmdsig cmr dcmsr dcmnet dcmtls dcmtkcharls dcmjpls ijg16 ijg12 ijg8 dcmjpeg dcmimage dcmimgle i2d dcmdata oflog ofstd z icuuc pthread wrap)

add_executable(test tests/test.cc)
target_link_libraries(test ${PROJECT_NAME})

add_executable(demo apps/demo.cc)
target_link_libraries(demo ${PROJECT_NAME})
 
add_executable(receiver apps/receiver.cc)
target_link_libraries(receiver ${PROJECT_NAME})

add_executable(test_publisher apps/test_publisher.cc)
target_link_libraries(test_publisher pthread ${PROJECT_NAME})

add_executable(test_subscriber apps/test_subscriber.cc)
target_link_libraries(test_subscriber pthread ${PROJECT_NAME})
