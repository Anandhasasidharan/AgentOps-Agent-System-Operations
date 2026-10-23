#include <stdint.h>

int ao_rate_limit_allows(uint32_t call_count, uint32_t max_calls) {
    return max_calls == 0 || call_count < max_calls;
}

int64_t ao_retry_after_ms(uint32_t window_seconds) {
    return window_seconds == 0 ? 0 : (int64_t)window_seconds * 1000;
}
