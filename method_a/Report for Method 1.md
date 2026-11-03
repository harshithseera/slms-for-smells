# Design-Time Code Smell Detection with SLMs: Midsubmission Technical Report

Harshith Seera, Shruthi Bathini, Harshit Lalwani

## 1. Summary

This project asks whether small language models (SLMs) can catch design and code smells in design documents *before* an LLM turns those documents into code. For the midsubmission we built and ran one arm of the proposal: a **design-time advisory pipeline** in which local SLMs read a Mermaid class diagram through an MCP server, produce a Design Advisory Document (DAD), and hand it to a code-generating LLM. We compared three conditions: a **baseline** with no advisory, **A** (fine-tuned LoRA adapters plus skills) and **B** (an untrained base model prompted with the same skills). The pipeline has been run twice. This report treats the second run as the current state and says where it differs from the first: the library test diagram was partly reformatted, and the code-generating model changed from Gemini 2.5 Flash to Gemini 3.1 Flash-Lite.

What was achieved:

- Two LoRA adapters (design smells, code smells) were fine-tuned on synthetic Mermaid diagrams and evaluated on held-out synthetic data.
- A working end-to-end pipeline exists: MCP server, DAD builder, three-condition code generation, and measurement of detection quality, latency, tokens, GPU energy and code-quality proxies.
- On the three seeded test diagrams, the pipeline ran without errors and produced all outputs.

What the results do and do not show, stated plainly:

- In the second run, code generated with a DAD had fewer smells by our proxy metrics than the baseline: 18.3 (A) and 21.7 (B) versus 39.6 smells per KLOC. The direction matches the first run (12.5, 21.4 and 43.7). **We still cannot attribute this to detection quality.** On the store project, condition B, whose DAD was mostly wrong, did slightly better than A (about 27 versus 33 smells per KLOC, baseline about 89), and on the library project B was worse than the baseline. The most likely explanation is that the instruction to "avoid the listed flaws" nudges the LLM toward cleaner code whatever the DAD says. A control experiment is needed to separate the two.
- The fine-tuned detectors perform very well on their own synthetic test sets but poorly on our hand-built diagrams: design recall is 0.14 for both A and B, and code recall is 0.50 for A. This suggests the adapters learned the generator's surface patterns more than the underlying smells.
- The partial diagram fix helped only narrowly. It removed the two false positives A produced on the library diagram, lifting A's design precision from 0.33 to 1.00, while recall stayed at 0.14. That a one-class formatting change altered the model's output is itself a sign of fragility.
- On the clean diagram, the fine-tuned model correctly reported nothing in both runs, while the untrained model produced three false positives. This remains the one clearly positive result for fine-tuning.
- The sample is tiny (three diagrams, two runs per condition), the code-generating model changed between runs, and the quality metrics are our own proxies rather than PyExamine or DPy. Neither of the controls we recommended (a no-DAD "write clean code" prompt, an oracle DAD) has been added yet. Treat all results as preliminary.

## 2. Project goal and scope

The proposal (Project\_Proposal.pdf) motivates the work with a practical problem: LLMs that generate code from class and sequence diagrams inherit flaws such as god classes and tangled dependencies, and fixing smells after code exists is slow and expensive. Existing linters work on finished code, and no approach checks design documents before generation. The proposal's objectives are to (1) build specialised SLMs for design smells and code smells, (2) define a structured Design Advisory Document, and (3) compare approaches on smell detection quality, smell removal, functional correctness, latency, token usage, compute cost and energy.

The proposal describes four comparison arms: a baseline, a design-time advisory (method 1), in-loop monitoring during generation (method 2) and an iterative LLM loop. It also names DevBench projects with unit tests, independent smell tools (PyExamine, DPy), and human-annotated Python smell data.

**Scope of this midsubmission.** Implemented: the baseline and the design-time advisory arm, with both a fine-tuned and an untrained SLM variant. Not yet implemented: in-loop monitoring, the iterative-LLM arm, DevBench and unit-test evaluation, PyExamine/DPy, human-annotated data, and the optional temporal-smell SLM.

## 3. What each document does

| File | Role |
| --- | --- |
| Project\_Proposal.pdf | States the problem, objectives, planned pipeline and evaluation. It is the reference everything else is checked against. |
| design\_smell\_unsloth\_t4.ipynb | Generates synthetic design-smell training data, fine-tunes the design adapter, evaluates it, and exports design\_smell\_lora.zip. |
| code\_smell\_unsloth\_t4.ipynb | Same for the code-smell adapter, exporting code\_smell\_lora.zip. |
| design\_skill.md | A skill specification for design-smell detection: when to use it, which smells exist, what the tool returns, how to build DAD rows, and known limitations. |
| code\_skill.md | The equivalent skill for code smells. |
| dad\_pipeline.ipynb (original) | The first attempt at the pipeline. It did not run (see section 5). |
| dad\_pipeline.ipynb (rewritten; executed copies dad\_pipeline\_1.ipynb and dad\_pipeline\_25dbc5.ipynb) | The current pipeline that was run to produce the results in section 6. |

### 3.1 The design-smell training notebook

The notebook builds a synthetic dataset of Mermaid class diagrams with a generator that creates classes (attributes, methods), dependency edges and inheritance edges, using domain-style names, single letters or numbered modules. Each diagram is labelled by a deterministic rule-based analyser, so the labels are exact but are only as meaningful as the rules:

- **God Class**: 12 or more methods and 4 or more outgoing dependencies.
- **Hub-like Modularization**: 5 or more incoming and 5 or more outgoing dependencies.
- **Data Class**: 6 or more attributes and no methods.
- **Cyclic Dependency**: a strongly connected component of two or more classes (Tarjan's algorithm).
- **Deep Hierarchy**: a leaf class at inheritance depth 4 or more.
- **Wide Hierarchy**: a parent with 8 or more direct subclasses.
- Severity (low/medium/high) is assigned from count thresholds.

The data is split into 3,500 training, 150 validation and 400 test examples. The model is Qwen2.5-1.5B-Instruct (4-bit) with LoRA (rank 16, alpha 16, all attention and MLP projections; 1.18 percent of parameters trainable), trained for 2 epochs at learning rate 2e-4 with loss computed only on the assistant response, at a 3072-token context. The notebook evaluates on the held-out test set and reports invalid-JSON rate, exact match, clean-diagram accuracy, severity accuracy and per-smell precision, recall and F1.

### 3.2 The code-smell training notebook

This notebook generates diagrams of numbered service classes and injects smells deliberately, together with **hard negatives** (near misses, such as a method with four parameters or a method name with only one "And"). Labels again come from string rules:

- **Long Parameter List**: a method signature with 5 or more commas (6 or more parameters).
- **Long Method**: a method name containing "And" at least twice (three or more verbs).
- **Primitive Obsession**: an attribute whose name contains email, phone, zip or currency.
- **Magic Number Risk**: an attribute whose name contains taxrate, discount, retry or timeout.

The split is 4,000 training, 100 validation and 200 test examples; the same base model and LoRA settings are used, trained for 3 epochs at learning rate 1e-4 with a 2048-token context. Note that these diagrams contain no relationships and use a narrow vocabulary.

### 3.3 The skill files

The two skill files are instructions plus reference data for an agent. Each describes when the skill applies, the numbered procedure (accept a diagram, call the MCP tool, retry once on invalid JSON, never invent findings), a table of smells with what triggers them and a standard fix, the JSON output format, rules for building DAD table rows, and a limitations section. Each also lists **unseen smells** the adapters were not trained on (Middle Man, Multifaceted Abstraction and Insufficient Modularization for design; Duplicate Code for code), meant as a generalisation probe, with a rule that findings from these must be marked "\[untrained probe\]" in the DAD. The skills are used in two ways in the pipeline: their tables supply the explanations and fixes in the DAD, and in condition B their text is injected into the untrained model's prompt.

## 4. What the pipeline does

The rewritten notebook runs on a Colab T4 and has these stages.

1. **Setup.** Installs dependencies (with the MCP SDK pinned below version 2, since version 2 removed the FastMCP API), loads the two adapter archives and the two skill files.
2. **Skill parsing.** Reads the smell tables from the skills into lookup tables for explanation, fix and trained-versus-unseen status. It also holds the rule for code-smell severity (Long Parameter List and Long Method medium; the others low).
3. **MCP server (smell-advisor).** One server process loads the 4-bit base model once and attaches both LoRA adapters. It exposes three tools: `detect_design_smells`, `detect_code_smells` and `read_design_doc`. Each detector takes a `mode`: `finetuned` swaps in the matching adapter and uses the exact system prompt from training; `base` disables the adapters and uses a prompt built from the skill's smell table and output format. Optional `probe` and `retry` arguments add the unseen smells to the prompt and enable sampling on a retry.
4. **Seeded design documents.** Three Mermaid diagrams with hand-labelled gold smells: an online store (God Class, Data Class, a three-class cycle, plus five code smells), a library system (Hub-like Modularization, Deep Hierarchy and three code smells), and a small note-taking app with no smells as a clean control. Each has a requirements sentence for the code generator. In the second run only one class of the library diagram (Item) was converted to the multi-line member format; the other single-line classes, including the hub, were left as they were.
5. **Detection through MCP.** For each diagram, the client reads the file via `read_design_doc`, calls both detectors in both modes, retries once on invalid JSON, drops findings that name unknown smells or classes not in the diagram, and records latency and GPU energy (sampled from nvidia-smi) per call after a warm-up.
6. **Detection quality.** Precision, recall and F1 against the gold labels, counting only trained smells; flags for other smells are reported separately.
7. **DAD construction.** One DAD per project per SLM condition, as a table with ID, smell, location, severity, explanation and suggested fix. Design rows are sorted by severity; code findings on the same class and smell are grouped; unseen-smell findings are prefixed "\[untrained probe\]".
8. **Code generation.** Gemini (2.5 Flash in the first run, 3.1 Flash-Lite in the second; temperature 0.2, thinking disabled) generates Python for every project, condition and run. The three prompts are identical except that conditions A and B add the DAD and the instruction to use it to avoid the listed flaws.
9. **Independent quality measurement.** Without involving the SLMs: pylint design checks (too many arguments, attributes, public methods, locals, statements), AST-based counts (long parameter lists, long methods, god classes, classes in dependency cycles, magic numbers), the fraction of diagram classes present in the code, and whether the code parses.
10. **Summary and export.** Per-condition means and an archive of all DADs, generated code, raw SLM outputs and tables.

## 5. Problems found in the original pipeline

The first version of the pipeline had several defects, listed here because they affect how earlier work should be read.

- The cell that wrote the MCP server script built it as an f-string containing literal braces, which raises an error, so the server could not have started.
- The server loaded only the base model and never loaded either LoRA adapter, so "fine-tuned" results would actually have been base-model results.
- The code-smell system prompt in the server differed from the prompt used at training time, which would have degraded the adapter.
- The sample diagram could not trigger a God Class under the training rule, because the class had no outgoing dependencies.
- The rule to label unseen-smell findings was never implemented, the tool names did not match the skills, and `asyncio.run` fails inside Colab's running event loop.

The rewrite fixes these. It was first tested end to end with a stubbed model and a faked LLM client before being run on the GPU.

## 6. Results

### 6.1 Adapter quality on held-out synthetic data (from the training notebooks)

**Design adapter** (400 test diagrams): 0 invalid JSON, exact match 42.0 percent, clean-diagram accuracy 96 of 105, severity accuracy 52.5 percent.

| Smell | Precision | Recall | F1 |
| --- | --- | --- | --- |
| God Class | 0.81 | 0.76 | 0.79 |
| Cyclic Dependency | 0.77 | 0.35 | 0.48 |
| Hub-like Modularization | 0.85 | 0.81 | 0.83 |
| Deep Hierarchy | 0.52 | 0.40 | 0.45 |
| Wide Hierarchy | 0.91 | 0.94 | 0.93 |
| Data Class | 0.97 | 0.91 | 0.94 |

**Code adapter** (200 test diagrams): 0 invalid JSON, exact match 100 percent, clean accuracy 40 of 40, and precision, recall and F1 of 1.00 for all four smells.

Interpretation: the code adapter's perfect score reflects that its labels are simple string rules and its test data comes from the same generator. It shows the model learned the rules in that format, not that it detects these smells in general. The design adapter is credible on count-based smells but weak on cycles and deep hierarchies, and its severity output is only about as good as a coin flip between categories.

### 6.2 Detection on the seeded diagrams

The gold labels follow the same rules used for training, so this tests in-distribution smells on unfamiliar diagrams, not real-world accuracy.

| Condition | Detector | TP | FP | FN | Precision | Recall | F1 | Other smells flagged |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A fine-tuned | Design | 1 | 0 | 6 | 1.00 | 0.14 | 0.25 | 0 |
| A fine-tuned | Code | 4 | 0 | 4 | 1.00 | 0.50 | 0.67 | 0 |
| B untrained | Design | 1 | 4 | 6 | 0.20 | 0.14 | 0.17 | 0 |
| B untrained | Code | 0 | 0 | 8 | 0.00 | 0.00 | 0.00 | 12 |

Behaviour behind the numbers:

- **A, design.** It found only the Data Class on the store diagram and missed the God Class and all three members of the cycle. On the library diagram it now returns nothing (in the first run it returned two wrong findings), so the hub and the deep hierarchy are still missed. Precision rose because wrong answers disappeared, not because more smells were found: 6 of the 7 gold design smells are still missed.
- **A, code.** Unchanged from the first run. It found the Long Method and the email and phone Primitive Obsession in the store, and one finding in the library. It missed the seven-parameter method and the tax-rate Magic Number Risk in the store, and two of three library smells. Because the same rules scored 100 percent in training, this points to overfitting to surface form: training used parameters named arg0, arg1 and similar, whereas our test method used named, typed parameters.
- **B, design.** Unchanged. It correctly found the Data Class, but put Cyclic Dependency on the wrong class and Wide Hierarchy on a class that has no subclasses.
- **B, code.** Unchanged. It reported only "Duplicate Code", the unseen smell, twelve times, including on methods within a single class, which is not what the smell means. It never reported any of the four trained code smells.
- **Clean control.** A returned empty results for both detectors. B produced one design and two code false positives.
- **Run to run.** Finding counts and the store DADs were identical across the two runs (greedy decoding), so the change in A's library result comes from the diagram edit. No invalid JSON occurred and no findings were dropped for naming nonexistent classes.

The unseen-smell probe was **not** run for condition A. The server supports it, but the pipeline used the exact training prompt, so A's DADs never contain probe findings. The generalisation question the skills describe is therefore still open.

### 6.3 Generated code quality

Latest run: means per generation over three projects and two runs each (the SLM columns are the cost of producing that condition's DAD):

| Metric | Baseline | A fine-tuned | B untrained |
| --- | --- | --- | --- |
| AST smells per KLOC | 39.6 | 18.3 | 21.7 |
| pylint design messages | 2.00 | 1.00 | 2.00 |
| Max parameters in a function | 5.0 | 3.8 | 3.7 |
| Functions with more than 5 parameters | 1.00 | 0.50 | 1.00 |
| God classes | 0.33 | 0 | 0 |
| Magic numbers | 1.17 | 0.83 | 0.67 |
| Diagram class coverage | 1.00 | 1.00 | 1.00 |
| LLM input tokens | 285 | 419 | 510 |
| LLM output tokens | 636 | 674 | 721 |
| SLM latency (s) | 0 | 10.1 | 14.4 |
| LLM latency (s) | 1.7 | 4.8 | 2.4 |
| SLM GPU energy (J) | 0 | 325 | 670 |

Per project, smells per KLOC (two runs each):

| Project | Baseline | A | B |
| --- | --- | --- | --- |
| Store | 83.3, 93.8 | 39.0, 26.0 | 25.3, 28.2 |
| Library | 30.3, 29.9 | 13.9, 30.8 | 38.5, 38.0 |
| Notes (clean) | 0, 0 | 0, 0 | 0, 0 |

Observations:

- **Store.** Both DAD conditions cut smells sharply (baseline about 89, A about 33, B about 27). B did slightly better than A even though its DAD named the wrong classes and smells, which is the clearest sign that the DAD's content is not what drives the improvement.
- **Library.** The effect is inconsistent. A improved in one run (13.9) and matched the baseline in the other (30.8 versus 29.9). B was worse than the baseline in both runs (38.5 and 38.0 against about 30), with more pylint messages (6 versus 4) and more functions over five parameters (3 versus 2). With two runs this could be noise, but it is also consistent with a wrong advisory misleading the generator.
- **Notes.** Nothing changed on the clean project, as expected.
- All generated files parse, which is not evidence of functional correctness since no tests were run. Diagram class coverage was 1.00 everywhere. The coverage drop seen in the first run (0.93 for A, 0.97 for B) did not reappear, so it may have been specific to the earlier model or to chance.
- The SLM stage dominated the added cost: 10 seconds (A) and 14 seconds (B) of SLM latency per project against about 2 seconds for a typical LLM call. B uses twice the GPU energy because its prompt carries the skill text and its outputs are longer. Energy is GPU board power only (including idle draw) and does not include the cloud LLM.
- The LLM latency mean for A is inflated by one 15.9 second call and one 4.9 second call, so latency differences between conditions should not be read as meaningful.

### 6.4 What changed between the first and second run

The second run is a modest improvement, not a fix: one diagram edit and one model swap, with no new conditions or controls.

| Aspect | First run | Second run |
| --- | --- | --- |
| Code-generating model | Gemini 2.5 Flash (as set in the notebook provided) | Gemini 3.1 Flash-Lite |
| Library diagram | All members single-line | Item reformatted to multi-line; other classes unchanged |
| A design on seeded diagrams | P 0.33, R 0.14, F1 0.20 | P 1.00, R 0.14, F1 0.25 |
| A code, B design, B code | See 6.2 | Identical |
| Smells per KLOC (baseline / A / B) | 43.7 / 12.5 / 21.4 | 39.6 / 18.3 / 21.7 |
| pylint design messages (baseline / A / B) | 2.00 / 0.67 / 1.33 | 2.00 / 1.00 / 2.00 |
| Class coverage (baseline / A / B) | 1.00 / 0.93 / 0.97 | 1.00 / 1.00 / 1.00 |
| Control conditions added | None | None |

The direction of the main result is stable across both runs: DAD conditions score better than the baseline on smells per KLOC. The size is not: A's advantage over B shrank on pylint, and A's library result is no longer clearly better than the baseline.

## 7. How to read these results honestly

**Supported by the evidence**

- The end-to-end design-time advisory pipeline works and has run twice, including MCP-based access to the design document and both adapters.
- Fine-tuning produces models that emit valid JSON in the required schema every time and stay quiet on a clean diagram, while a prompted untrained model of the same size does not. This held in both runs.
- Code with a DAD in the prompt scored better on average on our proxy metrics than code without one, in both runs and with two different code-generating models (39.6 versus 18.3 and 21.7 smells per KLOC in the second run).

**Not supported by the evidence**

- That the SLM's detections caused the improvement. A's store DAD missed the God Class and the long parameter list yet its code improved; B's DAD was largely wrong yet B matched or beat A on the store; and B's library code was worse than the baseline. A generic instruction to avoid smells may explain most of the effect.
- That fine-tuning improves detection in practice. Design recall is 0.14 and code recall is 0.50 on the seeded diagrams. The one gain in the second run (design precision 0.33 to 1.00) came from false positives vanishing after a formatting edit, not from finding more smells.
- That the approach preserves correctness. No unit tests were run, and the coverage drop from the first run did not reappear, so it tells us nothing either way.
- Any statistical claim. There are three diagrams, two runs per condition, a fixed temperature, and a code-generating model that changed between runs.

**Known limitations of this work**

- Training labels and gold labels come from the same hand-written rules, so "accuracy" measures rule recovery.
- The library diagram is only partly reformatted. Item now uses the multi-line member format, but Media, Book, Novel, Paperback and CatalogHub are still single-line, so the hub and deep-hierarchy results remain confounded by format.
- The code-generating model changed between runs, so absolute numbers are not comparable across them. The baseline moving from 43.7 to 39.6 smells per KLOC gives a rough sense of run-to-run variation.
- The quality metrics are proxies (pylint plus AST checks), not PyExamine or DPy.
- The unseen-smell probe was not run for A, and the untrained condition's prompt treats every skill smell as in scope, so the two conditions are not equivalent on that probe.
- The skills describe the adapter as running on a remote GPU; in the pipeline it runs as a local stdio server on the same Colab machine.

## 8. Recommended next steps

1. **Add two control conditions (not yet done).** A generic "write clean code and avoid common smells" prompt with no DAD, and an **oracle DAD** built from the gold labels. Together with the existing arms these separate the prompt-nudge effect, the cost of detector errors and the ceiling value of a perfect advisory.
2. **Finish and extend the seeded set.** Reformat every library class to multi-line members, add more diagrams in varied styles, include the same diagram in both formats to measure format sensitivity directly, and evaluate the adapters on the training notebooks' own held-out sets inside the pipeline to measure the generalisation gap.
3. **Run the unseen-smell probe for A** using the `probe` option, and report it separately.
4. **Pin the code-generating model and increase runs.** Use one model throughout, more runs per condition, and report variance.
5. **Move to the proposal's evaluation setup.** Use DevBench projects with unit tests for correctness, PyExamine and DPy for smell density, and human-annotated Python smell data for the code detector.
6. **Build the remaining arms.** In-loop monitoring and the iterative-LLM baseline, and the temporal-smell SLM if time permits.
7. **Reduce SLM latency.** Run both detectors in one pass, batch requests or shorten the prompts, since the SLM stage costs several times more than the LLM call it is meant to improve.
