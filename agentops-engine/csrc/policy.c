#include "util.h"
#include <stdint.h>
#include <string.h>

int ao_policy_body_patterns(const uint8_t *body, uint32_t len, const char **out, uint32_t *plen) {
    if (len < 2) return -1;
    uint16_t n = (uint16_t)(body[0] | (body[1] << 8));
    if (n > 64) return -1;
    uint32_t pos = 2;
    for (uint16_t i = 0; i < n && out && plen; i++) {
        if (pos + 2 > len) return -1;
        uint16_t l = (uint16_t)(body[pos] | (body[pos+1] << 8));
        pos += 2;
        if (pos + l > len || l > 256) return -1;
        out[i] = (const char *)(body + pos);
        plen[i] = l;
        pos += l;
    }
    return pos == len ? 0 : -1;
}

uint32_t ao_policy_body_u32(const uint8_t *body, uint32_t len, uint32_t *out) {
    if (len != 8) return 0;
    out[0] = (uint32_t)(body[0] | (body[1] << 8) | (body[2] << 16) | ((uint32_t)body[3] << 24));
    out[1] = (uint32_t)(body[4] | (body[5] << 8) | (body[6] << 16) | ((uint32_t)body[7] << 24));
    return 1;
}
