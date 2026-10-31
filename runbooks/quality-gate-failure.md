# Runbook: quality gate failure

CI is red and it is not obvious what broke.

## Symptom

A job in the `CI` workflow fails on a pull request that "only touched one
file", or on `main` with no obvious change.

## Confirm which gate and which file

Every gate names the file it objects to. Read the failing step before reading
the code.

```bash
gh run list --workflow=CI --limit 3
gh run view <run-id> --log-failed | head -40
```

Reproduce locally — each gate maps to one command:

| Failing step | Local command |
|---|---|
| Lint (ruff) | `make lint` |
| Format | `make format-check` (or `make format` to fix) |
| Types (mypy --strict) | `make types` |
| Dead code (vulture) | `make dead-code` |
| Duplicate code | `make duplicates` |
| Unused deps (deptry) | `make deps` |
| Feature flags | `make flags` |
| Tests | `make test` |
| Coverage floor | `make coverage` |
| Bandit | `make security` |
| AGENTS.md | `python bin/check_agents_md.py` |

## Stop the bleeding

Order matters: fix lint and format first, because they change line numbers and
make every other failure harder to read.

```bash
make format        # safe, mechanical
make lint          # then fix what remains by hand
```

Do **not** stop the bleeding by adding an ignore. An ignore that survives review
is worse than a red build.

## Find the cause, by gate

**ruff** — a real finding or a stale `# noqa`. Remove the `noqa` first; if the
finding is legitimate, fix the code. Only add `noqa` with a specific code and a
comment saying why the rule does not apply here.

**mypy** — strict mode rejects untyped dicts and `Any` leaking out of a
function. Annotate the boundary. `ignore_missing_imports` is already on for the
provider SDKs; anything else is your code.

**vulture** — something is defined and never used. Either it is dead (delete
it) or it is used only through a framework hook (add it to `ignore_names` in
`pyproject.toml` with a comment).

**pylint duplicate-code** — two blocks of twelve or more lines are the same
logic. Extract a function. If the duplication is deliberate (two experiments
that must stay independently readable), say so and lower the trigger for that
path.

**deptry** — an import that is not declared, or a declared package nobody
imports. The second is usually a leftover in `requirements.txt`; delete it.

**Tests** — run the failing file alone, without the parallel scheduler, to see
the real traceback:

```bash
pytest tests/unit/test_whatever.py -n0 --reruns 0 -x
```

**Coverage floor** — new code without tests. Write them; do not move
`fail_under` down.

**Flaky test** — the suite retries once (`--reruns 1`). A test that only passes
on retry is marked flaky and needs fixing, not a higher retry count. Look for
shared mutable state, wall-clock dependence, or filesystem writes outside
`tmp_path`.

## Verify

```bash
make verify
pre-commit run --all-files
```

Both must pass on the committed tree, not just on your working tree.

## Write it down

If a gate produced a false positive, the fix is to the gate's configuration,
committed with a comment explaining the case — never a silent loosening. If a
gate caught something real that the tests did not, the missing test is the
actual deliverable.
