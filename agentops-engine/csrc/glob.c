#include "util.h"

int ao_glob_match(const char *pattern, uint32_t plen, const char *text, uint32_t tlen, uint64_t *steps) {
    uint32_t pi = 0, ti = 0, star = tlen + 1, star_text = tlen + 1;
    uint64_t local = 0;
    while (ti <= tlen) {
        if (++local > 100000u) {
            if (steps) *steps = local;
            return 0;
        }
        if (pi < plen && (pattern[pi] == '?' || pattern[pi] == text[ti])) {
            pi++;
            ti++;
        } else if (pi < plen && pattern[pi] == '*') {
            star = pi++;
            star_text = ti;
        } else if (star <= plen) {
            pi = star + 1;
            ti = ++star_text;
        } else {
            if (steps) *steps = local;
            return 0;
        }
    }
    while (pi < plen && pattern[pi] == '*') pi++;
    if (steps) *steps = local;
    return pi == plen && ti == tlen;
}
