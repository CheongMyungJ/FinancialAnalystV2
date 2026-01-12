cmake_minimum_required(VERSION 3.20)
project(TestAgentDemo LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(ENABLE_TESTS "Enable unit tests" ON)

add_library(legacy_sample
  src/legacy_sample.cpp
)
target_include_directories(legacy_sample PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

if(ENABLE_TESTS)
  include(CTest)
  enable_testing()
  add_subdirectory(tests)
endif()

