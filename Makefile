.PHONY: setup dev demo test clean

setup:
	pip install -e agentops-core/
	pip install -e agent-circuit-breaker/"[dev]"
	pip install -e agent-chaos-toolkit/"[dev]"
	pip install -e agent-slo-platform/"[dev]"
	pip install -e dashboard/"[dev]"

dev:
	docker compose up --build

demo:
	python scripts/seed.py

test:
	cd agent-circuit-breaker && python -m pytest -x && cd ..
	cd agent-chaos-toolkit && python -m pytest -x && cd ..
	cd agent-slo-platform && python -m pytest -x && cd ..

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name \*.egg-info -exec rm -rf {} + 2>/dev/null || true
