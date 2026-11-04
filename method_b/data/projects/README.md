# Design projects (benchmark inputs)

Self-made design-to-code projects that replace DevBench as the benchmark input. They
use DevBench's layout, so the whole pipeline works on them unchanged.

```
<project>/
  docs/PRD.md, UML_class.md, UML_sequence.md (Mermaid), architecture_design.md   → given to the code-gen LLM
  repo_config.json      code_file_DAG: the files the LLM must write, dependencies first
  <package>/            reference implementation: HIDDEN (removed from the workspace)
  unit_tests/           hidden tests: copied in only for evaluation
```

| project | files to generate | hidden tests | where smells are likely (not told to the LLM) |
|---|---|---|---|
| `library_system` | 6 | 21 | `LoanService` absorbing reports/fines (god class); fine computation repeated in reports (duplication); reports reaching into loans/members (feature envy) |
| `shop_orders` | 7 | 20 | tier/discount switching instead of rule objects (missing hierarchy); text vs. CSV invoice totals (duplication); `CheckoutService` absorbing pricing/shipping (god class) |
| `event_scheduler` | 6 | 22 | frequency switching in recurrence (missing hierarchy); conflict checks repeated in `add`/`add_recurring` (duplication); long free-slot search (long method) |

Split (`configs/benchmark.yaml`): **dev** = `library_system` (prompts and thresholds are
tuned here only); **test** = `shop_orders`, `event_scheduler`.

## Rules every project follows
- Standard library only, so there are no dependency installs and tests are fast and deterministic.
- 4–7 files to generate with real cross-file dependencies, so cross-file smells (cycles,
  duplication across modules) are possible. DevBench had only 1 file in 6 of 10 projects.
- **Every behaviour a hidden test checks is stated in the PRD or the UML**: exact
  signatures, error types, ordering, rounding and output formats. Nothing is tested that
  the generator could not know.
- The reference implementation passes 100% of its hidden tests
  (`smells reference --project <name>`). It is reasonably clean, but the gates still fire on
  it (e.g. feature envy on methods that read a dataclass parameter), which gives
  realistic hard negatives for the SLM judges.
- Smells are **not** requested or seeded in the designs. The PRDs are realistic, so a
  single-pass LLM is naturally tempted into the smells listed above.

## Adding a project
1. Create the folder with the layout above; list every file to generate in `code_file_DAG`.
2. Write the PRD/UML first, then the reference, then tests that only check documented behaviour.
3. `smells reference --project <name>` must report all tests passing.
4. Add it to the `split` in `configs/benchmark.yaml` (never move a test project into dev).

## Provenance
The designs, reference implementations and tests were written with an AI assistant
(see `docs/ai_usage.md`) and checked by running the tests on the reference. They need
human review before numbers are reported.
