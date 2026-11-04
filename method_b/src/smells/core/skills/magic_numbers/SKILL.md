---
name: magic-numbers
smell: magic_numbers
family: code
status: judged
version: 1
---
<!-- Gate: numeric literals in a function body other than 0, 1, -1, 2; literals in default
     values, subscripts, range() arguments and round()'s digits are skipped. -->
## Smell: magic_numbers

**Definition.** A function uses unexplained numeric literals that encode a business rule or
tunable value (a rate, limit, threshold, weight or price), so the rule is hidden and repeated.

**Confirm when.**
- must: at least one literal is a domain decision someone could want to change (a discount,
  tax rate, fee, threshold, retry limit, scoring weight) rather than a fact of arithmetic.
- any of: the meaning is not obvious from the line itself; the same value appears in several
  places; several such literals combine into one rule.

**Reject when.**
- Unit conversions and calendar or physical facts: 60 (seconds or minutes), 24 (hours),
  7 (days in a week), 12 (months), 100 (percent), 1000 (milli).
- Literals named by a keyword argument that states their meaning (timedelta(days=7)).
- Values whose meaning is the code itself: a string-format width, an HTTP status code, an
  exit code, a well-known protocol or file constant.
- The literal already sits in an ALL_CAPS module constant or a named configuration.

**Severity.** high: several business-rule literals combine into one rule, or one repeats
across functions. medium: one unexplained business-rule literal. low: arguably obvious.

**Location:** Class.method or function.

**Fix.** Name each business value as a module constant or configuration field (say which
names), and use the names in the code.
