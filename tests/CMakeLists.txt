include(FetchContent)

set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
)
FetchContent_MakeAvailable(googletest)

add_executable(sample_tests
  sample_test.cpp
)
target_link_libraries(sample_tests PRIVATE legacy_sample GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(sample_tests)

# Generated tests (created by tools/test_agent) live here.
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/generated/CMakeLists.txt)
  add_subdirectory(generated)
endif()

