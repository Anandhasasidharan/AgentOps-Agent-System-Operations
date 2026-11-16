/* AgentOps C engine ABI v1 */
#ifndef AGENTOPS_H
#define AGENTOPS_H

#include <stddef.h>
#include <stdint.h>

#define AO_ABI_VERSION 1u

typedef struct ao_engine ao_engine;

typedef enum {
    AO_OK = 0,
    AO_ERR_ARG,
    AO_ERR_POLICY,
    AO_ERR_LIMIT,
    AO_ERR_STATE
} ao_status;

typedef enum {
    AO_ALLOW = 0,
    AO_REVIEW = 1,
    AO_BLOCK = 2
} ao_verdict;

typedef enum {
    AO_REASON_NONE = 0,
    AO_REASON_TOOL_BLOCKLIST = 1,
    AO_REASON_TOOL_ALLOWLIST = 2,
    AO_REASON_RATE_LIMIT = 3,
    AO_REASON_TOKEN_BUDGET = 4,
    AO_REASON_RISK_THRESHOLD = 5,
    AO_REASON_ANOMALY_THRESHOLD = 6,
    AO_REASON_TIME_WINDOW = 7,
    AO_REASON_REASONING_LOOP = 8,
    AO_REASON_ENGINE_LIMIT = 9,
    AO_REASON_POLICY_MISMATCH = 10,
    AO_REASON_GLOB_NO_MATCH = 11,
    AO_REASON_GLOB_LIMIT = 12
} ao_reason_code;

typedef struct {
    uint32_t max_agents;
    uint32_t max_state_bytes;
    uint8_t fail_open;
} ao_config;

typedef struct {
    const char *agent_id;
    uint32_t agent_id_len;
    const char *tool;
    uint32_t tool_len;
    const char *input;
    uint32_t input_len;
    uint32_t tokens;
    int64_t cost_micro;
    int64_t now_ns;
    uint16_t minute_of_day;
    uint8_t weekday;
    int64_t risk_score_micro;
    int64_t anomaly_score_micro;
} ao_call;

typedef struct {
    ao_verdict verdict;
    uint16_t reason_code;
    int32_t policy_index;
    int64_t retry_after_ms;
} ao_result;

ao_status ao_engine_new(const ao_config *cfg, ao_engine **out);
void ao_engine_free(ao_engine *e);
ao_status ao_policy_load(ao_engine *e, const uint8_t *blob, size_t len);
ao_status ao_intercept(ao_engine *e, const ao_call *call, ao_result *out);
uint32_t ao_abi_version(void);

#endif
