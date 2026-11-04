---
name: message-chains
smell: message_chains
family: code
status: judged
version: 1
---
<!-- Gate: an attribute chain of 3+ hops (a.b().c[x].d), calls and subscripts not counted. -->
## Smell: message_chains

**Definition.** Code navigates through several objects (a.b.c.d) to reach what it needs,
so it depends on the internal structure of every object along the way.

**Confirm when.**
- must: the chain walks through other project objects' internal attributes or collections
  to reach data that the first object could provide directly.
- any of: the same navigation appears more than once; the chain mixes several different
  objects' internals.

**Reject when.**
- A fluent or value-object API designed for chaining: string methods, pathlib paths,
  datetime/date methods, builders, query or DataFrame pipelines.
- The chain only reaches one level into a collaborator's public attribute plus a builtin
  collection method (a.items.values()).
- Module or package paths (os.path.join, package.module.function).

**Severity.** high: the same navigation is repeated or spans 3+ project objects.
medium: one chain through 2 project objects' internals. low: borderline.

**Location:** Class.method or function.

**Fix.** Hide the delegate: add a method on the first object that returns what the caller
needs (name it), and call that instead of navigating.
