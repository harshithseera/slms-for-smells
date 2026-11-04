# Method B: In-Loop Code Smell Monitoring with Small Language Models

A large LLM writes code. Small local language models (SLMs) act as **smell judges** on that
code, and their findings go back to the LLM so it can remove the smells. No model is
trained or fine-tuned: the SLMs are off-the-shelf, prompted with per-smell skill files, and
given deterministic facts from static analysis.

**Smell scope (code smells only).**

| smell | decided by |
|---|---|
| long method, long parameter list | static rules (counts and thresholds) |
| duplicated logic, magic numbers, primitive obsession, data clumps, message chains, flag argument | a cheap static gate finds candidates, then an SLM judge decides |

Each smell has its own definition in `src/smells/core/skills/<smell>/SKILL.md`. The shared
judging rules are in `skills/_shared/RULES.md`.

---

## 1. The monitor (shared by every pipeline)

```
code ──► static facts (AST metrics, radon complexity, import graph,
         renaming-invariant duplicate detection)                  ~ms, no model
           ├─► static rules ──────────────► long method, long parameter list
           └─► gates (loose: find all candidates)
                 └─► SLM judge, one call per candidate per smell
                       prompt = RULES.md + that smell's SKILL.md
                              + neutral task + static facts + code
                       answer = {"reject": {"R1": bool, ...}, "findings": [...]}
                       any reject rule true → no finding
                     ──► confirmed findings (medium/high): smell, location, evidence, fix
```

Design choices:
- **Rules for what can be counted, SLMs for what needs judgement.** The gates are loose on
  purpose. Their recall is the ceiling, and the SLM's job is precision.
- **One narrow question per call.** One smell, one candidate, about 1.2k prompt tokens.
  Small models do worse with several smells at once.
- **A reject checklist.** The judge must answer each "Reject when" rule of the skill
  explicitly. This raised precision more than any rewording of the skills.
- **A neutral prompt.** The judge is not told why the gate fired (it tended to agree with
  the gate). The exception is duplicated logic, which sees the similarity score
  (`judge.show_gate_reason_for`).
- **Strict JSON.** Invalid output gets one retry, then it is dropped and counted.
- **Design-fixed signatures.** A long parameter list that the UML fixes is reported as low,
  so it is never fed back.

## 2. Pipelines

### 2.1 In-loop generation: `smells run --mode in_loop`
The LLM writes a project from its design docs (PRD, Mermaid UML, architecture) one file at
a time, in dependency order. Every `write_file` goes through the monitor. Confirmed
findings come back as the tool result, and the LLM revises the file. A file gets at most
`max_fix_rounds` = 2 revisions, then a final project-wide pass checks cross-file
duplication (1 round). The hidden tests run at the end, and the LLM never sees them.

- `--mode baseline` is the same generator with no monitor: the single-pass reference.
- `--mode in_loop_static` uses rules and gates without the SLM: an ablation.

### 2.2 Scan an existing codebase: `smells scan`
Runs the monitor over any Python codebase. With `--labels`, it scores the findings against
ground truth (precision and recall per smell). Options: `--include`,
`--max-per-smell`, and `--review-csv`, a spot-check sheet with code, verdict and evidence.

### 2.3 Repair once: `smells repair`
1. Take a scan's findings. Two conditions:
   - `slm`: SLM-confirmed findings, sent with the SLM's evidence and fix.
   - `rules`: every gate candidate, unfiltered, sent with the gate's reason and the skill's
     fix pattern.
2. The LLM repairs each affected file once. It may not change public names or signatures,
   and any new helper must live in the same file.
3. Validity checks, not a second pass:
   - The file must parse. If not, one format retry.
   - The module must import. If not, one retry quoting the error, otherwise the file is
     reverted.
4. Run the project's **fixed test set**: the tests that pass on the original code.
5. Re-check. Rules only by default (`--recheck static`), plus a human/LLM review of the
   per-file diffs. A full SLM re-scan is available with `--recheck slm`.

`repair.attribute()` then applies each repaired file **on its own** to the original code
and reruns the tests. That separates "one bad file" from "many bad files".

## 3. Where things live

| component | module |
|---|---|
| model client (OpenAI-compatible: Gemini API, Ollama, …) | `src/smells/core/models.py` |
| design docs + Mermaid parser | `src/smells/core/design_parser.py` |
| static facts | `src/smells/core/static_facts.py` |
| gates + static rules | `src/smells/core/judges/gates.py` |
| SLM judges | `src/smells/core/judges/judges.py` |
| skill files + loader | `src/smells/core/skills/` |
| monitor | `src/smells/core/monitor.py` |
| unit-by-unit generator | `src/smells/core/codegen.py` |
| baseline / in-loop generation, run driver, planner | `src/smells/generation/` |
| scan, repair, detection, tests, quality, CLI | `src/smells/eval/` |
| configs | `configs/dev.example.yaml`, `configs/benchmark.yaml` (frozen) |

## 4. Data

| folder | what | used by |
|---|---|---|
| `data/mock_codebase/gymdesk` + `labels.yaml` | 10 modules, 15 injected code smells, 13 traps, 20 tests | `scan --labels`, `repair` |
| `data/seeded/` | 7 duplicated-logic snippets and traps | `smells detect` |
| `data/projects/` | 3 design-to-code projects (PRD, UML, hidden reference and tests) | `smells run` |
| `data/external/` (git-ignored) | real projects: HTTPie, MkDocs | `scan`, `repair` |

## 5. Logging and outputs
- Generation: `results/runs/<run_id>/{generated/, events.jsonl, summary.json}`, with one
  `monitor_check` event per check and one `llm_call` event per LLM call.
- Scan: a JSON file with every candidate, its verdict, the reject rules that fired, the
  evidence and the latency.
- Repair: `results/repair/<name>_<condition>/{code/, diffs/, repair.json, attribution.json}`.
- Every run logs the skill files' versions and hashes.

## 6. Protocol
- **Freeze before reporting:** models (exact ids and quantisation), decoding settings, gate
  thresholds and skill versions in `configs/benchmark.yaml`. Record the date of API runs.
- **Dev vs. held-out:** tune prompts and gates on the dev data only (gymdesk, HTTPie).
  MkDocs is held out.
- **Repeats:** Gemini isn't deterministic even at temperature 0, so run each repair
  condition 3 or more times when reporting.
- **Hardware:** laptop latency varies about 3× under sustained load. Report a range.

## 7. Pitfalls seen so far
- **Rubber-stamping:** the judge agrees with the gate. Watch the share of calls where a
  reject rule fires. Near zero, as for flag argument, means it isn't judging.
- **One-file-at-a-time repair can't fix cross-file smells.** Duplicates across files, data
  clumps and message chains whose fix belongs in another module come out duplicated or
  unchanged.
- **A single bad file zeroes a test suite,** for example through a missing import. That is
  why the import check and per-file attribution exist.
- **Acting on false positives creates new smells,** for example splitting a `dry_run` flag
  duplicated a loop.

## 8. Open decisions
- [ ] Gate-level fixes for flag argument and data clumps (validate on a new repo)
- [ ] 1.5B vs. 7B per smell; self-consistency on borderline cases
- [ ] Repeated repair runs; a SonarQube baseline; energy measurement
