# Site Deploy

The site (`site/index.html`) is a **generated artifact** and is **not committed
to git** (it's in `.gitignore`). It is built locally and deployed to Cloudflare
Pages via wrangler direct-upload.

## Why not build in CI?

`build.py` renders `site/index.html` from:

- `experiments/temporal-lab/runtime/journals/*.json` — **local-only, gitignored**
  runtime state (the temporal-lab characters' journals)
- `experiments/same-prompt/output/*.md` — committed
- `experiments/music/**` — committed

Because the journals live only on the machine that runs the temporal-lab loop
and are deliberately gitignored, a build from a fresh checkout (e.g. a CI runner
or Cloudflare's Git integration) would render an empty temporal-lab section. So
the build must run where the journals exist.

## How it deploys

Local build + direct upload to the Cloudflare Pages project `altered-states`:

```bash
python3 build.py
wrangler pages deploy site --project-name altered-states --commit-dirty=true
```

- **Cron:** `bin/rebuild-and-deploy.sh` runs this on a schedule, skipping the
  upload when the built output hasn't changed (sha compared against
  `/tmp/altered-states-site.hash`).
- **Watch/dev:** `python3 watch.py` rebuilds and redeploys on journal/experiment
  changes and serves a local preview on `:8765`.
- **One-shot:** `python3 watch.py --build`.

## Requirements

- `wrangler` on PATH, authenticated to the Cloudflare account that owns the
  `altered-states` Pages project (`wrangler login`, or a `CLOUDFLARE_API_TOKEN`
  with Pages edit scope).
- Cloudflare Pages **Git integration should be off** for this project — deploys
  come from wrangler direct-upload, not from pushes to `main`. (If Git
  integration is left on with no build command, it would try to serve the repo
  as-is and 404 on the un-committed `index.html`.)
