cmake_minimum_required(VERSION 3.24)

project(cpp-parametric-test)

set(CMAKE_BUILD_TYPE "RelWithDebInfo")
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
set(FETCHCONTENT_QUIET OFF)

FetchContent_Declare(
  dd-trace-cpp
  GIT_REPOSITORY https://github.com/DataDog/dd-trace-cpp
  GIT_TAG        main
  GIT_SHALLOW    ON
  GIT_PROGRESS   ON
)
FetchContent_MakeAvailable(dd-trace-cpp)

include(FindProtobuf)

# Project-level compile options
add_compile_options(-Wall -Wextra -Werror)
if (BUILD_COVERAGE)
  add_compile_options(-g -O0 -fprofile-arcs -ftest-coverage)
endif()

# grpc client library
add_library(grpc_apm_test_client)
target_sources(grpc_apm_test_client PRIVATE test_proto3_optional/apm_test_client.proto)

protobuf_generate(TARGET grpc_apm_test_client)
protobuf_generate(TARGET grpc_apm_test_client LANGUAGE grpc GENERATE_EXTENSIONS .grpc.pb.h .grpc.pb.cc PLUGIN "protoc-gen-grpc=/usr/bin/grpc_cpp_plugin")
target_include_directories(grpc_apm_test_client PUBLIC ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(grpc_apm_test_client PUBLIC protobuf::libprotobuf grpc grpc++)

# paramegtric test executable
add_executable(cpp-parametric-test)
target_sources(cpp-parametric-test PRIVATE tracing_service.cpp main.cpp)
target_include_directories(cpp-parametric-test PRIVATE ${dd-trace-cpp_SOURCE_DIR}/src)
target_link_libraries(cpp-parametric-test PRIVATE dd_trace_cpp-static grpc_apm_test_client)

install(TARGETS cpp-parametric-test RUNTIME DESTINATION bin)
