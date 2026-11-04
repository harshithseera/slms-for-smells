---
name: flag-argument
smell: flag_argument
family: code
status: judged
version: 2
---
<!-- Gate: a parameter annotated bool, or defaulting to True/False, that is tested in an if
     or conditional expression in the body. -->
## Smell: flag_argument

**Definition.** A boolean parameter switches a function between two different behaviours,
so one function does two jobs and callers pass an unexplained True or False.

**Confirm when.**
- must: the two branches do different jobs (different results, side effects or output
  types), not the same job with a small variation.
- any of: the function's name describes only one of the behaviours; callers would read more
  clearly as two separately named functions.

**Reject when.**
- Both branches do the same job and differ only in a detail of it: verbosity, eager vs
  lazy work, including or skipping an optional part, skipping a side effect (dry_run),
  refreshing or bumping something along the way, a sort direction. (A flag that changes
  the RETURN TYPE or turns one job into an opposite job is not such a detail.)
- The flag only says which state the caller is in (is_finished, first_run) and the
  function reports or renders that state.
- The flag is forwarded unchanged to a library call (sorted(reverse=...)).
- The design, a public interface, a framework hook or an overridden method fixes the parameter.

**Severity.** high: the branches return different types or have unrelated side effects.
medium: two clearly different jobs. low: borderline option.

**Location:** Class.method or function.

**Fix.** Split it into two well-named functions, one per behaviour (name them); share any
common part through a private helper.
