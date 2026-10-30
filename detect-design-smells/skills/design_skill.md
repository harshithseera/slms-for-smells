---
name: detect-design-smells
description: Detect design smells in Mermaid UML class diagrams using a fine-tuned SLM adapter served over MCP. Design smells are class- or module-level structural problems (God Class, Cyclic Dependency, Hub-like Modularization, Deep/Wide Hierarchy, Data Class, plus probed-but-untrained Feature Envy, Data Clumps, Refused Bequest, Shotgun Surgery, Divergent Change, Middle Man, Multifaceted Abstraction, Insufficient Modularization). Use this BEFORE generating code from any Mermaid classDiagram, and whenever the user asks for a design review, design quality check, or a Design Advisory Document (DAD). Do NOT use for code-level smells (Long Method, Long Parameter List, Magic Number, Primitive Obsession, Duplicate Code) — those belong to the detect-code-smells skill.
---

# Design Smell Detection

Detect **design smells** in a Mermaid `classDiagram` using a fine-tuned SLM adapter (Qwen2.5-1.5B + LoRA). Design smells are structural problems at the class or module level, visible from the class diagram itself (methods, attributes, dependencies, inheritance). Code smells are out of scope.

The adapter runs on a remote Colab GPU and is reached through the `smell-advisor` MCP server. Do not try to run it locally.

## Instructions

1. Accept a Mermaid `classDiagram` block as input (use `read_design_doc(path)` if it is a file).
2. Call the MCP tool `detect_design_smells(diagram)`. It loads the LoRA adapter from `design_smell_lora/` and returns a JSON array.
3. If the output is not valid JSON, retry once. If it still fails, report the failure. Do not invent findings.
4. Return the JSON to the user, or pass it to the DAD (Design Advisory Document) builder.

## Smells and standard fixes

### Trained smells 

| Smell | What it means | Suggested fix |
|---|---|---|
| God Class | One class has too many methods (12+ in training) and too many outgoing dependencies (4+) | Split by responsibility (Extract Class); move behaviour next to the data it uses |
| Cyclic Dependency | A dependency cycle among two or more classes | Introduce an interface or mediator; invert one dependency (DIP); extract shared code |
| Hub-like Modularization | A class with many incoming and many outgoing dependencies (5+ each in training) | Break the hub into focused classes; route through narrower interfaces |
| Deep Hierarchy | An inheritance chain at least 4 levels deep | Prefer composition over inheritance; flatten intermediate classes |
| Wide Hierarchy | A parent class with 8 or more direct subclasses | Group subclasses under intermediate abstractions, or use Strategy/composition |
| Data Class | A class with attributes (6+ in training) but no behaviour | Move related behaviour into the class (Move Method) or merge it into its main user |

### Unseen design smells 

The adapter was not trained on these. Including them in the inference prompt tests whether fine-tuning generalized to related design smells or only memorized the six training categories.

| Smell | What it means | Suggested fix |
|---|---|---|
| Middle Man | A class that only delegates to another class and adds no behaviour of its own | Remove or inline the delegating class; let clients call the target directly |
| Multifaceted Abstraction | A class that represents two or more unrelated concepts (e.g. `UserAuthenticatorBillingReporter`). Overlaps with Divergent Change and God Class; when reporting, prefer the more specific label | Split into one class per concept |
| Insufficient Modularization | A class that is not decomposed enough to isolate responsibilities, even if it does not meet the God Class method-count threshold | Extract smaller classes or modules around distinct responsibilities |

## Output format

The tool returns JSON:

```json
[
  {"smell": "God Class", "class": "OrderService", "severity": "high"},
  {"smell": "Insufficient Modularization", "class": "TaxCalculator", "severity": "medium"}
]
```

`[]` means no design smells detected.

## Building the DAD rows

Use this fixed table schema, with IDs `D1, D2...` for design findings, sorted high to low severity:

| ID | Smell | Location | Severity | Explanation | Suggested fix |

Location is the class name returned by the model. Take the explanation and fix from the tables above. For findings from the **unseen** table, start the explanation with `[untrained probe]` so readers know to trust them less.

## Limitations (state these when relevant)

- The detector was fine-tuned on synthetic diagrams whose labels come from metric thresholds (method counts, dependency counts, hierarchy depth). Treat findings as flags to check, not ground truth.
- Severity is the model's own estimate and is the least reliable output.
- Untrained smells are a generalization probe. Several of them (Feature Envy, Refused Bequest, Divergent Change, Shotgun Surgery) depend on method bodies or change history that a class diagram does not show, so expect low precision and treat them as hints only.
- Large diagrams may exceed the 3072-token context window; split them if so.
