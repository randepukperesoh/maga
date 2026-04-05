# 27 - Implementation Log (2026-04-03, postgres-first training DB)

Implemented in this iteration:

## Training data layer: PostgreSQL-first configuration

- Switched environment defaults to PostgreSQL for training storage:
  - `.env.example`: `TRAINING_DB_URL=postgresql+psycopg://...`
  - `docker-compose.yml`: backend and backend-worker now use `TRAINING_DB_URL=postgresql+psycopg://...`

## Backend DB URL normalization

- Updated training storage URL resolver to support robust fallback and driver normalization:
  - prefers `TRAINING_DB_URL`, then `DATABASE_URL`, then sqlite fallback
  - auto-converts `postgresql+asyncpg://` -> `postgresql+psycopg://` for sync SQLAlchemy engine
- Updated files:
  - `apps/backend/app/db/training_store.py`
  - `apps/backend/alembic/env.py`

## Dependency update

- Added sync PostgreSQL driver dependency:
  - `psycopg[binary]>=3.2,<4` in `apps/backend/requirements.txt`

## Verification

- `pytest tests -q` -> `5 passed`
- `pnpm --filter web build` -> passed
- `pnpm --filter training-dashboard build` -> passed
- `docker compose config` -> valid and shows postgres training DB URL for backend and worker

## Gap impact

- Gap #1 (data layer persistence) improved toward full closure:
  - training runtime now configured PostgreSQL-first in docker env.
  - sqlite remains as fallback for local/test resilience.
