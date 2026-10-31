# Runbook: deploy failure

The build is fine, but the wrong thing is live.

## Symptom

- `altered-states.pages.dev` (or the custom domain) serves an old page.
- The cron rebuild logged `Push failed`.
- A pull request merged but nothing changed in production.

## How deploys actually work

There are two paths, and knowing which one should have run is half the fix:

1. **Cron rebuild.** `bin/rebuild-and-deploy.sh` runs on a schedule on the
   maintainer's machine: rebuild → commit `site/` → push to `main`. If the site
   content changed, this is the path.
2. **GitHub Actions → Cloudflare Pages.** A push to `main` triggers the Pages
   build, which serves `site/`.

So a stale site means either the cron never ran, or the push failed, or Pages
failed to build.

## Confirm

```bash
tail -50 /tmp/site-rebuild.log          # cron path
gh run list --workflow=CI --limit 5     # Actions path
```

Then check what production is actually serving:

```bash
curl -s https://altered-states.pages.dev | grep -o '[0-9]* temporal cycles' | head -1
```

Compare with the committed page:

```bash
grep -o '[0-9]* temporal cycles' site/index.html | head -1
```

## Stop the bleeding

If production is serving something broken and the committed page is good,
re-deploy from the known-good commit:

```bash
git checkout <good-sha> -- site/index.html
git commit -m "revert(site): redeploy known-good page"
git push origin main
```

If the committed page is *also* bad, fix forward: run the build locally with the
data present, verify, commit.

## Find the cause

| Log line | Cause | Fix |
|---|---|---|
| `Push failed` | branch protection rejects the cron's direct push, or credentials expired | see below |
| `No site changes to push` every run | the build is not picking up new data | check the data directory the build reads |
| `wrangler is not installed` | `watch.py deploy()` ran on a machine without the CLI | install wrangler, or rely on the Actions deploy |
| Pages build failed | the artifact is missing or oversized | read the Pages build log; check `site/` size |

**Branch protection vs. the cron push.** `main` is protected: required status
checks must pass and changes arrive through a pull request. The cron script
therefore pushes to `chore/site-autorebuild` and arms `gh pr merge --auto`, so
the pull request merges itself once CI is green. If auto-merge could not be
armed, the pull request is open and waiting — merge it by hand after reading the
failure. Do not disable protection on `main` to make a deploy go through.

## Verify

```bash
curl -s https://altered-states.pages.dev | grep -c '</html>'   # must be 1
curl -s https://altered-states.pages.dev | grep -o '[0-9]* temporal cycles' | head -1
```

## Write it down

Record which of the two deploy paths failed. If both can fail independently,
say so in `docs/research-pipeline.md` so the next person does not debug the
wrong one.
