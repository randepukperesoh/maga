# Rod System Designer (MVP)

Монорепозиторий по `agent docs`:

- `apps/web` — конструктор стержневых систем (React + Fabric.js + Zustand)
- `apps/training-dashboard` — дашборд обучения (React)
- `apps/backend` — FastAPI API (`/health`, `/calculate`, defects CRUD, `/predict-defect`, `/report`)
- `packages/shared-types` — общие типы
- `docker-compose.yml` — запуск всей системы

## Запуск

```bash
docker-compose up --build
```

После запуска:

- Web: `http://localhost/`
- Training dashboard: `http://localhost/training/`
- API: `http://localhost/api/v1/health`

## Фолбэк: запуск без Docker

Требования:

- Node.js + `pnpm`
- Python 3.11+ (зависимости backend ставятся в `.venv`)

Подготовка:

```bash
pnpm install
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r apps/backend/requirements.txt
```

Автозапуск (Windows PowerShell, в отдельных окнах):

```bash
pnpm run dev:local
```

Или только API + Web (без training-dashboard):

```bash
pnpm run dev:local:web-only
```

Что поднимется:

- Web: `http://localhost:5173/`
- Training dashboard: `http://localhost:5174/`
- API: `http://localhost:8000/api/v1/health`

Примечания:

- В non-docker режиме backend использует SQLite (`apps/backend/data/training.db`) как fallback.
- Redis/Celery не обязателен: при недоступности брокера обучение падает в inline-режим.

## Статус реализации

Сделан рабочий MVP-каркас согласно документации, с базовыми эндпоинтами и визуальным конструктором.
МКЭ/нейросеть/PDF сейчас в формате базовой серверной реализации-заглушки, готовой к углублению по спринтам 3-7.