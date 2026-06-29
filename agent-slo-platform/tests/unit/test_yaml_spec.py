"""Tests for YAML SLO parser."""

import pytest

from agent_slo.yaml_spec import SLOYaml, parse_yaml, window_to_seconds


SLO_YAML = """
apiVersion: agentops.io/v1
kind: SLO
metadata:
  name: task-success-rate
  tenant: acme-corp
  environment: production
spec:
  sli: task_success_rate
  target: 0.95
  comparator: gt
  window: 7d
  burnRateAlerts:
    - threshold: 0.02
      severity: info
    - threshold: 0.10
      severity: critical
"""

RISK_YAML = """
apiVersion: agentops.io/v1
kind: RiskBudget
metadata:
  name: destructive-action-risk
  tenant: acme-corp
  environment: production
spec:
  budget: 5
  window: 1h
  weights:
    delete_file: 2
    send_email: 1
  action: require_approval
"""


def test_parse_slo() -> None:
    docs = parse_yaml(SLO_YAML)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.kind == "SLO"
    assert doc.metadata.name == "task-success-rate"
    assert doc.spec.target == 0.95
    assert doc.spec.comparator == "gt"
    assert doc.spec.window == "7d"
    assert len(doc.spec.burn_rate_alerts) == 2
    assert doc.spec.burn_rate_alerts[0].severity == "info"


def test_parse_risk_budget() -> None:
    docs = parse_yaml(RISK_YAML)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.kind == "RiskBudget"
    assert doc.spec.budget == 5
    assert doc.spec.weights["delete_file"] == 2
    assert doc.spec.action == "require_approval"


def test_window_to_seconds() -> None:
    assert window_to_seconds("1m") == 60
    assert window_to_seconds("1h") == 3600
    assert window_to_seconds("1d") == 86400
    assert window_to_seconds("1w") == 604800
    with pytest.raises(ValueError):
        window_to_seconds("invalid")
