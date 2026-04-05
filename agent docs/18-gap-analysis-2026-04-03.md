# 18 - Gap Analysis (2026-04-03)

По доке и текущему состоянию кода в приложении не хватает:

1. [Частично закрыто] Нет полноценного слоя данных для обучения: SQLAlchemy/Alembic/PostgreSQL модели и миграции отсутствуют, состояние обучения хранится в памяти и теряется при рестарте.  
   См.: `07-backend-api.md`, `apps/backend/app/services/nn.py`, `apps/backend/requirements.txt`.

2. Нет Celery-воркеров и асинхронного пайплайна обучения, хотя это требование спринта и стека.  
   См.: `15-development-plan.md`, `docker-compose.yml`.

3. [Частично закрыто] В training-dashboard нет CRUD датасета (таблица/поиск/редактирование), есть только мониторинг/старт/история.  
   См.: `06-frontend-training-dashboard.md`, `apps/training-dashboard/src/features/training/api/trainingApi.ts`.

4. [Закрыто] Нет `stop training`, логов обучения и WebSocket-стрима метрик (только polling).  
   См.: `15-development-plan.md`, `apps/backend/app/api/routes.py`.

5. Нейросеть пока не как полноценная модель из ноутбука: сейчас эвристика/сигналы, без реального инференса чекпоинта и дообучения.  
   См.: `10-neural-network.md`, `apps/backend/app/services/notebook_integration.py`, `apps/backend/app/services/nn.py`.

6. [Частично закрыто] Конструктор `web` не закрывает часть UX-функций из доки: нет нормального drag узлов, панорамирования, zoom, расширенного редактирования через формы.  
   См.: `05-frontend-constructor.md`, `apps/web/src/widgets/canvas-panel/ui/RodCanvas.tsx`.

7. [Частично закрыто] Основной фронт `web` не переведен на shadcn как базовую UI-систему (в доке это требование).  
   См.: `14-code-quality.md`, `apps/web/package.json`.

8. PDF-отчет пока упрощенный: нет схемы конструкции, графиков/эпюр, рекомендаций и полноценной структуры отчета.  
   См.: `11-pdf-report.md`, `apps/backend/app/services/pdf.py`.

9. Нет части инфраструктуры качества кода: ESLint/Prettier/Husky/lint-staged/Black/isort/mypy и CI-контура.  
   См.: `14-code-quality.md`, `package.json`.

10. [Закрыто] Не хватает `packages/ui-kit` и расширенного `shared-types` из технологической доки.  
    См.: `02-technology-stack.md`, `packages/shared-types/src/index.ts`.

---

## Обновление статуса (итерация 2026-04-03)

Сделано в этой итерации:

- Backend:
  - Добавлены endpoint'ы:
    - `POST /api/v1/training/stop`
    - `GET /api/v1/training/logs`
    - `GET /api/v1/training/dataset`
    - `POST /api/v1/training/dataset`
    - `PUT /api/v1/training/dataset/{sample_id}`
    - `DELETE /api/v1/training/dataset/{sample_id}`
  - Расширены training-схемы (`training.py`) под stop/logs/dataset.
  - Расширен сервис `nn.py`:
    - хранение/выдача training-логов
    - stop training
    - in-memory CRUD датасета

- Training Dashboard:
  - Добавлены API-методы для stop/logs/dataset.
  - Добавлены UI-блоки:
    - `TrainingDataset` (добавление и удаление sample, таблица dataset)
    - `TrainingLogs` (просмотр логов обучения)
  - Добавлена кнопка `Остановить обучение` в `TrainingControls`.
  - Обновлен `useTrainingPage` с поддержкой dataset/logs/stop.

Проверка:

- `pnpm --filter training-dashboard build` — успешно.
- `pytest tests -q` (backend) — `4 passed`.

## Обновление статуса (итерация 2026-04-03, слой данных)

Сделано:

- Backend:
  - Добавлен SQLAlchemy storage-модуль:
    - `app/db/training_store.py`
    - таблицы: `training_dataset_samples`, `training_logs`
    - CRUD для dataset + чтение/запись training logs
  - Инициализация training DB на startup:
    - `app/main.py` (`init_training_db`)
  - `nn.py` переведен на DB-операции для dataset/logs (с fallback на in-memory для логов).
  - В `requirements.txt` добавлены:
    - `sqlalchemy`
    - `alembic`

Проверка:

- Backend tests: `pytest tests -q` — `4 passed`.
- Training dashboard build: `pnpm --filter training-dashboard build` — успешно.

## Обновление статуса (итерация 2026-04-03, web shadcn migration)

Сделано:

- `apps/web`:
  - Инициализирован официальный `shadcn` (`init`) и добавлены компоненты (`button`, `card`, `input`, `select`, `badge`, `table`, `label`, `switch`, `textarea`).
  - Добавлен alias `@/*` в:
    - `apps/web/tsconfig.json`
    - `apps/web/vite.config.ts`
  - Ключевые панели переведены на shadcn-компоненты:
    - `widgets/editor-toolbar/ui/EditorToolbar.tsx`
    - `widgets/analysis-settings/ui/AnalysisSettingsPanel.tsx`
    - `widgets/defects-panel/ui/DefectsPanel.tsx`
  - Обновлены базовые стили `apps/web/src/app/styles/index.css` для совместимости c текущей Tailwind-конфигурацией.

Проверка:

- `pnpm --filter web build` — успешно.

## Обновление статуса (итерация 2026-04-03, canvas UX)

Сделано:

- В `RodCanvas` добавлены UX-механики:
  - zoom колесом мыши;
  - pan через `Space + drag`;
  - drag узлов с snap-to-grid и обновлением координат в store.
- В `editorStore` добавлен метод `moveNode`.

Проверка:

- `pnpm --filter web build` — успешно.

## Обновление статуса (итерация 2026-04-03, realtime + env)

Сделано:

- Backend realtime:
  - Добавлен WebSocket endpoint `GET ws /api/v1/training/ws` (snapshot status + logs каждые 2s).
  - Добавлен helper `get_training_stream_payload` в `app/services/nn.py`.
- Training dashboard:
  - Подключение к `ws://.../api/v1/training/ws` в `useTrainingPage` с fallback на polling.
- Infra/env:
  - Добавлен `.env.example` в корень репозитория.
  - В `docker-compose.yml` для backend добавлены:
    - `TRAINING_DB_URL=sqlite:///./data/training.db`
    - volume `backend_data:/app/data` для персистентности training dataset/logs.

Проверка:

- `pytest tests -q` (backend) — `4 passed`.
- `docker compose config` — валидно.

## Обновление статуса (итерация 2026-04-03, Alembic baseline)

Сделано:

- Добавлена базовая Alembic-конфигурация backend:
  - `apps/backend/alembic.ini`
  - `apps/backend/alembic/env.py`
  - `apps/backend/alembic/script.py.mako`
  - `apps/backend/alembic/versions/0001_training_tables.py`
- Создана первая миграция для таблиц:
  - `training_dataset_samples`
  - `training_logs`

Проверка:

- `alembic upgrade head` — успешно.
- `pytest tests -q` (backend) — `4 passed`.

## Обновление статуса (итерация 2026-04-03, shared packages)

Сделано:

- Добавлен пакет `packages/ui-kit`:
  - `packages/ui-kit/package.json`
  - `packages/ui-kit/src/index.ts`
- Расширен `packages/shared-types/src/index.ts`:
  - добавлены типы для нагрузок/ограничений/дефектов/расчетов/training-dataset.
