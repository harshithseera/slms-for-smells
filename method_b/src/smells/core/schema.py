"""Shared data types. Findings use one schema for static rules and SLM judges."""
from __future__ import annotations

from dataclasses import asdict, dataclass

SEVERITIES = ("low", "medium", "high")
SMELLS = (
    "duplicated_logic",
    "long_method",
    "long_parameter_list",
    "magic_numbers",
    "primitive_obsession",
    "data_clumps",
    "message_chains",
    "flag_argument",
    "syntax_error",
)
# Code smells only. Definitions: src/smells/common/skills/<smell>/SKILL.md (+ _shared/RULES.md)
CODE_SMELLS = ("duplicated_logic", "long_method", "long_parameter_list", "magic_numbers",
               "primitive_obsession", "data_clumps", "message_chains", "flag_argument")


@dataclass
class Finding:
    smell: str
    location: str
    severity: str
    evidence: str
    fix: str
    source: str = "static"  # "static" or "slm:<model>"
    file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def key(self) -> tuple[str, str]:
        """Identity used to track oscillation across fix rounds."""
        return (self.smell, self.location)
