#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "agentops.h"
#include "util.h"

extern int ao_glob_match(const char *pattern, uint32_t plen, const char *text, uint32_t tlen, uint64_t *steps);
extern int ao_rate_limit_allows(uint32_t call_count, uint32_t max_calls);
extern int64_t ao_retry_after_ms(uint32_t window_seconds);
extern int ao_blob_validate(const uint8_t *blob, size_t len, ao_blob_policy **out, uint32_t *count);
extern int ao_policy_body_patterns(const uint8_t *body, uint32_t len, const char **out, uint32_t *plen);
extern uint32_t ao_policy_body_u32(const uint8_t *body, uint32_t len, uint32_t *out);
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

struct ao_engine {
    ao_config cfg;
    ao_agent_slot *agents;
    pthread_mutex_t shard_locks[8];
    pthread_rwlock_t policy_lock;
    uint8_t *blob_copy;
    ao_blob_policy *policies;
    uint32_t policy_count;
};

uint32_t ao_abi_version(void) { return AO_ABI_VERSION; }

ao_status ao_engine_new(const ao_config *cfg, ao_engine **out) {
    if (!cfg || !out || cfg->max_agents == 0 || cfg->max_state_bytes == 0) return AO_ERR_ARG;
    ao_engine *e = calloc(1, sizeof(*e));
    if (!e) return AO_ERR_LIMIT;
    e->cfg = *cfg;
    e->agents = calloc(cfg->max_agents, sizeof(*e->agents));
    if (!e->agents) { free(e); return AO_ERR_LIMIT; }
    for (int i = 0; i < 8; i++) pthread_mutex_init(&e->shard_locks[i], NULL);
    pthread_rwlock_init(&e->policy_lock, NULL);
    *out = e;
    return AO_OK;
}

void ao_engine_free(ao_engine *e) {
    if (!e) return;
    for (int i = 0; i < 8; i++) pthread_mutex_destroy(&e->shard_locks[i]);
    pthread_rwlock_destroy(&e->policy_lock);
    free(e->agents);
    free(e->blob_copy);
    free(e->policies);
    free(e);
}

ao_status ao_policy_load(ao_engine *e, const uint8_t *blob, size_t len) {
    if (!e || !blob || len < 20 || len > 16 * 1024 * 1024) return AO_ERR_ARG;
    uint8_t *copy = malloc(len);
    if (!copy) return AO_ERR_LIMIT;
    memcpy(copy, blob, len);
    ao_blob_policy *policies = NULL;
    uint32_t count = 0;
    if (ao_blob_validate(copy, len, &policies, &count) != 0) {
        free(copy);
        return AO_ERR_POLICY;
    }
    pthread_rwlock_wrlock(&e->policy_lock);
    free(e->blob_copy);
    free(e->policies);
    e->blob_copy = copy;
    e->policies = policies;
    e->policy_count = count;
    for (uint32_t i = 0; i < e->cfg.max_agents; i++) e->agents[i].active = 0;
    pthread_rwlock_unlock(&e->policy_lock);
    return AO_OK;
}

static ao_verdict action_to_verdict(uint8_t action) {
    return action == 0 ? AO_ALLOW : AO_BLOCK;
}

static uint16_t policy_reason(uint8_t typ) {
    switch (typ) {
      case 1: return AO_REASON_TOOL_ALLOWLIST;
      case 2: return AO_REASON_TOOL_BLOCKLIST;
      case 3: return AO_REASON_RATE_LIMIT;
      case 4: return AO_REASON_TOKEN_BUDGET;
      case 5: return AO_REASON_RISK_THRESHOLD;
      case 6: return AO_REASON_ANOMALY_THRESHOLD;
      case 7: return AO_REASON_TIME_WINDOW;
      case 8: return AO_REASON_REASONING_LOOP;
      default: return AO_REASON_POLICY_MISMATCH;
    }
}

ao_status ao_intercept(ao_engine *e, const ao_call *call, ao_result *out) {
    if (!e || !call || !out || !call->agent_id || !call->tool) return AO_ERR_ARG;
    if (call->agent_id_len > sizeof(((ao_agent_slot *)0)->agent_id) - 1 || call->tool_len > sizeof(((ao_agent_slot *)0)->last_tool) - 1) return AO_ERR_ARG;
    uint32_t h = hash_bytes(call->agent_id, call->agent_id_len);
    uint32_t shard = h % 8;
    pthread_mutex_lock(&e->shard_locks[shard]);
    uint32_t idx = 0;
    int found = 0;
    for (uint32_t probe = 0; probe < e->cfg.max_agents && !found; probe++) {
        uint32_t i = (h / 8 + probe) % e->cfg.max_agents;
        if (!e->agents[i].active) break;
        if (bounded_equal(e->agents[i].agent_id, e->agents[i].agent_id_len, call->agent_id, call->agent_id_len)) { idx = i; found = 1; break; }
    }
    if (!found) {
        for (uint32_t i = 0; i < e->cfg.max_agents; i++) {
            if (!e->agents[i].active) {
                e->agents[i].active = 1;
                memcpy(e->agents[i].agent_id, call->agent_id, call->agent_id_len);
                e->agents[i].agent_id[call->agent_id_len] = '\0';
                e->agents[i].agent_id_len = call->agent_id_len;
                idx = i; found = 1; break;
            }
        }
    }
    if (!found) {
        pthread_mutex_unlock(&e->shard_locks[shard]);
        out->verdict = e->cfg.fail_open ? AO_ALLOW : AO_BLOCK;
        out->reason_code = AO_REASON_ENGINE_LIMIT;
        out->policy_index = -1;
        out->retry_after_ms = 0;
        return AO_OK;
    }
    ao_agent_slot *slot = &e->agents[idx];
    slot->call_count++;
    slot->total_tokens += call->tokens;
    if (slot->last_tool_len == call->tool_len && memcmp(slot->last_tool, call->tool, call->tool_len) == 0) slot->consecutive_same_tool++;
    else slot->consecutive_same_tool = 1;
    if (call->tool_len < sizeof(slot->last_tool)) { memcpy(slot->last_tool, call->tool, call->tool_len); slot->last_tool[call->tool_len] = '\0'; slot->last_tool_len = call->tool_len; }
    pthread_rwlock_rdlock(&e->policy_lock);
    out->verdict = AO_ALLOW;
    out->reason_code = AO_REASON_NONE;
    out->policy_index = -1;
    out->retry_after_ms = 0;
    for (uint32_t pi = 0; pi < e->policy_count; pi++) {
        ao_blob_policy *p = &e->policies[pi];
        int hit = 0;
        switch (p->type) {
          case 1: { // allowlist: block if not matched
            const char *patterns[64] = {0}; uint32_t plens[64] = {0};
            if (ao_policy_body_patterns(p->body, p->body_len, patterns, plens) == 0) {
                int allowed = 0;
                for (uint16_t i = 0; patterns[i] && i < 64; i++) { uint64_t steps=0; if (ao_glob_match(patterns[i], plens[i], call->tool, call->tool_len, &steps)) allowed = 1; if (steps > 100000) break; }
                hit = !allowed;
            }
            break;
          }
          case 2: { // blocklist: block if matched
            const char *patterns[64] = {0}; uint32_t plens[64] = {0};
            if (ao_policy_body_patterns(p->body, p->body_len, patterns, plens) == 0) {
                for (uint16_t i = 0; patterns[i] && i < 64; i++) { uint64_t steps=0; if (ao_glob_match(patterns[i], plens[i], call->tool, call->tool_len, &steps)) { hit = 1; break; } }
            }
            break;
          }
          case 3: { uint32_t v[2]; if (ao_policy_body_u32(p->body, p->body_len, v) && v[0] > 0 && slot->call_count >= v[0]) hit = 1; break; }
          case 4: { uint32_t v[2]; if (ao_policy_body_u32(p->body, p->body_len, v) && v[0] > 0 && slot->total_tokens >= v[0]) hit = 1; break; }
          case 5: { uint32_t v[2]; if (ao_policy_body_u32(p->body, p->body_len, v) && call->risk_score_micro > (int64_t)v[0]) hit = 1; break; }
          case 6: { uint32_t v[2]; if (ao_policy_body_u32(p->body, p->body_len, v) && call->anomaly_score_micro > (int64_t)v[0]) hit = 1; break; }
          case 7: { uint32_t v[2]; if (ao_policy_body_u32(p->body, p->body_len, v)) { uint32_t cur=call->minute_of_day; if (cur >= v[0] && cur <= v[1]) hit = 1; } break; }
          case 8: { uint32_t v[2]; if (ao_policy_body_u32(p->body, p->body_len, v) && v[0] > 0 && slot->consecutive_same_tool >= v[0]) hit = 1; break; }
        }
        if (hit) {
            out->verdict = action_to_verdict(p->action);
            out->reason_code = policy_reason(p->type);
            out->policy_index = (int32_t)pi;
            if (p->type == 3) { uint32_t v[2]; if (ao_policy_body_u32(p->body, p->body_len, v)) out->retry_after_ms = ao_retry_after_ms(v[1]); }
            break;
        }
    }
    pthread_rwlock_unlock(&e->policy_lock);
    pthread_mutex_unlock(&e->shard_locks[shard]);
    return AO_OK;
}
