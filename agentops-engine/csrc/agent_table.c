#include "util.h"
#include <stdint.h>
#include <string.h>

typedef struct {
    uint8_t active;
    char agent_id[128];
    uint32_t agent_id_len;
    char last_tool[128];
    uint32_t last_tool_len;
    uint32_t call_count;
    uint32_t total_tokens;
    uint32_t consecutive_same_tool;
} ao_agent_slot;

int ao_agent_slot_find(ao_agent_slot *slots, uint32_t capacity, const char *agent_id, uint32_t len, uint32_t *idx) {
    if (capacity == 0) return 0;
    uint32_t h = hash_bytes(agent_id, len) % capacity;
    for (uint32_t probe = 0; probe < capacity; probe++) {
        uint32_t i = (h + probe) % capacity;
        if (!slots[i].active) { *idx = i; return 0; }
        if (bounded_equal(slots[i].agent_id, slots[i].agent_id_len, agent_id, len)) { *idx = i; return 1; }
    }
    return 0;
}
