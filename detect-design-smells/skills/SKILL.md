---
name: detect-design-smell
description: Detect design smells in Mermaid UML class diagrams using a fine-tuned SLM adapter. Design smells are class- or module-level structural problems (God Class, Cyclic Dependency, Hub-like Modularization, Deep/Wide Hierarchy, Data Class, Feature Envy, Data Clumps, Refused Bequest, Shotgun Surgery, Divergent Change, Middle Man, Multifaceted Abstraction, Insufficient Modularization). Use when the user provides a Mermaid classDiagram and asks for design review. Do NOT use for code-level smells (Long Method, Long Parameter List, Magic Number, Primitive Obsession, etc.) — those belong to the detect-code-smell skill.
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/run_slm.py *)
---

# Design Smell Detection

Detect **design smells** in a Mermaid `classDiagram` using a fine-tuned SLM adapter. Design smells are structural problems at the class or module level, visible from the class diagram itself (methods, attributes, dependencies, inheritance). Code smells are out of scope.

## Instructions

1. Accept a Mermaid `classDiagram` block as input.
2. Run `${CLAUDE_SKILL_DIR}/scripts/run_slm.py --input <diagram_file>`.
3. The script loads the LoRA adapter from `design_smell_lora/` and returns a JSON array.
4. Return the JSON to the user, or pass it to the DAD builder.

## Smell categories

### Trained smells (the adapter was fine-tuned on these)

- **God Class** — one class has too many methods and too many outgoing dependencies
- **Cyclic Dependency** — a dependency cycle among two or more classes
- **Hub-like Modularization** — a class with many incoming and many outgoing dependencies
- **Deep Hierarchy** — an inheritance chain at least 4 levels deep
- **Wide Hierarchy** — a parent class with 8 or more direct subclasses
- **Data Class** — a class with attributes but no behavior

### Unseen design smells (probe for generalization)

The adapter was not trained on these. Including them in the inference prompt tests whether fine-tuning generalized to related design smells or only memorized the six training categories.

- **Feature Envy** — a method of class A visibly uses methods or attributes of class B more than its own
- **Data Clumps** — the same group of 3+ attributes appears together across multiple classes
- **Refused Bequest** — a subclass inherits but overrides or ignores most of the parent's interface
- **Shotgun Surgery** — one class is depended on by many unrelated classes, so a single change ripples widely
- **Divergent Change** — one class's methods cluster into unrelated groups, so it changes for many unrelated reasons
- **Middle Man** — a class that only delegates to another class and adds no behavior of its own
- **Multifaceted Abstraction** — a class that represents two or more unrelated concepts (e.g., `UserAuthenticatorBillingReporter`). Overlaps with Divergent Change and God Class; when reporting, prefer the more specific label.
- **Insufficient Modularization** — a class that is not decomposed enough to isolate responsibilities, even if it does not meet the God Class method-count threshold

## Output format

```json
[
  {"smell": "God Class", "class": "OrderService", "severity": "high"},
  {"smell": "Feature Envy", "class": "TaxCalculator", "severity": "medium"}
]

[] means no potential code smells detected.