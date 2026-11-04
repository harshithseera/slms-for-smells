---
name: long-method
smell: long_method
family: code
status: rule
version: 2
---
<!-- Decided by a static rule in the loop: LOC > long_method_loc or radon CC > long_method_cc;
     high above 2x either threshold. This file gives the definition, severity and fix text,
     and is used if long_method is moved to in_loop.judges. -->
## Smell: long_method

**Definition.** One function does too many steps: long, heavily branching or deeply nested.

**Confirm when.**
- must: it contains 2+ separable steps that could each have a name of their own.
- any of: nesting of 3+ levels; several independent branches; locals used in only one region.

**Reject when.**
- Long but flat and uniform: a lookup table, declarative registrations, argparse setup.
- One algorithm whose steps cannot be named separately (report low at most).
- The length is docstring, comments or a data literal.

**Severity.** high: over 2x a threshold, or 3+ nesting levels with several branches.
medium: over one threshold with separable steps. low: just over, or uniform.

**Location:** Class.method or function.

**Fix.** Extract each named step into a private helper with explicit inputs and outputs;
use guard clauses for nested conditionals; the public method calls the helpers in order.
