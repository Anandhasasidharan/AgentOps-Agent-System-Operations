.PHONY: setup dev demo test test-engine lint format-check clean demo-events

setup:
	pip install -e agentops-core/
	pip install -e agentops-events/
	pip install -e agent-circuit-breaker/"[dev]"
	pip install -e agent-chaos-toolkit/"[dev]"
	pip install -e agent-slo-platform/"[dev]"
	pip install -e dashboard/"[dev]"
	pip install -e agent-gateway/"[dev]"
	pip install -e agentops-sdk/"[dev]"
	pip install -e agentops-langchain/"[dev]"

dev:
	docker compose up --build

demo:
	python scripts/seed.py

demo-events:
	python scripts/demo_langchain.py

test:
	cd agentops-core && python -m pytest -x && cd ..
	cd agentops-events && python -m pytest -x && cd ..
	cd agent-circuit-breaker && python -m pytest -x && cd ..
	cd agent-chaos-toolkit && python -m pytest -x && cd ..
	cd agent-slo-platform && python -m pytest -x && cd ..
	cd dashboard && python -m pytest -x && cd ..
	cd agent-gateway && python -m pytest -x && cd ..
	cd agentops-sdk && python -m pytest -x && cd ..
	cd agentops-langchain && python -m pytest -x && cd ..

# The native engine is optional until M5. Install agent-circuit-breaker and
# agentops-engine before running this target.
test-engine:
	cd agentops-engine && python -m pytest -x

LINT_PATHS = agentops-core/src agentops-events/src agent-gateway/src \
	agent-circuit-breaker/src agent-chaos-toolkit/src agent-slo-platform/src \
	dashboard/src agentops-sdk/src agentops-langchain/src agentops-engine/src

lint:
	ruff check $(LINT_PATHS)

format-check:
	black --check $(LINT_PATHS)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name \*.egg-info -exec rm -rf {} + 2>/dev/null || true
