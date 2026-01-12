#include "legacy_sample.h"

#include <cstring>

namespace legacy_sample {

std::size_t copy_cstr(char* dst, std::size_t dst_size, const char* src) {
  if (dst == nullptr || dst_size == 0) return 0;
  if (src == nullptr) {
    dst[0] = '\0';
    return 0;
  }

  std::size_t n = std::strlen(src);
  if (n >= dst_size) n = dst_size - 1;  // keep room for '\0'
  std::memcpy(dst, src, n);
  dst[n] = '\0';
  return n;
}

int safe_div(int a, int b) {
  if (b == 0) return 0;
  return a / b;
}

}  // namespace legacy_sample

