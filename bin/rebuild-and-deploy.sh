#!/bin/bash
# Rebuild site and auto-push to GitHub if content changed.
# Cron target — picks up new journal entries and deploys to CF Pages.

set -e

REPO="/Users/jjoosshhmbpm1/DOX_ICE/altered-states"
LOG="/tmp/site-rebuild.log"
cd "$REPO"

echo "=== $(date) ===" >> "$LOG"

# 1. Rebuild site
python3 build.py >> "$LOG" 2>&1

# 2. Check if site/ has changes
if git diff --quiet site/ 2>/dev/null && git diff --cached --quiet site/ 2>/dev/null; then
    echo "No site changes to push" >> "$LOG"
    exit 0
fi

# 3. Commit and push
git add site/
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
git commit -m "chore(site): auto-rebuild $TIMESTAMP" >> "$LOG" 2>&1

if git push origin main >> "$LOG" 2>&1; then
    echo "Pushed to GitHub" >> "$LOG"
else
    echo "Push failed" >> "$LOG"
    exit 1
fi
