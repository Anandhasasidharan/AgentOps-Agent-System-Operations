"""Tests for SLO evaluation engine."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from agent_slo.engine import (
    compute_burn_rate,
    evaluate_slo,
    window_bounds,
)


def test_evaluate_slo_gt() -> None:
    assert evaluate_slo(0.96, 0.95, "gt") is True
    assert evaluate_slo(0.94, 0.95, "gt") is False


def test_evaluate_slo_lt() -> None:
    assert evaluate_slo(0.04, 0.05, "lt") is True
    assert evaluate_slo(0.06, 0.05, "lt") is False


def test_compute_burn_rate() -> None:
    # 2% consumed after 1% of window elapsed
    assert compute_burn_rate(0.02, 86400, 864) == pytest.approx(2.0)
    # 5% consumed after 10% of window elapsed
    assert compute_burn_rate(0.05, 86400, 8640) == pytest.approx(0.5)


def test_window_bounds() -> None:
    anchor = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)
    start, end = window_bounds("1h", anchor)
    assert end == anchor
    assert start == anchor - timedelta(hours=1)
