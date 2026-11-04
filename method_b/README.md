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

## Running (from `method_b/`)
```bash
# scan a codebase; with --labels, score against ground truth
smells scan data/mock_codebase/gymdesk --labels data/mock_codebase/labels.yaml --config configs/dev.yaml --out results/scan.json
smells scan data/external/httpie --include httpie --config configs/dev.yaml --out results/httpie.json --review-csv results/httpie.csv

# one repair pass from a scan's findings, then tests + re-check
smells repair data/mock_codebase/gymdesk --scan results/scan.json --condition slm \
  --out results/repair/gymdesk_slm --python ../.venv/bin/python --test-args "unit_tests" --config configs/dev.yaml

# generate a project from design docs: in-loop vs. single-pass baseline
smells run --mode in_loop baseline --project library_system --config configs/dev.yaml
smells compare --markdown

smells detect --config configs/dev.yaml           # seeded duplicated-logic snippets
smells reference --project library_system         # hidden tests pass on the reference code
```
