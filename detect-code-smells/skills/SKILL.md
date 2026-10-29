---
name: detect-code-smells
description: Predict potential code smells from Mermaid UML class diagrams using a fine-tuned SLM adapter. Use when the user provides a Mermaid classDiagram and asks for implementation-level warnings. Do NOT use for architectural design smells (God Class, Hub-like Modularization, etc.) — those belong to the detect-design-smell skill.
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/run_slm.py *)
---

# Code Smell Prediction

Predict potential code smells from a Mermaid `classDiagram` using a fine-tuned SLM adapter. This skill analyzes method signatures and attribute lists to warn about implementation flaws *before* the code is generated. 

## Instructions

1. Accept a Mermaid `classDiagram` block as input.
2. Run `${CLAUDE_SKILL_DIR}/run_slm.py --input <diagram_file>`.
3. The script loads the LoRA adapter from `code_smell_lora/` and returns a JSON array.
4. Return the JSON to the user, or pass it to the DAD (Design Advisory Document) builder.

## Smell categories

### Trained smells (the adapter was fine-tuned on these)

- **Long Parameter List** — a method signature contains more than 5 parameters, making it hard to call and read
- **Primitive Obsession** — domain concepts (like `email`, `phone`, `zipCode`, `currency`) are declared as raw `String` or `int` instead of dedicated value objects
- **Long Method** — method names combine multiple verbs (e.g., `validateAndProcessAndSaveOrder()`), indicating the method will likely do too much
- **Magic Number Risk** — business logic values (like `taxRate`, `discountPercentage`, `maxRetryCount`) are declared as raw `double` or `int` instead of constants or dedicated types

### Unseen code smell (probe for generalization)

The adapter was not trained on this. Including it in the inference prompt tests whether fine-tuning generalized to related implementation smells.

- **Duplicate Code** — identical method signatures or attribute sets appear across multiple unrelated classes, indicating copy-paste logic

## Output format

The script returns JSON:

```json
[
  {
    "smell": "Long Parameter List",
    "class": "OrderService",
    "method": "processOrder",
    "reason": "Method has more than 5 parameters."
  },
  {
    "smell": "Primitive Obsession",
    "class": "Customer",
    "attribute": "email",
    "reason": "Domain concept represented as a raw String."
  }
]

[] means no potential code smells detected.