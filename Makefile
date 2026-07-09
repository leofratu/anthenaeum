.PHONY: test lint typecheck check help

help:
	@echo "make test       - run pytest"
	@echo "make lint       - ruff check"
	@echo "make typecheck  - compileall (syntax gate)"
	@echo "make check      - lint + typecheck + test"

test:
	python3 -m pytest tests -q

lint:
	python3 -m ruff check athenaeum tests

typecheck:
	python3 -m compileall -q athenaeum tests

check: lint typecheck test
