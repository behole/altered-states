"""Per-substance cadence — how often each character should fire a cycle.

Each substance fires at an interval that loosely matches the *narrative
spacing between trips* — not the real dose duration (which would mean
salvia firing every 10 minutes and producing too much noise to read).

Adjust freely. Cron should run frequently (every 15 min recommended) and
the dispatcher decides which characters are due.
"""

from datetime import datetime, timedelta
from pathlib import Path
import json

# Minutes between cycles per substance.
# Faster = more frequent voice. Slower = more weight per cycle.
CYCLE_MINUTES: dict[str, int] = {
    "5-meo-dmt": 60,    # 2-20 min real arc, but heavy — once an hour
    "dmt":       60,    # 10-20 min real arc — once an hour
    "salvia":    60,    # 5-15 min real arc, dysphoric — once an hour
    "ketamine":  120,   # 30-60 min IV — twice an hour ish, slowed to 2hr
    "psilocybin": 360,  # 4-6 hr arc — every 6 hr
    "mdma":      360,   # 3-5 hr arc — every 6 hr
    "ayahuasca": 720,   # 4-6 hr arc, ceremonial — twice a day
    "lsd":       720,   # 8-12 hr arc — twice a day
    "mescaline": 720,   # 10-14 hr arc — twice a day (was: 12hr)
    "ibogaine":  1440,  # 12-24 hr arc, demanding — once a day
}

# How many recent journal entries to feed back into the next cycle as memory.
# Larger = more continuity, more tokens. Smaller = cheaper, more drift.
JOURNAL_HISTORY_DEPTH = 3


def cycle_minutes(substance: str) -> int:
    """Default: 6 hours if substance not in table."""
    return CYCLE_MINUTES.get(substance, 360)


def is_due(character: dict, now: datetime | None = None) -> bool:
    """Has enough time passed since this character's last cycle?"""
    now = now or datetime.now()
    last = character.get("last_cycle")
    if not last:
        return True  # never run — always due
    last_dt = datetime.fromisoformat(last)
    interval = timedelta(minutes=cycle_minutes(character["substance"]))
    return (now - last_dt) >= interval


def next_cycle_at(substance: str, from_time: datetime | None = None) -> str:
    """Compute next-cycle ISO timestamp from `from_time` (default now)."""
    base = from_time or datetime.now()
    return (base + timedelta(minutes=cycle_minutes(substance))).isoformat()


def due_characters(characters_dir: Path, now: datetime | None = None) -> list[dict]:
    """Return all characters whose next_cycle is due."""
    out = []
    for f in sorted(characters_dir.glob("*.json")):
        with open(f) as fh:
            char = json.load(fh)
        if is_due(char, now):
            out.append(char)
    return out
