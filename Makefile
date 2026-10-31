# Quality gate for the Python surfaces of this repo.
#
#   make check          # everything CI/pre-commit would run
#   make lint           # ruff lint
#   make format         # ruff format (writes)
#   make format-check   # ruff format --check
#   make types          # mypy --strict
#   make dead-code      # vulture
#   make duplicates     # pylint duplicate-code
#   make build          # regenerate site/index.html
#
# Tool versions match requirements-dev.txt / .pre-commit-config.yaml so local
# runs, hooks, and agents all agree.

UVX ?= uvx
PYTHON ?= python3

RUFF ?= $(UVX) ruff@0.14.4
MYPY ?= $(UVX) --with types-requests==2.33.0.20261030 --from mypy@1.18.2 mypy
VULTURE ?= $(UVX) vulture@2.16
PYLINT ?= $(UVX) pylint@4.1.3

PYLINT_TARGETS = build.py watch.py bin experiments

.PHONY: check lint format format-check types dead-code duplicates build install-hooks

check: lint format-check types dead-code duplicates

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

format-check:
	$(RUFF) format --check .

types:
	$(MYPY)

dead-code:
	$(VULTURE)

duplicates:
	$(PYLINT) --disable=all --enable=duplicate-code $(PYLINT_TARGETS)

build:
	$(PYTHON) build.py

install-hooks:
	$(UVX) pre-commit@4.7.0 install
