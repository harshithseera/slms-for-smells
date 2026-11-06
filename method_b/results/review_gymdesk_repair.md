# Manual review of the gymdesk repair diffs (first pass, temperature 0)

The reviewer read every per-file diff and gave each finding sent to Gemini one verdict:
fixed, partly fixed, not fixed (unchanged or cosmetic), or acted on a false positive.
Newly introduced smells were noted in changed code only, using the same skill definitions.

## SLM-filtered condition (16 findings; 20/20 tests still pass)

| verdict | count | findings |
|---|---|---|
| fixed | 5 | magic numbers ×2 (`charge_monthly_fees`, `loyalty_score`); flag argument ×2 (`apply_charge`, `session_summary`, both split with a thin dispatcher kept); long method (`plan_week`, 4 helpers extracted) |
| partly fixed | 2 | primitive obsession ×2 (one `Currency.validate` removes the repeated checks, but raw strings are still passed and the enum members are unused) |
| not fixed | 7 | cross-file duplicate (`_calculate_total` written into BOTH files); data clumps ×2 (cosmetic dataclass wrapping, signatures unchanged; `ClassSlot` defined in two files); long parameter list ×2 (unchanged, correct under "keep signatures"); message chains ×2 (file unchanged; the fix needs a method in another file) |
| false positive acted on | 2 | `send_reminders(dry_run)` split, duplicating the loop; `mean` vs `geometric_mean` given a generic lambda helper |

New smells introduced: 3 (two cross-file duplicates, `_calculate_total` and `ClassSlot`; a duplicated reminder loop), plus some dead code.

## All-candidates condition (26 findings, 10 of them traps; 17/20 tests still pass in the first run)

- **Fixed a real smell the SLM had missed:** the e-mail duplicate became one `_render_email`. A dead `_base_email` with the old duplicated logic was left behind.
- **Message chains fixed locally:** `_class_for()` hides the navigation once.
- **About 8 edits for traps:** `// 60` became `_SECONDS_PER_MINUTE`; an `Email` value class nobody asked for; `dry_run` split again.
- **Behaviour broken:** the `plan_week` refactor breaks 1 test on its own. `test_billing` and `test_export_and_report` fail only in combination with the billing, club and reports edits.

## Cross-cutting observations

1. Per-file repair fixes local smells (magic numbers, flags, long methods). It does not fix cross-file smells: helpers get duplicated into each file, or the code is left unchanged.
2. Every SLM false positive led to an unnecessary edit, and one of them created a new smell.
3. "Keep public signatures" correctly stops long-parameter-list fixes that would break callers.
