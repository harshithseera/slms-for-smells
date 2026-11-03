# Method A: Design-time advisory (DAD)

SLMs check the design documents (UML class and sequence diagrams) for smells before any code
is written and produce a Design Advisory Document (DAD). The code-generating LLM receives
the DAD together with the design.

This folder is for the DAD work: the pipeline, the SLM artifacts, the skill files and the
results. It is independent of `method_b/`.
