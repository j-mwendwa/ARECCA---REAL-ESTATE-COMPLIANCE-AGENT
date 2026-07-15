.PHONY: install dev test lint format serve clean

install:
	pip install -e ".[dev]"

dev:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

serve:
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --asyncio-mode=auto

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
