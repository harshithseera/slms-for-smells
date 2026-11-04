"""Load the per-smell skill files.

Layout:
  skills/_shared/RULES.md          shared rules + output format (top of every judge prompt)
  skills/<smell_id>/SKILL.md       one smell: frontmatter + one "## Smell: <id>" section

A judge call sees RULES.md plus the ONE skill file for the smell being judged.
Maintainer comments (<!-- ... -->) and frontmatter never reach a model.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent
SHARED = "_shared/RULES.md"
SMELL_HEADING = re.compile(r"^## Smell: (\w+)\s*$", re.M)
STATUSES = ("judged", "rule", "planned")


@dataclass(frozen=True)
class SmellSkill:
    smell: str
    skill: str  # skill name from the frontmatter, e.g. "god-class"
    family: str  # "design" | "code"
    status: str  # "judged" (SLM) | "rule" (static rule) | "planned"
    version: int | str
    path: Path
    rules: str  # shared rules text
    section: str  # this smell's "## Smell: <id>" section

    def prompt_text(self) -> str:
        return f"{self.rules}\n\n{self.section}"

    def reject_rules(self) -> list[str]:
        """The bullets under **Reject when.**, one string each."""
        m = re.search(r"\*\*Reject when\.\*\*\s*\n(.*?)(?=\n\*\*|\Z)", self.section, re.S)
        if not m:
            return []
        rules, cur = [], None
        for line in m.group(1).splitlines():
            if line.startswith("- "):
                cur = line[2:].strip()
                rules.append(cur)
            elif line.strip() and rules:
                rules[-1] = f"{rules[-1]} {line.strip()}"
        return rules


def _split(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front) or {}, re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()


@lru_cache(maxsize=None)
def load_skills(skills_dir: Path = SKILLS_DIR) -> dict[str, SmellSkill]:
    """smell id -> SmellSkill, one per skills/<smell>/SKILL.md."""
    skills_dir = Path(skills_dir)
    _, rules = _split(skills_dir / SHARED)
    out: dict[str, SmellSkill] = {}
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        meta, body = _split(path)
        heads = SMELL_HEADING.findall(body)
        smell = meta.get("smell")
        if heads != [smell] or path.parent.name != smell:
            raise ValueError(f"{path}: needs exactly one '## Smell: {path.parent.name}' section "
                             f"and frontmatter smell: {path.parent.name}")
        if meta.get("status") not in STATUSES or meta.get("family") not in ("design", "code"):
            raise ValueError(f"{path}: status must be one of {STATUSES} and family design|code")
        out[smell] = SmellSkill(smell, meta.get("name", smell), meta["family"], meta["status"],
                                meta.get("version", 0), path, rules, body[body.index("## Smell:"):])
    return out


def skill_for(smell: str, skills_dir: Path = SKILLS_DIR) -> SmellSkill:
    try:
        return load_skills(skills_dir)[smell]
    except KeyError:
        raise KeyError(f"no skill file defines smell {smell!r}") from None


def skills_fingerprint(skills_dir: Path = SKILLS_DIR) -> dict[str, dict]:
    """Version and content hash of the shared rules and every skill file (logged with each run)."""
    skills_dir = Path(skills_dir)
    out = {}
    for path in [skills_dir / SHARED, *sorted(skills_dir.glob("*/SKILL.md"))]:
        meta, _ = _split(path)
        out[meta.get("name", path.parent.name)] = {
            "version": meta.get("version", 0), "status": meta.get("status", "shared"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:12],
        }
    return out
