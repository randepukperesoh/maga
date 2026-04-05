# 32 - Implementation Log (2026-04-03, mypy + lifespan cleanup)

Implemented in this iteration:

## Backend typing cleanup

- Fixed `mypy` errors in `nn.py` related to nullable runtime-state keys (`str | None` used as dict index).
- Introduced safe state accessor helper and fallback handling for:
  - `last_model_version`
  - `active_inference_model`
- This stabilized typed access paths in:
  - `get_training_status`
  - `get_training_history`
  - `start_training`
  - `predict_defect`

Updated file:

- `apps/backend/app/services/nn.py`

## FastAPI startup deprecation cleanup

- Replaced deprecated `@app.on_event("startup")` initialization with lifespan API.
- Training DB initialization now runs inside app lifespan context manager.

Updated file:

- `apps/backend/app/main.py`

## Verification

- `mypy app` -> passed (`Success: no issues found in 24 source files`)
- `black --check app tests` -> passed
- `isort --check-only app tests` -> passed
- `pytest tests -q` -> `5 passed`
- `pnpm lint:js` -> passed
- `pnpm --filter web build` -> passed
- `pnpm --filter training-dashboard build` -> passed

## Gap impact

- Gap #9 (quality contour) improved:
  - backend typing checks are clean,
  - FastAPI deprecation warning source removed in app startup path.
