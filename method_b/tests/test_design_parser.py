from smells.core.design_parser import parse_class_diagram, parse_sequence_diagram, topo_order

CLASS_MD = """
# UML class
```mermaid
classDiagram
  class Shop {
    -items List
    +add(item Item) None
    +total() Float
  }
  class Item
  <<interface>> Priced
  Item : +price Float
  Item : Item is a value object.
  Shop "1" *-- "many" Item : contains
  Priced <|-- Item
  Shop --> Logger : uses >>
```
"""


def test_class_diagram():
    cd = parse_class_diagram(CLASS_MD)
    assert set(cd.classes) == {"Shop", "Item", "Priced", "Logger"}
    assert cd.classes["Shop"].methods == ["+add(item Item) None", "+total() Float"]
    assert cd.classes["Shop"].attributes == ["-items List"]
    assert cd.classes["Item"].attributes == ["+price Float"]
    assert cd.classes["Item"].notes == ["Item is a value object."]
    assert cd.classes["Priced"].stereotype == "interface"
    kinds = {(r.source, r.target, r.kind) for r in cd.relations}
    assert ("Shop", "Item", "composition") in kinds
    assert ("Item", "Priced", "inheritance") in kinds
    assert cd.dependencies("Shop") == ["Item", "Logger"]


def test_sequence_diagram():
    sd = parse_sequence_diagram(
        "```mermaid\nsequenceDiagram\n participant User\n participant API\n"
        " User->>API: of_text(text)\n API-->>User: Result\n```"
    )
    assert sd.participants == ["User", "API"]
    assert sd.messages == [("User", "API", "of_text(text)"), ("API", "User", "Result")]


def test_topo_order_deps_first():
    assert topo_order({"main.py": ["a.py", "b.py"], "b.py": ["a.py"]}) == ["a.py", "b.py", "main.py"]
