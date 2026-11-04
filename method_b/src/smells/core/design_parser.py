"""DevBench project loading and Mermaid UML parsing.

DevBench design docs are Markdown files with fenced ```mermaid blocks:
  - UML_class.md     -> classDiagram
  - UML_sequence.md  -> sequenceDiagram
plus PRD.md and architecture_design.md. repo_config.json lists the source files to
implement (code_file_DAG: file -> files it depends on) and how to run the unit tests.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- Mermaid: classes


@dataclass
class UMLClass:
    name: str
    attributes: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    stereotype: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class UMLRelation:
    source: str
    target: str
    kind: str  # association | inheritance | composition | aggregation | dependency | link
    label: str = ""


@dataclass
class ClassDiagram:
    classes: dict[str, UMLClass] = field(default_factory=dict)
    relations: list[UMLRelation] = field(default_factory=list)

    def dependencies(self, name: str) -> list[str]:
        return sorted({r.target for r in self.relations if r.source == name})

    def to_dict(self) -> dict:
        return {
            "classes": {
                n: {"attributes": c.attributes, "methods": c.methods, "stereotype": c.stereotype}
                for n, c in self.classes.items()
            },
            "relations": [r.__dict__ for r in self.relations],
        }


_ARROWS = [  # longest first
    ("<|--", "inheritance", True), ("--|>", "inheritance", False),
    ("<|..", "realization", True), ("..|>", "realization", False),
    # diamond side is the whole; the whole depends on its parts
    ("*--", "composition", False), ("--*", "composition", True),
    ("o--", "aggregation", False), ("--o", "aggregation", True),
    ("<--", "association", True), ("-->", "association", False),
    ("<..", "dependency", True), ("..>", "dependency", False),
    ("--", "link", False), ("..", "link", False),
]
_CARD = r'(?:\s*"[^"]*")?'
_ID = r"([A-Za-z_][\w.]*)(?:~[^~]*~)?"


def _mermaid_blocks(md: str, kind: str) -> list[str]:
    blocks = re.findall(r"```mermaid\s*\n(.*?)```", md, re.DOTALL)
    return [b for b in blocks if b.lstrip().startswith(kind)] or ([md] if kind in md else [])


def _add_member(cls: UMLClass, member: str) -> None:
    member = member.strip()
    if not member or member.startswith("%%"):
        return
    if member.startswith("<<") and member.endswith(">>"):
        cls.stereotype = member[2:-2]
    elif "(" in member:
        cls.methods.append(member)
    else:
        cls.attributes.append(member)


def parse_class_diagram(md: str) -> ClassDiagram:
    diagram = ClassDiagram()

    def get(name: str) -> UMLClass:
        return diagram.classes.setdefault(name, UMLClass(name))

    for block in _mermaid_blocks(md, "classDiagram"):
        current: UMLClass | None = None
        for raw in block.splitlines():
            line = raw.strip()
            if not line or line.startswith("%%") or line == "classDiagram":
                continue
            if current is not None:
                if line.startswith("}"):
                    current = None
                else:
                    _add_member(current, line)
                continue
            m = re.match(rf"class\s+{_ID}\s*(\{{)?\s*(\}})?\s*$", line)
            if m:
                cls = get(m.group(1))
                if m.group(2) and not m.group(3):
                    current = cls
                continue
            m = re.match(rf"<<(\w+)>>\s+{_ID}", line)
            if m:
                get(m.group(2)).stereotype = m.group(1)
                continue
            rel = _parse_relation(line)
            if rel:
                get(rel.source), get(rel.target)
                diagram.relations.append(rel)
                continue
            m = re.match(rf"{_ID}\s*:\s*(.+)$", line)
            if m and m.group(1) not in ("note",):
                member = m.group(2)
                cls = get(m.group(1))
                # "X : X is a fake class ..." style free text -> note
                if " " in member.strip() and "(" not in member and not member.strip().startswith(("+", "-", "#", "~")):
                    cls.notes.append(member.strip())
                else:
                    _add_member(cls, member)
    return diagram


def _parse_relation(line: str) -> UMLRelation | None:
    label = ""
    if ":" in line:
        line, label = line.split(":", 1)
        label = label.strip()
    for arrow, kind, reverse in _ARROWS:
        m = re.match(rf"^{_ID}{_CARD}\s*{re.escape(arrow)}{_CARD}\s*{_ID}\s*$", line.strip())
        if m:
            a, b = m.group(1), m.group(2)
            src, dst = (b, a) if reverse else (a, b)
            return UMLRelation(src, dst, kind, label)
    return None


# ------------------------------------------------------------- Mermaid: sequence


@dataclass
class SequenceDiagram:
    participants: list[str] = field(default_factory=list)
    messages: list[tuple[str, str, str]] = field(default_factory=list)  # (from, to, text)


def parse_sequence_diagram(md: str) -> SequenceDiagram:
    sd = SequenceDiagram()
    for block in _mermaid_blocks(md, "sequenceDiagram"):
        for raw in block.splitlines():
            line = raw.strip()
            m = re.match(r"(?:participant|actor)\s+(\S+)(?:\s+as\s+.*)?$", line)
            if m:
                if m.group(1) not in sd.participants:
                    sd.participants.append(m.group(1))
                continue
            m = re.match(r"([\w.]+)\s*(-{1,2}>>|-{1,2}>|-{1,2}x|-{1,2}\))[+-]?\s*([\w.]+)\s*:\s*(.*)$", line)
            if m:
                sd.messages.append((m.group(1), m.group(3), m.group(4).strip()))
    return sd


# --------------------------------------------------------------- DevBench project


@dataclass
class Project:
    name: str
    root: Path
    prd: str
    uml_class: str
    uml_sequence: str
    architecture: str
    code_file_dag: dict[str, list[str]]
    required_files: list[str]
    unit_tests_dir: str
    unit_test_script: str
    config: dict

    @property
    def class_diagram(self) -> ClassDiagram:
        return parse_class_diagram(self.uml_class)

    @property
    def sequence_diagram(self) -> SequenceDiagram:
        return parse_sequence_diagram(self.uml_sequence)

    def design_docs(self) -> str:
        """Everything the generator is allowed to see. Never includes tests."""
        return (
            f"# PRD\n{self.prd}\n\n{self.uml_class}\n\n{self.uml_sequence}\n\n"
            f"{self.architecture}"
        )

    def source_files(self) -> list[str]:
        """Files to implement, dependencies first (topological order of code_file_DAG)."""
        return topo_order(self.code_file_dag)


def topo_order(dag: dict[str, list[str]]) -> list[str]:
    nodes: list[str] = []
    for k, deps in dag.items():
        for n in [*deps, k]:
            if n not in nodes:
                nodes.append(n)
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(n: str, stack: tuple[str, ...]) -> None:
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            raise ValueError(f"cycle in code_file_DAG: {' -> '.join((*stack, n))}")
        state[n] = 1
        for d in dag.get(n, []):
            visit(d, (*stack, n))
        state[n] = 2
        order.append(n)

    for n in nodes:
        visit(n, ())
    return order


def _read_doc(root: Path, rel: str) -> str:
    for cand in (root / rel, root / "docs" / rel):
        if cand.is_file():
            return cand.read_text(encoding="utf-8", errors="replace")
    return ""


def load_project(devbench_dir: Path, name: str) -> Project:
    root = Path(devbench_dir) / name
    cfg = json.loads((root / "repo_config.json").read_text())
    return Project(
        name=name,
        root=root,
        prd=_read_doc(root, cfg.get("PRD", "PRD.md")),
        uml_class=_read_doc(root, cfg.get("UML_class", "UML_class.md")),
        uml_sequence=_read_doc(root, cfg.get("UML_sequence", "UML_sequence.md")),
        architecture=_read_doc(root, cfg.get("architecture_design", "architecture_design.md")),
        code_file_dag=cfg.get("code_file_DAG", {}),
        required_files=cfg.get("required_files", []),
        unit_tests_dir=cfg.get("unit_tests", "unit_tests"),
        unit_test_script=cfg.get("unit_test_script", "pytest unit_tests"),
        config=cfg,
    )


def list_projects(devbench_dir: Path) -> list[str]:
    return sorted(p.name for p in Path(devbench_dir).iterdir() if (p / "repo_config.json").is_file())
