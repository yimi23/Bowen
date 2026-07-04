"""
core/skills.py — The skill library: progressive disclosure for agent expertise.

A skill is a folder under skills/ holding a SKILL.md — YAML frontmatter
(name, description) plus markdown instructions. Three loading tiers:

  1. Index    — name + description only (~80 tokens/skill). Y carries this
                for the whole library; it is how skills get discovered.
  2. Standing — agents.yaml lists each agent's permanent skills; their FULL
                bodies are injected into that agent's system prompt at spawn.
  3. Mounted  — Y attaches extra skill names to a dispatch brief; the
                receiving agent loads those bodies for that task only.

Tenant-scoped skills live at memory/users/<id>/skills/ and are visible
only inside that tenant's wall — same isolation law as everything else.

Description quality determines routing accuracy: the agent reasons over
descriptions alone when choosing skills. Write them as invocation cues.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path
    tenant_scoped: bool = False


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Minimal frontmatter parser: --- key: value --- then body."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, parts[2].strip()


def validate_skill(skill_dir: Path) -> list[str]:
    """
    Structural audit of one skill folder. DEVOPS runs this (plus a content
    review) before any tenant-authored or third-party skill enters the
    library — a skill can direct an agent's behavior, so the house reviews
    its own onboarding guides.
    """
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"{skill_dir.name}: missing SKILL.md"]

    meta, body = _parse_frontmatter(skill_md.read_text(errors="replace"))
    name = meta.get("name", "")
    if not name:
        errors.append(f"{skill_dir.name}: frontmatter missing 'name'")
    elif not _NAME_RE.match(name):
        errors.append(f"{skill_dir.name}: name {name!r} must be kebab-case")
    elif name != skill_dir.name:
        errors.append(f"{skill_dir.name}: folder name and skill name differ ({name!r})")

    description = meta.get("description", "")
    if not description:
        errors.append(f"{skill_dir.name}: frontmatter missing 'description'")
    elif len(description) > 500:
        errors.append(f"{skill_dir.name}: description too long (>500 chars) — it rides in every index")

    if not body.strip():
        errors.append(f"{skill_dir.name}: empty body — a skill with no instructions is noise")
    return errors


class SkillLibrary:
    """House library plus (optionally) one tenant's private skills."""

    def __init__(self, house_dir: Path, tenant_dir: Optional[Path] = None) -> None:
        self._house_dir = house_dir
        self._tenant_dir = tenant_dir
        self._skills: dict[str, SkillMeta] = {}
        self._scan()

    def _scan(self) -> None:
        for base, tenant_scoped in ((self._house_dir, False), (self._tenant_dir, True)):
            if base is None or not base.exists():
                continue
            for skill_dir in sorted(p for p in base.iterdir() if p.is_dir()):
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                meta, _ = _parse_frontmatter(skill_md.read_text(errors="replace"))
                name = meta.get("name", skill_dir.name)
                if name in self._skills and tenant_scoped:
                    logger.warning("tenant skill %r shadows a house skill — house wins", name)
                    continue
                self._skills[name] = SkillMeta(
                    name=name,
                    description=meta.get("description", ""),
                    path=skill_md,
                    tenant_scoped=tenant_scoped,
                )

    # ── Tier 1: the index ─────────────────────────────────────────────────────

    def index_text(self) -> str:
        """One line per skill — the ~80-token discovery tier."""
        return "\n".join(
            f"- {m.name}: {m.description}" for m in self._skills.values()
        )

    def names(self) -> list[str]:
        return list(self._skills.keys())

    # ── Tiers 2-3: full bodies ────────────────────────────────────────────────

    def load(self, name: str) -> Optional[str]:
        """Full skill body (frontmatter stripped). None if unknown."""
        meta = self._skills.get(name)
        if meta is None:
            return None
        _, body = _parse_frontmatter(meta.path.read_text(errors="replace"))
        return body

    def load_many(self, names: list[str]) -> str:
        """Concatenated bodies for standing/mounted injection. Skips unknowns loudly."""
        sections = []
        for name in names:
            body = self.load(name)
            if body is None:
                logger.warning("skill %r not found in library — skipped", name)
                continue
            sections.append(f"### Skill: {name}\n{body}")
        return "\n\n".join(sections)


# ── Process-wide house library (cached; tenant libraries built per call) ──────

_HOUSE: Optional[SkillLibrary] = None


def house_library(skills_dir: Optional[Path] = None) -> SkillLibrary:
    global _HOUSE
    if _HOUSE is None:
        if skills_dir is None:
            skills_dir = Path(__file__).parent.parent / "skills"
        _HOUSE = SkillLibrary(skills_dir)
    return _HOUSE


def reset_house_library() -> None:
    """Test seam."""
    global _HOUSE
    _HOUSE = None
