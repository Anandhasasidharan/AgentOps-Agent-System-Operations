"""Regression test for the seeded-API-key quickstart in README.md."""

from __future__ import annotations

from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"


def _section(name: str, next_name: str) -> str:
    text = README.read_text()
    return text.split(name, 1)[1].split(next_name, 1)[0]


def test_quickstart_seeds_then_sources_the_key_file() -> None:
    quickstart = _section("## ⚡ Quick Start", "## 📸 Dashboard")

    assert "python scripts/seed.py" in quickstart
    assert "set -a; . ./.agentops.env; set +a" in quickstart
    assert quickstart.index("python scripts/seed.py") < quickstart.index(
        "set -a; . ./.agentops.env; set +a"
    )


def test_demo_uses_the_seeded_key_file() -> None:
    demo = _section("## 🧪 Demo", "## 📄 License")

    assert "python scripts/seed.py" in demo
    assert "set -a; . ./.agentops.env; set +a" in demo
    assert 'export API_KEY="dev-api-key:<token-from-seed-output>"' not in demo


def test_no_bare_dev_api_key_in_curl_examples() -> None:
    text = README.read_text()

    assert "X-API-Key: dev-api-key" not in text
