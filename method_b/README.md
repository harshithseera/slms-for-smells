# Method B: In-loop code smell monitoring with SLMs

A large LLM (Gemini) writes or repairs Python code. Small local language models (Ollama,
e.g. `qwen2.5-coder:7b`) act as per-smell judges on that code, and their findings
(smell, location, evidence, fix) go back to the LLM. Nothing is trained or fine-tuned.
The full method description is in [docs/in_loop.md](docs/in_loop.md).

**Code smells covered:**
- **Static rules:** long method, long parameter list.
- **Gate, then SLM judge:** duplicated logic, magic numbers, primitive obsession, data
  clumps, message chains, flag argument.

## Layout
```
src/smells/
  core/          model client, static facts, gates + rules, SLM judges, skill files, monitor,
                 unit-by-unit code generator, design-doc parser
  generation/    in-loop generation, single-pass baseline (the reference), run driver, planner
  eval/          CLI (run.py), scan, repair, detection eval, hidden-test runner, quality metrics
configs/         dev.example.yaml (copy to dev.yaml), benchmark.yaml (frozen for reported numbers)
data/            mock_codebase/ (labelled), seeded/, projects/, external/ (git-ignored real repos)
results/         scan, repair and generation outputs
docs/            in_loop.md: the method
tests/           pytest suite (fake models, no network needed)
```

## Setup
From the repository root (one virtualenv for the package):
```bash
uv venv && source .venv/bin/activate
uv pip install -e 'method_b[dev]'
cd method_b
cp configs/dev.example.yaml configs/dev.yaml      # models: codegen (API) + judge_code (Ollama)
cp .env.example .env                              # add GEMINI_API_KEY
OLLAMA_CONTEXT_LENGTH=8192 ollama serve           # in another terminal
ollama pull qwen2.5-coder:7b
smells check --config configs/dev.yaml            # codegen tool call, judge JSON, judge context
pytest
```

## Usage guide

Run every command from `method_b/` with the virtualenv active. Keep Ollama running in a
second terminal (`OLLAMA_CONTEXT_LENGTH=8192 ollama serve`) for anything that calls the SLM.
Commands with `--static-only` need no models at all.

### 0. Check the models
```bash
smells check --config configs/dev.yaml
```
Expect `ok` for the codegen tool call and the judge JSON. The context-probe line uses a
deliberately oversized prompt: a warning there does not affect normal scans, whose prompts
are under about 3.3k tokens.

### 1. Detect smells: `smells scan`
```bash
# labelled mock codebase: precision and recall per smell, rules alone vs. rules + SLM
smells scan data/mock_codebase/gymdesk --labels data/mock_codebase/labels.yaml \
  --config configs/dev.yaml --out results/scan_gymdesk.json

# a real codebase (unlabelled): per-smell counts, plus a spot-check sheet
smells scan data/external/httpie --include httpie --config configs/dev.yaml \
  --out results/httpie.json --review-csv results/httpie_review.csv

# rules only, instant, no models
smells scan data/mock_codebase/gymdesk --labels data/mock_codebase/labels.yaml --static-only
```
| option | effect |
|---|---|
| `--labels FILE` | score against a ground-truth file (format in section 6) |
| `--include DIR …` | only scan these subfolders. Tests (`tests/`, `unit_tests/`, `test_*.py`, `conftest.py`) are always skipped |
| `--max-per-smell N` | randomly sample at most N candidates per smell (`--seed` for reproducibility) |
| `--review-csv FILE` | one row per candidate: code, SLM verdict, evidence, fix, and empty columns for a human label |
| `--temperature T` | override the judge's temperature (default 0, which gave the best precision/recall) |
| `--static-only` | gates and rules only, no SLM |

Output JSON: every candidate with its gate reason, the SLM verdict, the reject rules that
fired (`rejected_by`), evidence, fix and latency. Plus per-smell counts and, with labels,
`scores` and `verdicts`. Expect roughly 10–30 s per SLM call on a laptop (about 1 call per
100 lines of code).

### 2. Repair once: `smells repair`
Takes a scan's findings, lets the code-gen LLM fix each affected file once, then runs the
project's tests and a re-check.
```bash
smells repair data/mock_codebase/gymdesk --scan results/scan_gymdesk.json --condition slm \
  --out results/repair/gymdesk_slm --python ../.venv/bin/python --test-args "unit_tests" \
  --config configs/dev.yaml
```
| option | effect |
|---|---|
| `--condition slm` | send only SLM-confirmed findings (with the SLM's evidence and fix) |
| `--condition rules` | send every gate candidate, unfiltered (the comparison condition) |
| `--python PY` | an interpreter that has the project's test dependencies |
| `--test-args "…"` | arguments for `pytest`. Only tests that pass on the original code count |
| `--include DIR …` | same as for `scan`: use the same value as the scan that produced the findings |
| `--temperature T` | override the code-gen LLM's temperature |
| `--recheck static\|slm\|none` | after repair: rules-only re-scan (default), full SLM re-scan, or tests only |

Test settings used for the three codebases:

| codebase | `--python` | `--test-args` |
|---|---|---|
| gymdesk | `../.venv/bin/python` | `"unit_tests"` |
| HTTPie | `.venvs/httpie/bin/python` | `"tests -o addopts= -m 'not requires_installation and not requires_external_processes'"` |
| MkDocs | `.venvs/mkdocs/bin/python` | `"mkdocs -o addopts= -o python_files=*tests.py"` |

Output in `--out`: `code/` (the repaired copy, git-ignored), `diffs/` (one diff per edited
file), `repair.json` (per-file status, retries, tokens, tests, re-check), `scan_after.json`.
A file whose reply is not valid Python gets one format retry. A module that fails to
import gets one retry with the error, and is otherwise reverted. Both are recorded per file.

Then find out which edited files break tests **on their own** (one bad file can stop a
whole suite):
```bash
smells attribute results/repair/gymdesk_slm data/mock_codebase/gymdesk \
  --python ../.venv/bin/python --test-args "unit_tests"
```
For HTTPie, add `-n 4` to `--test-args` (needs `pytest-xdist` in its env) to run in parallel.

### 3. Collect report statistics: `smells stats`
```bash
smells stats      # → results/report_stats.md and results/report_stats.json
```
Reads every finished scan and repair run. It reports precision/recall per pipeline
version, judge behaviour (confirm rate, how often a reject rule fired, gate echo,
latency), and repair results per run and aggregated over repeats (mean ± spread). Rerun it
whenever new runs finish.

### 4. Generate code from designs: `smells run`
```bash
smells run --mode in_loop baseline --project library_system --config configs/dev.yaml
smells compare --markdown
```
`--mode in_loop` monitors every file the LLM writes. `baseline` is a single pass with no
feedback. `in_loop_static` uses rules only. `--project all` runs every project in
`data/projects/`, and `--repeats N` repeats each run. Outputs:
`results/runs/<run_id>/{generated/, events.jsonl, summary.json}`.

### 5. Other commands
```bash
smells detect --config configs/dev.yaml       # seeded duplicated-logic snippets (data/seeded)
smells reference --project library_system     # the hidden tests pass on the reference code
```

### 6. Using your own codebase
- **Scan only:** point `smells scan` at the folder. Use `--include` for the package
  directory if the repo also has docs or tooling.
- **Repair:** also needs a test environment with the project's dependencies:
  ```bash
  uv venv -p 3.12 .venvs/myproject
  uv pip install -p .venvs/myproject/bin/python pytest <the project's deps>
  ```
  If the project registers plugins or themes through package metadata (MkDocs does), also run
  `uv pip install -p .venvs/myproject/bin/python --no-deps <path to the project>`. The tests
  still import the code under test first.
- **Labels** for scoring (`--labels`): a YAML file outside the codebase with three lists:
  ```yaml
  smells:      # real, injected smells
    - {id: C1, smell: magic_numbers, file: pkg/billing.py, target: compute_fee}
    - {id: C2, smell: duplicated_logic, file: pkg/a.py, target: "pkg/a.py::f|pkg/b.py::g"}
  negatives:   # traps: a gate fires but the smell is absent
    - {id: N1, smell: magic_numbers, file: pkg/time.py, target: Slot.minutes}
  borderline:  # defensible either way; not scored
    - {id: B1, smell: primitive_obsession, file: pkg/mail.py, target: domain}
  ```
  `target` is a `Class.method` or function name. For duplicated logic and data clumps it is
  the functions, joined with `|`.

### 7. Configuration (`configs/dev.yaml`, layered on `dev.example.yaml`)
| key | meaning |
|---|---|
| `models.codegen` | the code-writing LLM (OpenAI-compatible: `base_url`, `model`, `api_key_env`, `temperature`, `extra_body`) |
| `models.judge_code` | the SLM judge (Ollama); keep `json_mode: false` |
| `in_loop.judges` / `in_loop.static_only_smells` | which smells the SLM judges / which the rules decide |
| `judge.show_gate_reason`, `judge.show_gate_reason_for`, `judge.reject_checklist` | prompt switches (the defaults are the best-measured setting) |
| `gates.*` | rule thresholds (long method lines/complexity, parameter count, duplicate similarity) |

Freeze `configs/benchmark.yaml` (exact model ids, settings and date) before collecting
numbers you report.

### 8. Troubleshooting
| symptom | fix |
|---|---|
| `Connection refused` for the judge | start Ollama: `OLLAMA_CONTEXT_LENGTH=8192 ollama serve` |
| Gemini `400 … Unknown name "seed"` | set `seed: null` under `models.codegen` |
| Gemini `429` rate limits | handled automatically: retries with backoff, honouring `Retry-After` |
| judge always says `{"findings": []}` | `json_mode` is on: set `models.judge_code.json_mode: false` |
| a repaired suite shows 0% | usually one file fails to import: see `repair.json` (`import_error`) and run `smells attribute` |
| slow scans | expected on a fanless laptop (8–30 s per call). Plug in, close heavy apps, or use `--max-per-smell` |
