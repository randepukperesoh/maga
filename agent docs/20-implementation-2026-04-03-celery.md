# 20 - Implementation Log (2026-04-03, celery pipeline)

Completed in this iteration:

## Asynchronous training pipeline with Celery

- Added Celery app config:
  - `apps/backend/app/celery_app.py`
- Added background training task:
  - `apps/backend/app/tasks/training.py`
- Extracted deterministic training runtime function:
  - `apps/backend/app/services/training_runtime.py`
- Refactored training service to async-first workflow:
  - dispatches training via Celery when broker is available
  - tracks `current_task_id`
  - finalizes model when task completes on status/history/models reads
  - supports stop via task revoke
  - falls back to inline training if Celery/broker is unavailable
  - file: `apps/backend/app/services/nn.py`

## Infra updates

- Added `celery` dependency:
  - `apps/backend/requirements.txt`
- Added dedicated worker service:
  - `backend-worker` in `docker-compose.yml`
  - command: `celery -A app.celery_app:celery_app worker -l info`

## Tests and verification

- Added API test for training start/status:
  - `apps/backend/tests/test_api.py`
- Verification run:
  - `pytest tests -q` -> `5 passed`
  - `black --check app tests` -> passed
  - `isort --check-only app tests` -> passed
  - `pnpm --filter training-dashboard build` -> passed
  - `pnpm --filter web build` -> passed
  - `docker compose config` -> valid

## Gap status impact

- Gap #2 (Celery workers + async training pipeline): moved from "not implemented" to "implemented baseline".
- Remaining major gap after this iteration: full model runtime/inference from notebook checkpoint (Gap #5).
