#pragma once

#include <cstddef>

// Intentionally simple "legacy-like" APIs for end-to-end verification.
// In real adoption, these will be replaced by your legacy targets.

namespace legacy_sample {

// Copies src into dst.
// Returns number of bytes written (excluding terminating null).
// Contract:
// - If dst is null or dst_size == 0, returns 0 and does nothing.
// - Always null-terminates when dst_size > 0.
std::size_t copy_cstr(char* dst, std::size_t dst_size, const char* src);

// Contract:
// - If b == 0, returns 0 (legacy behavior; not throwing).
int safe_div(int a, int b);

}  // namespace legacy_sample

