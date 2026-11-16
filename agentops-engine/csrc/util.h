#ifndef AGENTOPS_UTIL_H
#define AGENTOPS_UTIL_H

#include <stdint.h>
#include <string.h>

typedef struct {
    uint8_t type;
    uint8_t action;
    uint16_t reserved;
    uint32_t body_len;
    const uint8_t *body;
} ao_blob_policy;

static inline uint32_t hash_bytes(const char *s, uint32_t n) {
    uint32_t h = 2166136261u;
    for (uint32_t i = 0; i < n; i++) {
        h ^= (unsigned char)s[i];
        h *= 16777619u;
    }
    return h;
}

static inline int bounded_equal(const char *a, uint32_t alen, const char *b, uint32_t blen) {
    return alen == blen && memcmp(a, b, alen) == 0;
}

static inline int buffer_copy_safe(char *dst, uint32_t dst_cap, const char *src, uint32_t src_len) {
    if (src_len >= dst_cap) return -1;
    memcpy(dst, src, src_len);
    dst[src_len] = '\0';
    return 0;
}

static inline uint32_t ao_crc32(const uint8_t *data, size_t len) {
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        c ^= data[i];
        for (int b = 0; b < 8; b++) c = (c & 1u) ? (c >> 1) ^ 0xEDB88320u : c >> 1;
    }
    return c ^ 0xFFFFFFFFu;
}

#endif
