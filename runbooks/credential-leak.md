# Runbook: credential leak

A key, token, or password is somewhere it should not be.

Treat this as urgent even if you are not sure. Rotating a key that was never
exposed costs five minutes; the alternative costs a lot more.

## Symptom

- A pull request review reports "added line contains what looks like a …".
- A log line shows a full key instead of `***REDACTED***`.
- `git log -S` finds a key in history.
- A provider emails you about unusual usage.

## Confirm the blast radius

Where did it go? Each answer changes the response:

```bash
# Working tree and the last commit
git grep -nE 'sk-(ant-|or-)?[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}' HEAD

# Full history (slow, but the only honest answer)
git log --all -S 'sk-ant-' --oneline

# Local log and ledger files that are not in git
grep -rIl 'sk-ant-\|ghp_\|AKIA' experiments/*/runtime/ runtime/ 2>/dev/null
```

If the answer is "only in an unpushed local file", you are in the easy case.

## Stop the bleeding

**Rotate first, investigate second.** A rotated key makes the leak inert.

| Provider | Action |
|---|---|
| Anthropic | Revoke the key in the console, issue a new one |
| OpenRouter / OpenAI | Same |
| GitHub PAT | Settings → Developer settings → revoke; issue a replacement |
| Cloudflare | Roll the API token |
| AWS | Deactivate the access key, then delete it |

Then update wherever the key is consumed — the cron environment, the shell
profile, the CI secret store. Do **not** commit the new key.

## Clean up

1. **Unpushed or in the working tree.** Remove it, confirm with `git grep`, done.
2. **In a pushed commit on a branch.** Rewrite the branch, force-push with
   `--force-with-lease`, and note that anyone who fetched still has it.
3. **In `main`.** Rotation is the fix. Rewriting public history on `main` breaks
   every clone and the deploy cron, and does not un-leak anything — the key was
   already public. Rotate, then remove it from the current tree going forward.

Then make sure it cannot recur:

```bash
pre-commit run --all-files          # includes the same secret shapes
python bin/review_pr.py --diff-file <(git show HEAD) --fail-on never
```

## Verify

```bash
# The old key is dead:
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "x-api-key: $OLD_KEY" https://api.anthropic.com/v1/models   # expect 401

# The new key works, from the environment only:
python3 bin/run_eval.py --dry-run --substances lsd              # no key needed
```

Confirm no plaintext key exists in the tree or in the files the app writes:

```bash
grep -rIl 'sk-ant-\|ghp_\|AKIA' --exclude-dir=.git . | grep -v '^./tests/' || echo clean
```

## Write it down

If the leak came from your own code — a `print()`, a `repr()` in an f-string, a
log field named something the redactor does not know — add a case to
`tests/unit/test_log_utils.py` and extend `_SENSITIVE_KEYS` or `_SECRET_VALUES`
so the next one is caught automatically. A runbook entry alone does not fix it.
