#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "util.h"

int ao_blob_validate(const uint8_t *blob, size_t len, ao_blob_policy **out, uint32_t *count) {
    if (len < 16 || memcmp(blob, "AOPL", 4) != 0) return -1;
    uint16_t version = (uint16_t)(blob[4] | (blob[5] << 8));
    uint16_t flags = (uint16_t)(blob[6] | (blob[7] << 8));
    uint32_t total_len = (uint32_t)(blob[8] | (blob[9] << 8) | (blob[10] << 16) | ((uint32_t)blob[11] << 24));
    uint32_t crc = (uint32_t)(blob[12] | (blob[13] << 8) | (blob[14] << 16) | ((uint32_t)blob[15] << 24));
    if (version != 1 || flags != 0 || total_len != len) return -1;
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < 12; i++) { c ^= blob[i]; for (int b = 0; b < 8; b++) c = (c & 1u) ? (c >> 1) ^ 0xEDB88320u : c >> 1; }
    for (size_t i = 16; i < len; i++) { c ^= blob[i]; for (int b = 0; b < 8; b++) c = (c & 1u) ? (c >> 1) ^ 0xEDB88320u : c >> 1; }
    if ((c ^ 0xFFFFFFFFu) != crc) return -1;
    if (len >= 20) {
        uint32_t n = (uint32_t)(blob[16] | (blob[17] << 8) | (blob[18] << 16) | ((uint32_t)blob[19] << 24));
        size_t pos = 20;
        ao_blob_policy *arr = n ? calloc(n, sizeof(*arr)) : NULL;
        if (n && !arr) return -1;
        for (uint32_t i = 0; i < n; i++) {
            if (pos + 8 > len) { free(arr); return -1; }
            arr[i].type = blob[pos];
            arr[i].action = blob[pos+1];
            arr[i].reserved = (uint16_t)(blob[pos+2] | (blob[pos+3] << 8));
            arr[i].body_len = (uint32_t)(blob[pos+4] | (blob[pos+5] << 8) | (blob[pos+6] << 16) | ((uint32_t)blob[pos+7] << 24));
            pos += 8;
            if (pos + arr[i].body_len > len) { free(arr); return -1; }
            arr[i].body = blob + pos;
            pos += arr[i].body_len;
        }
        if (pos != len) { free(arr); return -1; }
        *out = arr;
        *count = n;
        return 0;
    }
    return -1;
}
