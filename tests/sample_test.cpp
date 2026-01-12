#include <gtest/gtest.h>

#include "legacy_sample.h"

TEST(LegacySample, SafeDiv_ZeroDivisor_ReturnsZero) {
  EXPECT_EQ(legacy_sample::safe_div(10, 0), 0);
}

TEST(LegacySample, CopyCstr_NullDstOrZeroSize_DoesNothing) {
  EXPECT_EQ(legacy_sample::copy_cstr(nullptr, 10, "abc"), 0u);

  char buf[4] = {'x', 'x', 'x', '\0'};
  EXPECT_EQ(legacy_sample::copy_cstr(buf, 0, "abc"), 0u);
  EXPECT_EQ(buf[0], 'x');  // unchanged
}

TEST(LegacySample, CopyCstr_AlwaysNullTerminates_WhenSizePositive) {
  char buf[4];
  auto n = legacy_sample::copy_cstr(buf, sizeof(buf), "abcdef");
  EXPECT_LT(n, sizeof(buf)) << "must leave room for null terminator";
  EXPECT_EQ(buf[sizeof(buf) - 1], '\0');
}

