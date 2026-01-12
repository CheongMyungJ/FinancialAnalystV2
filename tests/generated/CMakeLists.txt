# Generated tests are written into this directory by tools/test_agent.
# We intentionally keep this CMakeLists stable so the agent doesn't have to edit CMake.

file(GLOB TEST_AGENT_GENERATED_SRCS CONFIGURE_DEPENDS "*.cpp")

if(TEST_AGENT_GENERATED_SRCS)
  add_executable(test_agent_generated_tests ${TEST_AGENT_GENERATED_SRCS})
  target_link_libraries(test_agent_generated_tests PRIVATE legacy_sample GTest::gtest_main)

  include(GoogleTest)
  gtest_discover_tests(test_agent_generated_tests)
endif()

