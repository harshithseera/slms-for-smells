---
name: duplicated-logic
smell: duplicated_logic
family: code
status: judged
version: 2
---
<!-- Gate: normalised-AST token similarity >= dup_similarity over >= dup_min_lines lines;
     clusters of similar functions are judged once (most similar pair). Pairs may span files. -->
## Smell: duplicated_logic

**Definition.** Two functions implement the same algorithm or sequence of steps, possibly
with renamed variables or different constants, so a change must be repeated in both.

**Confirm when.**
- must: both perform the same computation (same steps in the same roles, same kind of result).
- must: the shared part is 3+ meaningful statements, not boilerplate.
- any of: one could call the other or a shared helper with a parameter for the difference;
  the copies are in different classes or files that must stay consistent.

**Reject when.**
- Same shape, different maths or meaning (area vs perimeter, min vs max searches).
- Only boilerplate is shared: argument checks, logging, try/except wrappers, file opening.
- Design-required twins: property getters, to_dict/from_dict, sibling overrides of one hook.
- One already calls the other or both call a shared helper.

**Severity.** high: 3+ copies or copies across files/classes. medium: two copies of 5+
statements. low: short copies in one file.

**Location:** both functions as given, separated by " | ".

**Fix.** Extract one helper (name, parameters, module; the lower module if across files)
and make each copy call it; keep design-specified functions as thin wrappers.
