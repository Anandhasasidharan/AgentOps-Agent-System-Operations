from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any


class ExecutionGraph:
    def __init__(self, window_seconds: int = 3600):
        self.window_seconds = window_seconds
        self._agent_tool: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._agent_agent: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    def record_edge(self, source_agent: str, target_tool: str, timestamp: float | None = None) -> None:
        ts = timestamp or time.time()
        self._prune(source_agent)
        self._agent_tool[source_agent][target_tool].append(ts)

    def record_agent_edge(self, source_agent: str, target_agent: str, timestamp: float | None = None) -> None:
        ts = timestamp or time.time()
        self._prune_agent(source_agent)
        self._agent_agent[source_agent][target_agent].append(ts)

    def get_anomaly_score(self, agent_id: str, tool_name: str) -> float:
        self._prune(agent_id)
        edges = self._agent_tool.get(agent_id, {})
        counts = {tool: len(ts_list) for tool, ts_list in edges.items()}
        total = sum(counts.values())
        if total < 3 or tool_name not in counts:
            return 0.0

        values = list(counts.values())
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values) if len(values) > 1 else 1.0
        std = math.sqrt(variance) or 1.0

        current = counts[tool_name]
        z_score = (current - mean) / std
        if z_score > 2.0:
            return min(1.0, (z_score - 2.0) / 5.0)
        return 0.0

    def status(self) -> dict[str, Any]:
        agent_count = len(self._agent_tool)
        tool_edges = sum(len(tools) for tools in self._agent_tool.values())
        agent_edges = sum(len(agents) for agents in self._agent_agent.values())
        return {
            "agents": agent_count,
            "tool_edges": tool_edges,
            "agent_edges": agent_edges,
            "window_seconds": self.window_seconds,
        }

    def anomalies(self) -> list[dict[str, Any]]:
        results = []
        for agent, tools in self._agent_tool.items():
            counts = {t: len(ts) for t, ts in tools.items()}
            total = sum(counts.values())
            if total < 3:
                continue
            values = list(counts.values())
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values) if len(values) > 1 else 1.0
            std = math.sqrt(variance) or 1.0
            for tool, count in counts.items():
                z = (count - mean) / std
                if z > 2.0:
                    results.append({
                        "agent": agent, "tool": tool, "count": count,
                        "z_score": round(z, 3), "mean": round(mean, 3),
                    })
        return results

    def _prune(self, agent_id: str) -> None:
        cutoff = time.time() - self.window_seconds
        tools = self._agent_tool.get(agent_id, {})
        expired = [t for t, ts_list in tools.items() if all(ts < cutoff for ts in ts_list)]
        for t in expired:
            del tools[t]
        for t in list(tools.keys()):
            tools[t] = [ts for ts in tools[t] if ts >= cutoff]
            if not tools[t]:
                del tools[t]

    def _prune_agent(self, agent_id: str) -> None:
        cutoff = time.time() - self.window_seconds
        agents = self._agent_agent.get(agent_id, {})
        expired = [a for a, ts_list in agents.items() if all(ts < cutoff for ts in ts_list)]
        for a in expired:
            del agents[a]
        for a in list(agents.keys()):
            agents[a] = [ts for ts in agents[a] if ts >= cutoff]
            if not agents[a]:
                del agents[a]


_graph = ExecutionGraph()


def get_graph() -> ExecutionGraph:
    return _graph
