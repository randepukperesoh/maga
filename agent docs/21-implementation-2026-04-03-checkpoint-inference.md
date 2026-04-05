# 21 - Implementation Log (2026-04-03, checkpoint inference)

Implemented in this iteration:

## Real checkpoint-based inference baseline

- Added checkpoint model service:
  - `apps/backend/app/services/checkpoint_model.py`
  - supports loading/caching/saving `risk_model.json`
  - configurable path via `RISK_MODEL_PATH`
- Updated prediction pipeline in `nn.py`:
  - uses checkpoint weights (`bias`, `length`, `area`, `load`, `defect`) when available
  - computes risk via sigmoid score
  - keeps heuristic fallback when checkpoint is missing/broken
  - exposes `inference_source` in response (`checkpoint` or `heuristic`)
- On training completion, backend now writes updated checkpoint weights to model file.

## Config updates

- Added env example key:
  - `.env.example`: `RISK_MODEL_PATH=./app/models/risk_model.json`

## Validation

- `pytest tests -q` -> `5 passed`
- `black --check app tests` -> passed
- `isort --check-only app tests` -> passed
- `pnpm --filter training-dashboard build` -> passed
- `pnpm --filter web build` -> passed

## Gap impact

- Gap #5 (notebook model as real runtime): moved from pure heuristic to checkpoint-based runtime baseline.
- Remaining for full closure: richer artifact format and full training-to-checkpoint export parity with notebook.
