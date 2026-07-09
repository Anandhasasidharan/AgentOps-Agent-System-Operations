from __future__ import annotations

import time

from circuit_breaker.graph_monitor import ExecutionGraph


class TestExecutionGraph:
    def setup_method(self):
        self.graph = ExecutionGraph(window_seconds=3600)

    def test_record_edge_adds_weight(self):
        self.graph.record_edge("agent-1", "read_file")
        self.graph.record_edge("agent-1", "read_file")
        tool_edges = self.graph._agent_tool["agent-1"]
        assert len(tool_edges["read_file"]) == 2

    def test_record_agent_edge(self):
        self.graph.record_agent_edge("agent-1", "agent-2")
        self.graph.record_agent_edge("agent-1", "agent-2")
        assert len(self.graph._agent_agent["agent-1"]["agent-2"]) == 2

    def test_anomaly_score_zero_for_insufficient_data(self):
        assert self.graph.get_anomaly_score("agent-1", "read_file") == 0.0

    def test_anomaly_score_increases_with_frequent_tool(self):
        for _ in range(50):
            self.graph.record_edge("agent-1", "read_file")
        for _ in range(2):
            self.graph.record_edge("agent-1", "write_file")
        assert self.graph.get_anomaly_score("agent-1", "read_file") == 0.0
        score = self.graph.get_anomaly_score("agent-1", "write_file")
        assert score >= 0.0

    def test_status_returns_counts(self):
        self.graph.record_edge("agent-1", "read_file")
        self.graph.record_agent_edge("agent-1", "agent-2")
        status = self.graph.status()
        assert status["agents"] == 1
        assert status["tool_edges"] == 1
        assert status["agent_edges"] == 1

    def test_anomalies_returns_list(self):
        for _ in range(50):
            self.graph.record_edge("agent-1", "read_file")
        self.graph.record_edge("agent-1", "write_file")
        result = self.graph.anomalies()
        assert isinstance(result, list)

    def test_window_eviction(self):
        self.graph = ExecutionGraph(window_seconds=0.01)
        self.graph.record_edge("agent-1", "read_file")
        time.sleep(0.02)
        self.graph._prune("agent-1")
        assert "read_file" not in self.graph._agent_tool.get("agent-1", {})

    def test_multiple_agents(self):
        self.graph.record_edge("agent-1", "read_file")
        self.graph.record_edge("agent-2", "execute_command")
        assert self.graph.status()["agents"] == 2
