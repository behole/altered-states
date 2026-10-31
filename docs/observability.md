# Observability

How to tell whether this project is working, without reading the code.

There is no metrics server and no long-running service. Signals are written to
disk by whatever process just ran, and CI evaluates them. That keeps the whole
pipeline inspectable with `cat` and `git diff`.

## The three signals

### 1. Structured logs

Every entry is one JSON object on stderr:

```json
{"ts": "2026-04-22T17:46:13.926+00:00", "level": "INFO", "event": "build.complete",
 "service": "altered-states", "trace_id": "build-e40a7d65", "duration_ms": 41.2,
 "size_bytes": 255484, "cycles": 3482, "experiments": 9, "music_experiments": 4}
```

- `event` is a dotted name: `build.start`, `build.journals_loaded`,
  `eval.retry`, `metrics.flush`.
- `trace_id` correlates every line from one run. `build-…` for a site build,
  `eval-…` for an eval sweep.
- Secrets are redacted by field name and by value shape. A redaction increments
  `secret_redactions`, which is itself an alerting signal.

Read them:

```bash
python3 build.py 2>&1 >/dev/null | jq -r 'select(.event) | "\(.trace_id) \(.event)"'
```

### 2. Metrics

A Prometheus textfile, rewritten on every flush:

```
runtime/metrics/altered-states.prom
experiments/temporal-lab/runtime/metrics/altered-states.prom
```

| Series | Type | Meaning |
|---|---|---|
| `altered_states_build_runs` | counter | successful site builds |
| `altered_states_build_duration_seconds` | histogram | build wall time |
| `altered_states_cycles_generated` | gauge | temporal cycles in the last build |
| `altered_states_llm_calls{status,substance}` | counter | model calls by outcome |
| `altered_states_llm_tokens{direction}` | counter | tokens in and out |
| `altered_states_llm_latency_seconds` | histogram | per-call latency |
| `altered_states_secret_redactions{kind}` | counter | secrets scrubbed from output |

The same values appear in the `metrics.flush` log event, keyed identically, so a
number can be traced from the log line to the textfile.

Because it is a textfile, any collector can scrape it (`node_exporter`'s
textfile collector, `prometheus` with a file SD) and any consumer can read it
without one. `make build` writes it; nothing needs to be running.

### 3. Errors

Sentry, but only when `SENTRY_DSN` is set. Without it every call
(`init_error_tracking`, `breadcrumb`, `capture_exception`) is a no-op, and
failures still show up as `build.failed` / `eval.retry` log events.

When it is enabled: `service`, `release`, and `environment` tags, breadcrumbs
for each pipeline step, and `trace_id` attached to breadcrumb data so a Sentry
event points at the log lines that produced it. `send_default_pii` is off.

## Alerting

Thresholds are a file, not a dashboard:

```yaml
# alerts/alerts.yaml
- name: build-not-running
  signal: altered_states_build_runs
  comparison: "<"
  threshold: 1
  severity: critical
  runbook: runbooks/site-build-failure.md
```

Evaluate locally:

```bash
make alerts                                            # policy is valid
uvx --with pyyaml==6.0.2 python bin/check_alerts.py \
  --snapshot runtime/metrics/altered-states.prom       # evaluate now
```

The `alerts` workflow runs the same evaluation every 30 minutes, carries
consecutive-fire counts in `--state` so one noisy sample does not page anyone,
and posts to `ALERT_WEBHOOK_URL` when a critical alert fires. Every alert must
name a runbook that exists — the validator fails the build otherwise.

## Deploy observability

| Question | Where to look |
|---|---|
| What is production serving? | `curl -s https://altered-states.pages.dev \| grep -o '[0-9]* temporal cycles'` |
| Did the cron deploy run? | `/tmp/site-rebuild.log` |
| Did the CI deploy run? | GitHub Actions → `CI` → the run for that commit |
| What did Pages build? | Cloudflare dashboard → Pages → the deployment |
| Which commit is live? | `git log -1 --format=%H` against the Pages deployment SHA |

The two deploy paths (cron rebuild on a maintainer's machine, and Actions on
push) are documented in `runbooks/deploy-failure.md`. If production is stale,
establish which one should have run before changing anything.

## What is deliberately not instrumented

- **No user tracking.** There are no users, no sessions, and no cookies. The
  page has no analytics script.
- **No request metrics.** The site is static files; the CDN reports them.
- **No always-on exporter.** Metrics are written on flush, not served. A sample
  is a snapshot of the last process that ran, which is the honest granularity
  for a batch pipeline.
