SHELL = /bin/bash

.PHONY: setup test lint check release restview

# First time setup - run this after cloning
setup:
	uv sync
	uv run pre-commit install

test:
	uv run pytest tests/ -v --cov=dedup --cov-report=term-missing

lint:
	uv run ruff check . --fix
	uv run ruff format .
	uv run mypy dedup --ignore-missing-imports

# Run all checks (same as pre-commit)
check:
	uv run pre-commit run --all-files

release:
	bump2version --verbose $${PART:-patch}
	git push
	git push --tags

restview:
	restview README.rst -w README.rst
