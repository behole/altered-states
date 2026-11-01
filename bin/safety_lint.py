#!/usr/bin/env python3
"""Content-safety lint for the Altered States skill content and built site.

Stdlib-only, offline. Scans:

  * every Markdown file under skills/** (SKILL.md files, overlay lines,
    consistency matrix, tolerance README), and
  * the BUILT site/site_index (default site/index.html — never
    site/index.template.html, which is not what ships; forbidden text in
    the template means nothing until a build would push it to the reader).

for four families of forbidden patterns, each tied to SAFETY.md terminology:

  dose-verb       a dose figure (mg/g/mcg/ug) in the same line as a dosing
                  verb (take/ingest/consume/…) — text that reads as usable
                  dosing advice. SAFETY.md: no dosing practical instructions,
                  only phenomenology and quoted research figures.
  schedule        dosing-schedule / posology phrasing ("every N days",
                  "wait N hours"). SAFETY.md: no recovery regimens.
  therapy         therapy/guidance claims in instruction voice ("therapeutic
                  benefit", "used to treat depression", "integration
                  practice"). SAFETY.md: no therapy/treatment claims.
  sourcing        sourcing-language slips ("where to buy", "darknet",
                  ".onion", duck/viating vendor slang). SAFETY.md: no sourcing.
  forbidden-word  the bare-word grep used project-wide: protocol|schedule|
                  regimen|posology. Findings are governed by the allowance
                  chain below rather than by blanket exception.

Every finding names FILE:LINE and shows the matched line. Exit codes:
0 = clean, 1 = findings, 2 = usage/missing-input error (e.g. the built site
is absent so only a partial scan happened).

Allowlist mechanism (the designed whitelist, per orchestrator notes and
VAL-TOOL-003/004):

1. Inline scoped allow. An HTML comment on the line immediately ABOVE a
   matched line scopes the suppression:

      <!-- safety-lint: allow: forbidden-word -- reason: historical phrase,
           quoted not instructive -->

   Rules may be comma-separated; each comment must carry a reason string
   (>=6 chars after "--"), otherwise it suppresses nothing. DEFEAT GUARD
   (proven in tests/unit/test_safety_lint.py): the dose-verb rule is NEVER
   suppressible — by construction every dose-verb match contains a dose
   number, and an allow comment can not rescue a line carrying a forbidden
   pattern plus a number. "take 120 mg" fails even with an allow comment
   directly above it claiming to.

2. Refusal-context allowance. The overlay lines (combos, tolerance,
   afterglow) express their regimen/schedule bans AS refusal sentences,
   e.g. skills/afterglow/SKILL.md: "**No schedule, and no recovery
   arithmetic.**" A forbidden-word match inside a line that also contains
   an explicit refusal/negation marker (no, never, not, without, zero,
   refus*, prohibit*, decript*, "as description", banned, ...) is a
   documented non-finding. This is text-only: the allowance can never
   rescue dose-verb matches, which do not consult it.

3. Baseline allow phrases (hard-coded, each historical). A forbidden word
   inside one of these exact pre-existing phrases is a known false
   positive quoted from research literature:

      "Ineffability protocol"   (skills/psilocybin — mysticism literature term)
      "clinical protocol"       (skills/ketamine — quoted clinical setting)

   These phrases are the designed whitelist that lets the 11 base substance
   skills, 2 combo skills, 3 tolerance overlays, afterglow, and the router
   all produce zero findings while the dose-figure whitelist mechanism
   still keeps base-skill research citations (dose figures in quoted
   intensity headings, no verbs) distinct from genuine dosing advice.
   research/ is exempt from scanning entirely (never scanned here): dose
   figures in research/*/sources.md annotations (e.g. "22 mg/70 kg" in
   psilocybin) are factual clinical literature and never user guidance.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SKILLS_DIR = REPO / "skills"
DEFAULT_SITE = REPO / "site" / "index.html"

RULE_DOSE_VERB = "dose-verb"
RULE_SCHEDULE = "schedule"
RULE_THERAPY = "therapy"
RULE_SOURCING = "sourcing"
RULE_FORBIDDEN_WORD = "forbidden-word"

# Rules whose matches are never suppressible (see docstring: defeat guard).
# A dose-verb match always carries a dose number — exactly what the
# allowlist exists to NOT excuse.
NEVER_SUPPRESSIBLE = {RULE_DOSE_VERB}

# --- dose figure -----------------------------------------------------------
# number(s) with a mass unit; tolerates ranges ("1-1.5g") and decimals.
_DOSE_FIGURE = r"\d[\d.,\-\u2013\s]{0,10}\s?(?:mg|mcg|µg|ug|g)\b"

# dosing verbs (imperative force). The ambiguous noun "dose" is deliberately
# excluded so quoted research headings like
#   "### LOW (museum dose: ~1-1.5g / ~10mg)"
# stay findings-free; the verb list is words that read as instructions.
_VERB_FIRST = (
    r"take|taking|ingest(?:ing|ed)?|consume|administer(?:ing|ed)?"
    r"|swallow(?:ing|ed)?|snort(?:ing|ed)?|insufflate|dissolve|vaporize"
    r"|redose|re-dose"
)
_DOSE_VERB_VERB_FIRST = re.compile(rf"\b(?:{_VERB_FIRST})\b[^\n]{{0,40}}{_DOSE_FIGURE}", re.I)
_DOSE_VERB_FIGURE_FIRST = re.compile(rf"{_DOSE_FIGURE}[^\n]{{0,40}}\b(?:{_VERB_FIRST})\b", re.I)

# --- dosing schedule / posology ---------------------------------------------
_SCHEDULE_RE = re.compile(
    r"\b(?:every(?: other)?|repeat(?:ed|ing)?)\s+\d+[\d.\-\u2013]*\s*"
    r"(?:day|hour|week|month)s?\b"
    r"|\b(?:wait|waiting)\s+\d+[\d.\-\u2013]*\s*(?:day|hour|week|month)s?\b",
    re.I,
)

# --- therapy / guidance claims ----------------------------------------------
_THERAPY_RE = re.compile(
    r"\b(?:therapeutic benefit|effectively treats?|used? to treat(?:ment)?"
    r"|treats? (?:depression|anxiety|ptsd|bipolar|addiction|trauma)"
    r"|therapy (?:protocol|schedule|regimen)"
    r"|integration practice|practice integration)\b",
    re.I,
)

# --- sourcing-language slips -------------------------------------------------
_SOURCING_RE = re.compile(
    r"(?:where (?:can (?:i|you)|to)\s+(?:buy|get|source|obtain)"
    r"|darknet|\.onion\b|onion address|vendor list|sourcing guide"
    r"|\bduck\b)",
    re.I,
)

# --- bare forbidden-word grep (protocol|schedule|regimen, + posology) --------
_FORBIDDEN_WORD_RE = re.compile(r"\b(?:protocol|schedule|regimen|posology)\b", re.I)

# Baseline allow phrases: word matches inside these exact phrases are
# pre-existing, research-derived, and pre-date the lint (each historically
# tied to a specific base skill — see docstring).
_BASELINE_ALLOW_PHRASES = [
    "ineffability protocol",
    "clinical protocol",
]

# Refusal markers and the character window in which they must appear around
# the forbidden word for the refusal allowance to apply.
_REFUSAL_MARKER = re.compile(
    r"\b(?:no|never|not|without|zero|none|refus\S*|prohibit\S*"
    r"|forbid\S*|banned|descriptive|description|exempt|rather than|instead of)\b",
    re.I,
)
_REFUSAL_BEFORE = 60
_REFUSAL_AFTER = 40

# Inline allow comment, parsed for the rules it scopes.
_INLINE_ALLOW_RE = re.compile(
    r"safety-lint:\s*allow:\s*(?P<rules>[\w, -]+?)(?:\s*--\s*(?P<reason>[^>]*?))?\s*(?:-->|$)",
    re.I,
)
_MIN_REASON_LEN = 6

SITE_NOT_BUILT_HINT = (
    "built site target missing — run `make build` first so the lint scans what actually ships, not just sources."
)


class Finding:
    __slots__ = ("line", "path", "rule", "text")

    def __init__(self, path: Path, line: int, rule: str, text: str):
        self.path = path
        self.line = line
        self.rule = rule
        self.text = text

    def render(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.text[:180]}"


def _inline_allows(line: str) -> list[str] | None:
    """Returns the list of rules an inline allow comment on this line scopes.

    A malformed comment (missing reason) suppresses nothing rather than
    failing the build — the absence of suppression is the safe failure.
    """
    if "safety-lint: allow" not in line.lower():
        return None
    m = _INLINE_ALLOW_RE.search(line)
    if not m:
        return []
    reason = (m.group("reason") or "").strip()
    if len(reason) < _MIN_REASON_LEN:
        return []
    return [r.strip() for r in m.group("rules").split(",") if r.strip()]


def _matching_baseline(line: str) -> bool:
    lowered = line.lower()
    return any(p in lowered for p in _BASELINE_ALLOW_PHRASES)


def _refusal_allowed(line: str, match: re.Match[str]) -> bool:
    start, end = match.start(), match.end()
    for m in _REFUSAL_MARKER.finditer(line.lower()):
        if start - _REFUSAL_BEFORE <= m.start() <= end + _REFUSAL_AFTER:
            return True
    return False


def iter_finding_lines(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    allow_next: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        allows_here = allow_next
        allow_next = _inline_allows(line) or []

        def allowed(rule: str, _scoped: list[str] = allows_here) -> bool:
            return rule not in NEVER_SUPPRESSIBLE and rule in _scoped

        if _SCHEDULE_RE.search(line) and not allowed(RULE_SCHEDULE):
            findings.append(Finding(path, i, RULE_SCHEDULE, line.strip()))
        if _THERAPY_RE.search(line) and not allowed(RULE_THERAPY):
            findings.append(Finding(path, i, RULE_THERAPY, line.strip()))
        if _SOURCING_RE.search(line) and not allowed(RULE_SOURCING):
            findings.append(Finding(path, i, RULE_SOURCING, line.strip()))
        # Dose-verb rules always report: they are never suppressible (see
        # defeat guard in the docstring) and never consult the refusal
        # allowance (the refusal allowance is textual, dose-verb matches are
        # numeric-bearing and never textually excused).
        for pattern in (_DOSE_VERB_VERB_FIRST, _DOSE_VERB_FIGURE_FIRST):
            m = pattern.search(line)
            if m:
                findings.append(Finding(path, i, RULE_DOSE_VERB, m.group(0).strip()))
                break
        m = _FORBIDDEN_WORD_RE.search(line)
        if m and not allowed(RULE_FORBIDDEN_WORD) and not _matching_baseline(line) and not _refusal_allowed(line, m):
            findings.append(Finding(path, i, RULE_FORBIDDEN_WORD, line.strip()))
    return findings


def scan_file(path: Path) -> list[Finding]:
    return iter_finding_lines(path, path.read_text(encoding="utf-8"))


def collect_skills_findings(skills_dir: Path) -> list[Finding]:
    out: list[Finding] = []
    for path in sorted(skills_dir.rglob("*.md")):
        out.extend(scan_file(path))
    return out


def _scan_built_outputs(site: Path | None, extras: list[Path], findings: list[Finding]) -> tuple[int, list[str]]:
    """Scans the built site (if requested and present) and extra targets.

    Returns (status, notes): status 2 marks an input error (a scan surface
    is missing — the run must not silently count as a full pass).
    """
    status, notes = 0, []
    if site is not None:
        if site.exists():
            findings.extend(scan_file(site))
        else:
            notes.append(f"site={site}: {SITE_NOT_BUILT_HINT}")
            status = 2
    for extra in extras:
        if not extra.exists():
            notes.append(f"extra={extra}: not found")
            status = 2
            continue
        findings.extend(scan_file(extra))
    return status, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Content-safety lint: scans skills Markdown and the built site for forbidden patterns.",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help="root of the Markdown content to lint (default: skills/)",
    )
    parser.add_argument(
        "--site",
        type=Path,
        default=DEFAULT_SITE,
        help="built site file to scan (default: site/index.html)",
    )
    parser.add_argument(
        "--extra",
        type=Path,
        action="append",
        default=[],
        help="additional file to scan (repeatable)",
    )
    parser.add_argument(
        "--no-site",
        action="store_true",
        help="skip the built-site scan (skills-only pass)",
    )
    args = parser.parse_args(argv)

    if not args.skills_dir.exists():
        print(f"safety-lint: skills dir not found: {args.skills_dir}", file=sys.stderr)
        return 2

    findings: list[Finding] = collect_skills_findings(args.skills_dir)
    site = None if args.no_site else args.site
    status, notes = _scan_built_outputs(site, args.extra, findings)
    for note in notes:
        print(f"warning: {note}", file=sys.stderr)
    for f in findings:
        print(f.render())

    if findings:
        print(
            f"safety-lint: {len(findings)} finding(s) — each names file:line. "
            "See the module docstring for the allowlist contract.",
            file=sys.stderr,
        )
        return 1
    scope = f"skills={args.skills_dir}"
    if site is not None:
        scope += f", site={site}"
    if args.extra:
        scope += f", extras={len(args.extra)}"
    print(f"safety-lint: clean ({scope})")
    return status


if __name__ == "__main__":
    sys.exit(main())
