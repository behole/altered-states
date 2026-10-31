## What changed

<!-- One or two sentences. What is different after this pull request? -->

## Why

<!-- The problem or the goal. Link an issue if there is one: Fixes #123 -->

## How to verify

<!--
Commands a reviewer can run. Delete the ones that do not apply.
-->

- [ ] `make check` passes
- [ ] `make test` passes
- [ ] `make build` regenerates `site/index.html` without placeholder markup

## Checklist

- [ ] Tests cover the behaviour that changed (not just the lines)
- [ ] No new dependency without a pinned version and a lockfile refresh (`make lock`)
- [ ] New user-visible behaviour is behind a flag in `feature_flags.json`
- [ ] Documentation updated if behaviour or commands changed (`README.md`, `AGENTS.md`, `runbooks/`)
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]` for user-facing changes
- [ ] No secrets, tokens, or personal data in the diff or the logs it emits

## Risk and rollback

<!--
What breaks if this is wrong, and how do we undo it? For a site-only change,
"revert and redeploy" is a fine answer. For anything touching the lab runtime,
name the affected data files.
-->
