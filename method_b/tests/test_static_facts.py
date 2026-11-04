import textwrap

from smells.core.judges.gates import gate, static_findings
from smells.core.static_facts import file_facts, module_name, project_facts
from smells.config import load_config

G = load_config()["gates"]


def d(s: str) -> str:
    return textwrap.dedent(s).lstrip()


def test_module_name():
    assert module_name("readtime/api.py") == "readtime.api"
    assert module_name("hone/__init__.py") == "hone"
    assert module_name("src/hybrid.py") == "hybrid"


def test_function_metrics():
    code = d(
        """
        def f(a, b, c, d, e, g, *args, **kw):
            for x in a:
                if x:
                    while b:
                        b -= 1
            return 1

        class K:
            def m(self, x):
                return self.y + x.a + x.b + x.c
        """
    )
    ff, _ = file_facts("m.py", code)
    f = next(x for x in ff.functions if x.qualname == "f")
    assert f.params == 8 and f.nesting == 3 and f.cc >= 4
    m = next(x for x in ff.functions if x.qualname == "K.m")
    assert m.params == 1 and m.self_accesses == 1 and m.foreign_accesses == {"x": 3}


def test_syntax_error_is_a_finding():
    pf = project_facts({"bad.py": "def f(:\n  pass\n"}, G)
    fs = static_findings(pf, "bad.py", G)
    assert [f.smell for f in fs] == ["syntax_error"]
    assert gate(pf, "bad.py", G) == []


def test_import_cycle_detected_with_relative_imports():
    files = {
        "pkg/__init__.py": "",
        "pkg/a.py": "from .b import g\ndef f():\n    return g()\n",
        "pkg/b.py": "from pkg import a\ndef g():\n    return 1\n",
    }
    pf = project_facts(files, G)
    assert pf.import_graph["pkg.a"] == ["pkg.b"]
    assert pf.import_graph["pkg.b"] == ["pkg.a"]
    assert pf.cycles == [["pkg.a", "pkg.b"]]  # still a fact (quality metric), no longer a smell


def test_no_cycle_for_external_imports():
    pf = project_facts({"a.py": "import os\nimport numpy as np\n"}, G)
    assert pf.cycles == [] and pf.import_graph["a"] == []


def test_duplicate_detection_survives_renaming():
    code = d(
        """
        def total_price(items):
            s = 0
            for it in items:
                if it.qty > 0:
                    s += it.qty * it.price
            return round(s, 2)

        def order_sum(lines):
            acc = 0
            for ln in lines:
                if ln.qty > 0:
                    acc += ln.qty * ln.price
            return round(acc, 2)

        def unrelated(path):
            with open(path) as fh:
                return [l.strip() for l in fh if l]
        """
    )
    pf = project_facts({"m.py": code}, G)
    assert len(pf.duplicates) == 1
    pair = pf.duplicates[0]
    assert "total_price" in pair.a and "order_sum" in pair.b and pair.similarity >= 0.9
    hits = gate(pf, "m.py", G)
    assert [h.judge for h in hits if h.judge == "duplicated_logic"] == ["duplicated_logic"]


def test_duplicate_clusters_give_one_gate_hit():
    fns = "\n\n".join(
        f"def f{i}(a, b):\n    out = []\n    for x in a:\n        if x > b:\n            out.append(x * {i})\n    return out"
        for i in range(5)
    )
    pf = project_facts({"m.py": fns}, G)
    assert len(pf.duplicates) == 10
    hits = [h for h in gate(pf, "m.py", G) if h.judge == "duplicated_logic"]
    assert len(hits) == 1 and hits[0].facts["cluster_size"] == 5




def test_long_method_and_params():
    body = "\n".join(f"    x{i} = {i}" for i in range(G["long_method_loc"] + 5))
    code = f"def f(a, b, c, d, e, f, g):\n{body}\n    return x0\n"
    pf = project_facts({"l.py": code}, G)
    smells = sorted(f.smell for f in static_findings(pf, "l.py", G))
    assert smells == ["long_method", "long_parameter_list"]


def test_fan_out_ignores_exceptions_builtins_and_typing():
    code = d(
        """
        from typing import Optional

        class NotFound(Exception):
            pass

        class Service:
            def get(self, k) -> Optional[Repo]:
                try:
                    return Repo(k, Cache())
                except KeyError:
                    raise NotFound(k) from None

            def check(self, v):
                if not isinstance(v, int):
                    raise ValueError(v)
        """
    )
    ff, _ = file_facts("s.py", code)
    svc = next(c for c in ff.classes if c.name == "Service")
    assert svc.referenced == ["Cache", "Repo"] and svc.fan_out == 2


def test_design_fixed_parameter_list_is_low():
    from smells.core.design_parser import parse_class_diagram
    from smells.core.judges.gates import design_signatures
    diagram = parse_class_diagram(
        "```mermaid\nclassDiagram\n  class Av {\n    +free_slots(a int, b int, c int, d int, e int, f int) list\n  }\n```"
    )
    assert design_signatures(diagram) == {"free_slots": 6}
    code = "def free_slots(a, b, c, d, e, f):\n    return []\n\ndef other(a, b, c, d, e, f):\n    return []\n"
    pf = project_facts({"av.py": code}, G)
    sev = {f.location: f.severity for f in static_findings(pf, "av.py", G, design_signatures(diagram))}
    assert sev == {"free_slots": "low", "other": "medium"}


def _hits(code, judge):
    pf = project_facts({"m.py": d(code)}, G)
    return [h for h in gate(pf, "m.py", G) if h.judge == judge]


def test_magic_numbers_gate_skips_obvious_literals():
    hits = _hits("""
        def fee(visits, amount, xs):
            for i in range(10):
                pass
            first = xs[3]
            total = round(amount * 1.0, 2)
            return total * 0.9 if visits > 20 else total
        def ok(xs, n=5):
            return [x + 1 for x in xs if x != 0]
        """, "magic_numbers")
    assert [h.target for h in hits] == ["fee"]
    assert [l["value"] for l in hits[0].facts["literals"]] == [0.9, 20]


def test_primitive_obsession_needs_domain_name_type_and_use():
    hits = _hits("""
        def charge(amount: float, currency: str) -> str:
            if currency not in ("EUR", "USD"):
                raise ValueError(currency)
            return f"{amount:.2f} {currency}"
        def label(name: str, currency) -> str:
            return name + str(currency)
        def forward(email: str) -> dict:
            return {"to": email}
        """, "primitive_obsession")
    assert [(h.target, h.facts["params"]) for h in hits] == [("charge", ["currency"])]


def test_message_chain_gate():
    hits = _hits("""
        class Desk:
            def room(self, b):
                return self.club.classes[self.club.bookings[b].class_id].room
            def short(self):
                return self.club.name
        """, "message_chains")
    assert [h.target for h in hits] == ["Desk.room"]


def test_flag_argument_gate():
    hits = _hits("""
        def apply(amount, refund: bool = False):
            if refund:
                return -amount
            return amount
        def passthrough(xs, reverse=False):
            return sorted(xs, reverse=reverse)
        """, "flag_argument")
    assert [(h.target, h.facts["flags"]) for h in hits] == [("apply", ["refund"])]


def test_data_clump_gate():
    files = {"a.py": "def late_fee(amount, due_date, paid_date, grace_days):\n    return 0\n",
             "b.py": "def days_overdue(due_date, paid_date, grace_days):\n    return 0\n"
                     "def other(x, y, z):\n    return 0\n"}
    pf = project_facts(files, G)
    hits = [h for h in gate(pf, "a.py", G) if h.judge == "data_clumps"]
    assert len(hits) == 1 and hits[0].facts["shared"] == ["due_date", "grace_days", "paid_date"]
    assert hits[0].target == "a.py::late_fee@1|b.py::days_overdue@1"


def test_message_chain_ignores_value_methods_self_and_modules():
    hits = _hits("""
        import os
        class R:
            def a(self, s, d):
                x = s.strip().lower().split("@")      # value methods
                y = d.start.date().isoformat()         # value methods on a value
                z = self.club.members.values()         # own collaborator + dict method
                return os.path.join(x, y), z           # module path
            def b(self, booking):
                return self.club.classes[booking.class_id].room
            def c(self, env):
                return env.config.version_file
        """, "message_chains")
    assert sorted(h.target for h in hits) == ["R.b", "R.c"]
