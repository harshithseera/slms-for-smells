---
name: long-parameter-list
smell: long_parameter_list
family: code
status: rule
version: 2
---
<!-- Decided by a static rule in the loop: more than long_parameter_list parameters (self/cls
     excluded, *args/**kwargs count one each); a signature fixed by the UML is reported low.
     Planned: data clumps (the same 3+ names across 2+ signatures). -->
## Smell: long_parameter_list

**Definition.** A function takes too many parameters, usually because some belong together
as one concept or because it does too many things.

**Confirm when.**
- must: 3+ parameters form a cohesive group (x, y, z; host, port, user; start, end, step),
  or the parameters serve 2+ unrelated purposes.

**Reject when.**
- The design (UML signature) fixes this exact parameter list (report low; fix internally).
- Keyword-only options with defaults on a public entry point mirroring a known interface.
- A record (dataclass) constructor where each parameter is a field.

**Severity.** high: more than threshold + 3, or the same group recurs in 2+ signatures.
medium: over the threshold with a clear group. low: fixed by the design.

**Location:** Class.method or function.

**Fix.** Introduce a parameter object (a dataclass named after the concept) for the group,
or split the function by purpose; if the design fixes the signature, build the object inside.
