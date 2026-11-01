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

# The test suite needs the runtime SDKs importable (run_eval imports openai),
# PyYAML for the policy-manifest tests, and Pillow for the OG-card tests.
PYTEST ?= $(UVX) --with openai==3.42.0 \
	--with pyyaml==6.0.2 \
	--with pillow==13.0.0 \
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
	test coverage security safety-lint deps flags docs skills-check release alerts labels build \
	install-hooks lock

verify: check test security deps flags docs skills-check safety-lint

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

security: safety-lint
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

# Skill-tree structural validator: front matter, Safety Override, dimension
# matrix, dose arc, router alias resolution. Source of truth for the skill
# schema; see bin/check_skills.py --new-skill for the authoring checklist.
skills-check:
	$(PYTHON) bin/check_skills.py

# Content-safety lint: forbidden dose+verb, schedule/posology, therapy-claim
# and sourcing patterns over skills/**/*.md AND the built site/index.html
# (not the template). Allowlist contract documented in bin/safety_lint.py;
# tests in tests/unit/test_safety_lint.py prove the defeat guard.
safety-lint:
	$(PYTHON) bin/safety_lint.py

alerts:
	$(PY_YAML) bin/check_alerts.py --validate-only

release:
	$(PYTHON) bin/release_notes.py

labels:
	$(PY_YAML) bin/sync_labels.py --dry-run

# The build renders the OG share cards (altered_states/og.py uses Pillow). The
# committed site/og/*.png bytes are the output of the PINNED pillow==13.0.0 (the
# pip-audit-clean line chosen in bin/requirements.txt), not the ambient
# interpreter's Pillow, so the build env pins Pillow the same way the test env
# (PYTEST above) does. A rebuild under any other Pillow version produces
# different bytes and fails tests/unit/test_og_cards.py's committed-blob test.
BUILD_PY ?= $(UVX) --with pillow==13.0.0 $(PYTHON)

build:
	$(BUILD_PY) build.py

install-hooks:
	$(UVX) pre-commit@4.7.0 install

# Regenerate the hash-pinned lock files after editing a requirements.txt.
# bin/requirements.lock resolves for 3.11 (the oldest interpreter any consumer
# of it installs on — CI test matrix and the labels/alerts jobs are all 3.11+):
# the OG-card dependency Pillow 13 (the pip-audit-clean line) requires >= 3.11.
lock:
	$(UVX) uv pip compile bin/requirements.txt -o bin/requirements.lock \
		--python-version 3.11 --universal --generate-hashes --quiet
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
