cmake_minimum_required(VERSION 3.24)

project(cpp-parametric-http-test)

set(CMAKE_BUILD_TYPE "RelWithDebInfo")
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(DD_TRACE_CPP_COMMIT "main" CACHE STRING "Branch or commit SHA1 of dd-trace-cpp to use. Use `main` by default") 

message(STATUS "Using dd-trace-cpp@${DD_TRACE_CPP_COMMIT}")

include(FetchContent)
set(FETCHCONTENT_QUIET OFF)

FetchContent_Declare(
  dd-trace-cpp
  GIT_REPOSITORY https://github.com/DataDog/dd-trace-cpp
  GIT_TAG        ${DD_TRACE_CPP_COMMIT} 
  GIT_SHALLOW    ON
  GIT_PROGRESS   ON
)
FetchContent_MakeAvailable(dd-trace-cpp)

add_executable(cpp-parametric-http-test)

target_compile_options(cpp-parametric-http-test
  PUBLIC
  $<$<COMPILE_LANGUAGE:CXX>:-Wall -Wextra -Werror>
)

target_sources(cpp-parametric-http-test
  PRIVATE 
  main.cpp
  developer_noise.cpp
  request_handler.cpp
)

target_link_libraries(cpp-parametric-http-test dd_trace_cpp-objects)

install(
  TARGETS cpp-parametric-http-test
  DESTINATION bin
)
