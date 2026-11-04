---
name: data-clumps
smell: data_clumps
family: code
status: judged
version: 2
---
<!-- Gate: the same 3+ parameter names (self/cls excluded) appear together in 2+ function
     signatures across the project; one candidate per shared name set (up to 3 functions). -->
## Smell: data_clumps

**Definition.** The same group of values travels together through several signatures,
because together they form one concept that has no type of its own.

**Confirm when.**
- must: the shared parameters describe one concept (a date range, a time slot, an address,
  connection settings) rather than independent inputs.
- any of: the functions do related work on that group; the group is checked or combined the
  same way in each function.

**Reject when.**
- The shared names are independent, coincidentally common inputs (ids of different things,
  a "now" timestamp, a logger).
- One function only forwards the values to the other (a thin wrapper with the same signature).
- The parameters are the fields of an existing type that the function constructs.
- The signature is dictated from outside: the method overrides a base-class or library
  method, or is a framework hook or callback whose parameters the framework fixes (for
  example a command-line action, a parser or lexer callback, an event handler, __call__).
- The functions are overrides of the same method in different classes (polymorphism).

**Severity.** high: the group appears in 3+ signatures. medium: in 2 with related logic.
low: borderline cohesion.

**Location:** the functions as given, separated by " | ".

**Fix.** Introduce one parameter object (a dataclass named after the concept, with the
shared fields) and pass it in each function.
