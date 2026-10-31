# Quality gate for the Python surfaces of this repo.
#
#   make verify         # everything CI runs: quality + tests + security + site
#   make check          # static analysis only (lint, format, types, dead code)
#   make test           # unit + integration tests, parallel
#   make coverage       # tests with the enforced coverage floor
#   make security       # bandit + pip-audit
#   make deps           # deptry (unused/missing/transitive dependencies)
#   make build          # regenerate site/index.html
#
# Tool versions match requirements-dev.txt / .pre-commit-config.yaml so local
# runs, hooks, and CI all agree.

UVX ?= uvx
PYTHON ?= python3

RUFF ?= $(UVX) ruff@0.14.4
MYPY ?= $(UVX) --with types-requests==2.33.0.20261030 --with types-pyyaml==6.0.12.20261030 \
	--from mypy@1.18.2 mypy
VULTURE ?= $(UVX) vulture@2.16
PYLINT ?= $(UVX) pylint@4.1.3
DEPTRY ?= $(UVX) deptry@0.25.1
BANDIT ?= $(UVX) bandit@1.9.4
PIP_AUDIT ?= $(UVX) pip-audit@2.10.1

# The test suite needs the runtime SDKs importable (run_eval imports anthropic)
# and PyYAML for the policy-manifest tests.
PYTEST ?= $(UVX) --with anthropic==2.3.0 \
	--with pyyaml==6.0.2 \
	--with pytest==9.2.0 \
	--with pytest-cov==7.1.0 \
	--with pytest-xdist==3.8.0 \
	--with pytest-rerunfailures==16.7 \
	pytest

PYLINT_TARGETS = build.py watch.py bin experiments
BANDIT_TARGETS = build.py watch.py altered_states bin experiments

# Repository automation that reads the YAML policy files.
PY_YAML = $(UVX) --with pyyaml==6.0.2 python

# pip-audit needs a real environment to inspect. `python -m venv` does not work
# in every sandbox (ensurepip can be blocked), so build the throwaway venv with
# uv, which seeds pip itself, then point pip-audit at its site-packages.
AUDIT_VENV ?= $(CURDIR)/.audit-venv
AUDIT_LOCKFILES = bin/requirements.lock experiments/music/requirements.lock experiments/temporal-lab/requirements.lock

.PHONY: verify check lint format format-check types dead-code duplicates \
	test coverage security deps flags docs release alerts labels build \
	install-hooks lock

verify: check test security deps flags docs

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

test:
	$(PYTEST)

coverage:
	$(PYTEST) --cov --cov-report=term-missing --cov-report=xml

security:
	$(BANDIT) --quiet -c pyproject.toml -r $(BANDIT_TARGETS)
	@rm -rf $(AUDIT_VENV)
	@$(UVX) uv venv $(AUDIT_VENV) --python 3.11 -q
	@$(UVX) uv pip install --python $(AUDIT_VENV)/bin/python -q \
		$(foreach lock,$(AUDIT_LOCKFILES),-r $(lock))
	@$(PIP_AUDIT) --path $(AUDIT_VENV)/lib/python3.11/site-packages
	@rm -rf $(AUDIT_VENV)

deps:
	$(DEPTRY) .

flags:
	$(PYTHON) -m altered_states.feature_flags check

docs:
	$(PYTHON) bin/check_agents_md.py

alerts:
	$(PY_YAML) bin/check_alerts.py --validate-only

release:
	$(PYTHON) bin/release_notes.py

labels:
	$(PY_YAML) bin/sync_labels.py --dry-run

build:
	$(PYTHON) build.py

install-hooks:
	$(UVX) pre-commit@4.7.0 install

# Regenerate the hash-pinned lock files after editing a requirements.txt.
lock:
	$(UVX) uv pip compile bin/requirements.txt -o bin/requirements.lock \
		--python-version 3.10 --universal --generate-hashes --quiet
	$(UVX) uv pip compile experiments/music/requirements.txt \
		-o experiments/music/requirements.lock \
		--python-version 3.10 --universal --generate-hashes --quiet
	$(UVX) uv pip compile experiments/temporal-lab/requirements.txt \
		-o experiments/temporal-lab/requirements.lock \
		--python-version 3.10 --universal --generate-hashes --quiet
	$(UVX) uv pip compile requirements-dev.txt -o requirements-dev.lock \
		--python-version 3.11 --universal --generate-hashes --quiet
	$(UVX) uv pip compile requirements-test.txt -o requirements-test.lock \
		--python-version 3.10 --universal --generate-hashes --quiet
