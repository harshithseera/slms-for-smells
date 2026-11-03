---
name: detect-code-smells
description: Predict potential code smells from Mermaid UML class diagrams using a fine-tuned SLM adapter served over MCP. Use BEFORE implementing any Mermaid classDiagram, and whenever the user asks for implementation-level warnings, method signature review, or a Design Advisory Document (DAD). Do NOT use for architectural design smells (God Class, Hub-like Modularization, etc.) — those belong to the detect-design-smells skill.
---

# Code Smell Prediction

Predict potential code smells from a Mermaid `classDiagram` using a fine-tuned SLM adapter (Qwen2.5-1.5B + LoRA). This skill analyzes method signatures and attribute lists to warn about implementation flaws *before* the code is generated. It reads diagrams, not source code, so findings are predictions rather than confirmed smells.

The adapter runs on a remote Colab GPU and is reached through the `smell-advisor` MCP server. Do not try to run it locally.

## Instructions

1. Accept a Mermaid `classDiagram` block as input (use `read_design_doc(path)` if it is a file).
2. Call the MCP tool `detect_code_smells(diagram)`. It loads the LoRA adapter from `code_smell_lora/` and returns a JSON array.
3. If the output is not valid JSON, retry once. If it still fails, report the failure. Do not invent findings.
4. Return the JSON to the user, or pass it to the DAD (Design Advisory Document) builder.

## Smells and standard fixes

### Trained smells (the adapter was fine-tuned on these)

| Smell | What triggers it | Suggested fix |
|---|---|---|
| Long Parameter List | A method signature contains more than 5 parameters, making it hard to call and read | Introduce a parameter object; group related arguments into a class |
| Primitive Obsession | Domain concepts (like `email`, `phone`, `zipCode`, `currency`) are declared as raw `String` or `int` instead of dedicated value objects | Create small value classes (`Email`, `Money`, `ZipCode`) with validation |
| Long Method | Method names combine multiple verbs (e.g. `validateAndProcessAndSaveOrder()`), indicating the method will likely do too much | Split into single-purpose methods; extract helpers |
| Magic Number Risk | Business logic values (like `taxRate`, `discountPercentage`, `maxRetryCount`) are declared as raw `double` or `int` instead of constants or dedicated types | Use named constants, configuration, or a dedicated type |

### Unseen code smell 

The adapter was not trained on this. Including it in the inference prompt tests whether fine-tuning generalized to related implementation smells.

| Smell | What triggers it | Suggested fix |
|---|---|---|
| Duplicate Code | Identical method signatures or attribute sets appear across multiple unrelated classes, indicating copy-paste logic | Extract the shared members into a common base class, mixin, or utility |

## Output format

The tool returns JSON:

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
```

`[]` means no potential code smells detected.

## Building the DAD rows

Use the same table schema as `detect-design-smells`, with IDs `C1, C2...`:

| ID | Smell | Location | Severity | Explanation | Suggested fix |

Location is `Class.method` or `Class.attribute`. This model does not output severity, so assign it by rule: Long Parameter List and Long Method = medium; Primitive Obsession, Magic Number Risk and Duplicate Code = low. Use the model's `reason` as the explanation. For Duplicate Code, start the explanation with `[untrained probe]`.

## Limitations (state these when relevant)

- Training labels come from string rules (comma counts, the word "And" in a method name, specific attribute names), so the model has probably learned those rules. Real diagrams with different naming may be missed or misflagged.
- Findings are predictions from signatures only. Confirm them against the generated code with an independent tool.
- Duplicate Code is untrained and needs comparison across classes, which the model sees only within one chunk of the diagram. Treat it as a hint.
