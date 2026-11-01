#!/usr/bin/env python3
"""Skill validator for the Altered States skill tree.

Stdlib-only, offline. Validates every SKILL.md in skills/ — top-level
substances, the router, and the nested overlay lines (skills/combos/*,
skills/tolerance/*) — against the structural contract documented at the
bottom of --help ("--new-skill" prints the same rules as an authoring
checklist).

Usage:
    python3 bin/check_skills.py                 # validate the whole tree
    python3 bin/check_skills.py --skills-dir X  # validate a copied tree
    python3 bin/check_skills.py --new-skill P   # authoring checklist for a new skill

Exit codes: 0 = all skills valid, 1 = validation failures, 2 = usage error.

Every failure names the file AND the failing section, plus the fix. The
canonical reference structure is skills/psilocybin/SKILL.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SKILLS_DIR = REPO / "skills"

# Section names the rules cite (single source for checks and the checklist).
SEC_FRONTMATTER = "front matter"
SEC_OVERRIDE = "Safety Override — Read First"
SEC_DIMENSIONS = "7 Phenomenological Dimensions table"
SEC_INTENSITY = "Intensity Profiles / Intensity Levels"
SEC_DOSE_ARC = "Dose Arc"

# Break conditions every Safety Override must carry (checked by keyword).
OVERRIDE_CONDITION_KEYWORDS = [
    "suicidal ideation",
    "psychosis",
    "substance emergency",
    "acute distress",
    "dosage, sourcing, combinations, or interactions",
]
OVERRIDE_RESOURCE_KEYWORDS = ["988", "741741", "not harm reduction"]

# Dimension category patterns: at least 6 of these must be stated somewhere
# in an intensity-profile section (files with the explicit table are
# validated row-by-row instead).
DIMENSION_PATTERNS = [
    ("Perceptual", r"perceptual|perception|sensory|visual|light|color"),
    ("Temporal", r"temporal|time|duration"),
    ("Cognitive", r"cognitive|thinking|analytical|thought|language"),
    ("Emotional", r"emotional|feeling|euphor|awe|reverence|terror"),
    ("Self/Ego", r"ego|self|identity|dissolution"),
    ("Mystical", r"mystical|entity|visionary|sacred|unity|meaning|source|formless"),
    ("Somatic", r"somatic|body|tactile"),
]

# Dose-figure units that must NEVER appear in overlay skills (combos,
# tolerance, afterglow): overlays are valid skills but not substances and
# carry zero dose figures by construction.
DOSE_UNIT = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|µg|ug)\b")

REQUIRED_DIMENSION_ROWS = 7
MIN_PROFILE_COVERAGE = 4
DIMENSION_NAMES = [
    "Perceptual",
    "Temporal",
    "Cognitive",
    "Emotional",
    "Self/Ego",
    "Mystical",
    "Somatic",
]


def fail(file: Path, section: str, problem: str, fix: str) -> str:
    """Format one failure: file + section + fix, in the authoring-guide voice."""
    return f"{file}: FAIL [{section}] {problem}\n    fix: {fix}"


class SkillFile:
    """One discovered SKILL.md plus its class (substance / overlay / router)."""

    def __init__(self, path: Path, skills_root: Path):
        self.path = path
        self.relpath = path.relative_to(skills_root.parent) if skills_root.name else path
        self.text = path.read_text(encoding="utf-8")
        parent = path.parent
        if path.parent.parent != skills_root:
            # skills/combos/candy-flip, skills/tolerance/<sub>: overlay line
            self.line: str | None = parent.parent.name
            self.slug = parent.name
        else:
            self.line = None
            self.slug = parent.name
        if self.slug == "router":
            self.kind = "router"
        elif self.line in ("combos", "tolerance") or self.slug == "afterglow":
            self.kind = "overlay"
        else:
            self.kind = "substance"

    # --- structural helpers -------------------------------------------------

    def heading_lines(self) -> list[tuple[str, str]]:
        out = []
        for line in self.text.splitlines():
            if line.startswith("#"):
                heading = line.lstrip("#").strip()
                out.append((line.split(" ")[0], heading))  # (level-marker, title)
        return out

    def has_heading(self, pattern: str) -> bool:
        return any(re.search(pattern, title, re.I) for _, title in self.heading_lines())

    def section_text(self, pattern: str) -> str | None:
        """Text from the first heading matching `pattern` to the next heading
        of the same-or-higher level (sub-levels included, so tables and
        intensity subsections under `###` stay inside the section)."""
        lines = self.text.splitlines()
        start = None
        level = 0
        for i, line in enumerate(lines):
            if not line.startswith("#"):
                continue
            heading = line.lstrip("#").strip()
            if re.search(pattern, heading, re.I):
                start = i
                level = len(line) - len(line.lstrip("#"))
                break
        if start is None:
            return None
        end = len(lines)
        for j in range(start + 1, len(lines)):
            line = lines[j]
            if line.startswith("#"):
                found_level = len(line) - len(line.lstrip("#"))
                if found_level <= level:
                    end = j
                    break
        return "\n".join(lines[start:end])


def parse_front_matter(text: str) -> tuple[dict[str, str], list[str]]:
    """Deterministic front-matter parser (no YAML dependency).

    Returns (field dict, problems). Handles the flat keys the schema
    requires: name, description (may be a folded `>` block), tags list,
    quoted version, author.
    """
    problems: list[str] = []
    fields: dict[str, str] = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return fields, ["file does not open with a `---` front-matter fence"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return fields, ["front-matter fence never closes (no second `---`)"]
    block = lines[1:end]

    current_key: str | None = None
    for line in block:
        if re.match(r"^\s+- ", line) or line.startswith("  "):
            if current_key:
                fields[current_key] += " " + line.strip()
            continue
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match:
            current_key = match.group(1)
            fields[current_key] = match.group(2)
    if not fields:
        problems.append("front matter carries no `key: value` pairs")
    return fields, problems


def check_front_matter(file: SkillFile) -> list[str]:
    problems: list[str] = []
    if file.kind == "router":
        # The router is a routing table, not a state: name/matrix rules differ.
        return _check_router_front_matter(file, problems)
    fields, parse_problems = parse_front_matter(file.text)
    for problem in parse_problems:
        problems.append(
            fail(
                file.path,
                SEC_FRONTMATTER,
                problem,
                "front matter must be a `---` fenced YAML-style header; see skills/psilocybin/SKILL.md lines 1-11",
            )
        )
    if not fields:
        return problems

    for key in ("name", "description", "tags", "version", "author"):
        if key not in fields:
            problems.append(
                fail(
                    file.path,
                    SEC_FRONTMATTER,
                    f"required key `{key}:` missing",
                    "add it to the front matter (schema: name/description/tags/version/author)",
                )
            )
    name = fields.get("name", "")
    if name and not name.strip().endswith("-altered-state"):
        problems.append(
            fail(
                file.path,
                SEC_FRONTMATTER,
                f"name `{name}` must end in `-altered-state`",
                "also required so the router's alias resolution can map it to a skill directory",
            )
        )
    version = fields.get("version", "")
    if version and not re.match(r'^"[0-9]+\.[0-9]+"$', version.strip()):
        problems.append(
            fail(
                file.path,
                SEC_FRONTMATTER,
                f"version `{version}` is not a quoted semver string",
                'use version: "1.5"-style (quoted, major.minor)',
            )
        )
    if fields.get("author", "behole").strip() != "behole":
        problems.append(
            fail(
                file.path,
                SEC_FRONTMATTER,
                "author must be `behole`",
                "all skills in this project are authored by behole",
            )
        )
    tags = fields.get("tags", "")
    if tags and "altered-states" not in tags:
        problems.append(
            fail(
                file.path,
                SEC_FRONTMATTER,
                "tags list must include `altered-states`",
                "project membership tag; see any existing skill's front matter",
            )
        )
    return problems


def check_safety_override(file: SkillFile) -> list[str]:
    section = file.section_text(r"^Safety Override")
    if not section:
        if file.kind == "overlay" and file.slug == "README":
            return []  # tolerated; README is a policy doc, not a skill
        return [
            fail(
                file.path,
                SEC_OVERRIDE,
                "section missing",
                "copy the Safety Override block from skills/psilocybin/SKILL.md (## Safety Override — Read First)",
            )
        ]
    problems = []
    if "overrides every other instruction" not in section:
        problems.append(
            fail(
                file.path,
                SEC_OVERRIDE,
                "override declaration missing (must say it overrides every other instruction)",
                "keep the bold opening line; weaken nothing — "
                "this is what makes the override beat the immersion directive",
            )
        )
    joined = section.lower()
    for keyword in OVERRIDE_CONDITION_KEYWORDS:
        if keyword.lower() not in joined:
            problems.append(
                fail(
                    file.path,
                    SEC_OVERRIDE,
                    f"break condition missing: '{keyword}'",
                    "all five break condition bullets must be present, verbatim in substance",
                )
            )
    for resource in OVERRIDE_RESOURCE_KEYWORDS:
        if resource.lower() not in joined:
            problems.append(
                fail(
                    file.path,
                    SEC_OVERRIDE,
                    f"crisis resource / harm-reduction statement missing: '{resource}'",
                    "keep the crisis-resource blockquote and the 'This is not harm reduction' line; see SAFETY.md",
                )
            )
    return problems


def _check_router_front_matter(file: SkillFile, problems: list[str]) -> list[str]:
    fields, parse_problems = parse_front_matter(file.text)
    for problem in parse_problems:
        problems.append(
            fail(
                file.path,
                SEC_FRONTMATTER,
                problem,
                "front matter must be a `---` fenced header; see the router's own lines 1-9",
            )
        )
    for key in ("name", "description", "tags", "version", "author"):
        if key not in fields:
            problems.append(
                fail(
                    file.path, SEC_FRONTMATTER, f"required key `{key}:` missing", "add it to the router's front matter"
                )
            )
    version = fields.get("version", "")
    if version and not re.match(r'^"[0-9]+\.[0-9]+"$', version.strip()):
        problems.append(
            fail(
                file.path,
                SEC_FRONTMATTER,
                f"version `{version}` is not a quoted semver string",
                'use version: "1.5"-style (quoted, major.minor)',
            )
        )
    return problems


def check_intensities_and_matrix(file: SkillFile) -> list[str]:
    """Matrix rule: either a fully-populated dimension table, or an intensity
    section whose prose covers the dimension space. Files with a table get
    the strict per-row check; without one, profile coverage is required."""
    if file.kind == "router":
        return []  # the router has no state matrix; its rules are alias checks

    intensity_section = file.section_text(r"^Intensity (Profiles|Levels|Ladder)")
    table_section = file.section_text(r"(7 Phenomenological Dimensions|Seven Dimensions)")
    if not intensity_section and not table_section:
        return [_fail_no_matrix(file)]

    if table_section:
        return _check_dimension_table(file, table_section)

    if intensity_section is None:  # unreachable; guards the mypy narrowing
        return []
    return _check_profile_coverage(file, intensity_section)


def _fail_no_matrix(file: SkillFile) -> str:
    return fail(
        file.path,
        SEC_INTENSITY,
        "no dimension matrix and no intensity profiles section",
        "every skill must carry either a '## The 7 Phenomenological Dimensions' "
        "table or an '## Intensity Profiles/Ladder' section; see the sibling skills",
    )


def _check_dimension_table(file: SkillFile, table_section: str) -> list[str]:
    rows: list[list[str]] = []
    for line in table_section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.match(r"^\d+$", cells[0]):
            rows.append(cells)
    problems: list[str] = []
    if len(rows) < REQUIRED_DIMENSION_ROWS:
        problems.append(
            fail(
                file.path,
                SEC_DIMENSIONS,
                f"dimension table has {len(rows)} numbered rows, expected 7",
                "all 7 dimensions must appear: Perceptual, Temporal, Cognitive, Emotional, Self/Ego, Mystical, Somatic",
            )
        )
    for row in rows:
        cells = row[1:]
        index = row[0]
        if any(cell == "" for cell in cells):
            which = DIMENSION_NAMES[int(index) - 1] if 1 <= int(index) <= len(DIMENSION_NAMES) else "?"
            problems.append(
                fail(
                    file.path,
                    SEC_DIMENSIONS,
                    f"row {index} ({which}) has an empty intensity cell",
                    "every dimension row must be populated in every intensity column",
                )
            )
    return problems


def _check_profile_coverage(file: SkillFile, intensity_section: str) -> list[str]:
    joined = intensity_section.lower()
    covered = [name for name, pattern in DIMENSION_PATTERNS if re.search(pattern, joined)]
    missing = [name for name, _ in DIMENSION_PATTERNS if name not in covered]
    if len(covered) < MIN_PROFILE_COVERAGE:
        return [
            fail(
                file.path,
                SEC_INTENSITY,
                f"intensity profile coverage too thin; missing {missing}",
                "profile-bulleted skills must still state each dimension per level "
                "(see skills/ketamine/SKILL.md Intensity Levels)",
            )
        ]
    return []


def check_dose_arc(file: SkillFile) -> list[str]:
    if file.kind == "router":
        return []
    if not file.has_heading(r"Dose Arc|Dose arc"):
        return [
            fail(
                file.path,
                SEC_DOSE_ARC,
                "no `## The Dose Arc` section",
                "add the arc with onset/ascent/peak/descent framing; see "
                "skills/psilocybin/SKILL.md '## The Dose Arc — Onset Rules'",
            )
        ]
    return []


def check_safety_bar(file: SkillFile) -> list[str]:
    """Overlay skills (combos/tolerance/afterglow) are valid but not
    substances: they carry zero dose figures by construction."""
    if file.kind != "overlay":
        return []
    hits = [match.group(0) for match in DOSE_UNIT.finditer(file.text)]
    if hits:
        return [
            fail(
                file.path,
                "dose figures",
                f"dose figures found in an overlay skill: {', '.join(hits[:3])}",
                "overlay lines are phenomenology-only; move any wording around them to intensity/duration terms",
            )
        ]
    return []


def build_alias_map(files: list[SkillFile]) -> dict[str, Path]:
    """Map front-matter `*-altered-state` names -> skill directory."""
    aliases: dict[str, Path] = {}
    for file in files:
        fields, _ = parse_front_matter(file.text)
        name = fields.get("name", "").strip()
        if name:
            aliases[name] = file.path
    return aliases


def check_router(files: list[SkillFile], router: SkillFile) -> list[str]:
    problems: list[str] = []
    alias_map = build_alias_map(files)

    # Every `xxx-altered-state` the router names must resolve to a real dir.
    referenced = set(re.findall(r"[a-z0-9\-]+-altered-state", router.text))
    unknown = sorted(n for n in referenced if n not in alias_map)
    for name in unknown:
        problems.append(
            fail(
                router.path,
                "## Routing Logic (alias resolution)",
                f"router alias `{name}` does not resolve to any skill directory",
                "fix the alias or create the skill it points at; aliases map by front-matter name",
            )
        )
    # Substance slugs of disk dirs (overlay lines carry their own base label)
    for child in router.path.parent.iterdir():
        if child.is_dir() and child.name != "router" and child.name not in ("combos", "tolerance"):
            slug = child.name
            if slug.lower() not in router.text.lower():
                problems.append(
                    fail(
                        router.path,
                        "## Routing Logic (Step 1 table)",
                        f"substance `{slug}` never mentioned by the router",
                        "every substance skill dir must appear in the router's Step-1 table",
                    )
                )
    return problems


def validate_all(skills_dir: Path) -> tuple[list[str], list[SkillFile]]:
    files: list[SkillFile] = []
    for path in sorted(skills_dir.rglob("SKILL.md")):
        files.append(SkillFile(path, skills_dir))
    problems: list[str] = []
    router = next((f for f in files if f.kind == "router"), None)
    for file in files:
        problems.extend(check_front_matter(file))
        problems.extend(check_safety_override(file))
        problems.extend(check_intensities_and_matrix(file))
        problems.extend(check_dose_arc(file))
        problems.extend(check_safety_bar(file))
    if router:
        problems.extend(check_router(files, router))
    return problems, files


# --- authoring guide ---------------------------------------------------------

AUTHORING_CHECKLIST = """\
# New-skill authoring checklist ({path})

Every rule check_skills.py enforces — a new SKILL.md that satisfies this
checklist passes `make skills-check`. Reference structure:
skills/psilocybin/SKILL.md.

Front matter (`---` fenced block, first 11 lines):
  1. `name:` must end in `-altered-state`.
  2. `description:` multi-line (`>` block) naming the phenomenological contract.
  3. `tags:` list must contain the substance/topic word and `altered-states`.
  4. `version:` quoted semver string, e.g. `version: "1.5"`.
  5. `author: behole`.

Sections, in order:
  6. `## Safety Override — Read First` — overrides-everything declaration,
     the five break conditions (suicidal ideation / psychosis / substance
     emergency / acute distress / requests for dosage, sourcing,
     combinations, or interactions), the crisis-resource blockquote
     (988 / 741741 / SAMHSA / EMS / international), and the
     "This is not harm reduction" line pointing at SAFETY.md.
  7. A dimension matrix: either a `## The 7 Phenomenological Dimensions`
     markdown table — 7 numbered rows (Perceptual, Temporal, Cognitive,
     Emotional, Self/Ego, Mystical, Somatic), no empty intensity cell —
     or an `## Intensity Profiles` / `## Intensity Levels` section that
     states each dimension in prose per level.
  8. `## The Dose Arc` (headings may add a subtitle) with onset framing.
  9. Substance skills also carry Descent & Exit and Set & Setting sections
     by convention (not machine-enforced; reviewers will ask).

Safety bar (SAFETY.md): no dose figures, no dosing verbs, no therapy or
integration-treatment claims, no sourcing language. Overlay skills
(skills/combos/, skills/tolerance/, skills/afterglow) must carry ZERO dose
figures — they are valid skills, not substances.

If you are an overlay line: place the file at skills/<line>/<name>/SKILL.md
(never a bare SKILL.md inside the line directory) and register the new
front-matter name in skills/router/SKILL.md so alias resolution finds it.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Altered States skill tree (structure + safety furniture)."
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help="skills root to validate (default: the repo's skills/; useful on tmp copies for tests)",
    )
    parser.add_argument(
        "--new-skill",
        type=Path,
        default=None,
        help="print the full authoring checklist for a would-be new skill; pass its intended path",
    )
    args = parser.parse_args(argv)

    if args.new_skill:
        print(AUTHORING_CHECKLIST.format(path=args.new_skill))
        return 0

    skills_dir: Path = args.skills_dir
    if not skills_dir.is_dir():
        print(f"error: skills dir not found: {skills_dir}", file=sys.stderr)
        return 2

    problems, files = validate_all(skills_dir)
    if problems:
        print(f"check_skills: {len(problems)} failure(s) across {len(files)} skill files in {skills_dir}\n")
        for problem in problems:
            print(problem)
            print()
        return 1

    for file in files:
        fields, _ = parse_front_matter(file.text)
        version = fields.get("version", "?").strip().strip('"').strip("'") or "?"
        print(f"{file.relpath}: OK (v{version}, {file.kind})")
    print(f"\ncheck_skills: {len(files)} skill files OK — {skills_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
