"""Unit planner: order files dependencies-first and attach the design classes they implement."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from smells.core.design_parser import Project


@dataclass
class Unit:
    unit_id: int
    path: str
    classes: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


def plan(project: Project) -> list[Unit]:
    diagram = project.class_diagram
    arch = project.architecture
    units = []
    for i, path in enumerate(project.source_files()):
        # classes named in the architecture section for this file (best effort)
        fname = path.rsplit("/", 1)[-1]
        section = ""
        m = re.search(rf"`?{re.escape(fname)}`?\s*:?\s*\n(.*?)(?:\n\s*\n`|\Z)", arch, re.DOTALL)
        if m:
            section = m.group(1)
        classes = [c for c in diagram.classes if c in section]
        units.append(Unit(i, path, classes, project.code_file_dag.get(path, [])))
    return units
