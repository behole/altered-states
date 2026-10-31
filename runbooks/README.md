# Runbooks

What to do when something breaks, written for the person who gets woken up —
which is the same person who wrote the code, six months later.

Every runbook follows the same shape: **symptom → confirm → stop the bleeding →
find the cause → verify → write it down**.

| Runbook | Use when |
|---|---|
| [site-build-failure.md](site-build-failure.md) | `build.py` exits non-zero, or the page is missing content |
| [deploy-failure.md](deploy-failure.md) | Cloudflare Pages is serving a stale or broken site |
| [lab-runtime-failure.md](lab-runtime-failure.md) | Temporal-lab cycles stop running, or the ledger looks wrong |
| [credential-leak.md](credential-leak.md) | A key appears in a log, a commit, or a PR |
| [quality-gate-failure.md](quality-gate-failure.md) | CI is red and it is not obvious which change broke it |

## Where the signals live

| Signal | Location |
|---|---|
| Structured logs | stderr of `build.py` / `run_eval.py` / lab scripts, JSON lines with `trace_id` |
| Metrics snapshot | `runtime/metrics/altered-states.prom` (Prometheus textfile), lab equivalent under `experiments/temporal-lab/runtime/metrics/` |
| Metrics in logs | the `metrics.flush` event payload, keyed by series name |
| Errors | Sentry, only when `SENTRY_DSN` is set; otherwise the `build.failed` / `eval.retry` log events |
| Alert thresholds | `alerts/alerts.yaml`, evaluated by `python bin/check_alerts.py` |
| Deploy log | Cloudflare Pages build log, and `/tmp/site-rebuild.log` for the cron path |
| CI | GitHub Actions, workflow `CI` |

## The first three commands for anything

```bash
python -m altered_states.feature_flags check    # is a flag off or expired?
python bin/check_alerts.py --snapshot runtime/metrics/altered-states.prom
git log --oneline -10
```

A surprising share of incidents are one of those three.
