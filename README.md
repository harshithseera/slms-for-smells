# slms-for-smells

**Design-Time and In-Loop Code Smell Detection with Small Language Models**

Harshith Seera, Shruthi Bathini, Harshit Lalwani

Can small local language models (SLMs) keep code smells out of code that a large LLM writes,
and which point of intervention works best? The two methods are developed independently,
each in its own self-contained folder:

| folder | method | when the SLMs intervene |
|---|---|---|
| [`method_a/`](method_a/) | **Design-time advisory (DAD)**: SLMs check the design documents and produce a Design Advisory Document that the code-generating LLM receives | before code is written |
| [`method_b/`](method_b/) | **In-loop monitoring**: SLMs judge the code the LLM writes, and their findings go back to the LLM for fixing | while and after code is written |
