# Технологический стек

## Монорепозиторий и инфраструктура

| Компонент        | Технология     | Версия | Назначение                     |
| ---------------- | -------------- | ------ | ------------------------------ |
| Package Manager  | pnpm           | 8.x    | Управление пакетами, workspace |
| Containerization | Docker         | 24.x   | Контейнеризация                |
| Orchestration    | Docker Compose | 2.x    | Запуск всех сервисов           |
| Reverse Proxy    | Nginx          | alpine | Маршрутизация запросов         |
| Database         | PostgreSQL     | 15     | Основное хранилище             |
| Cache            | Redis          | 7      | Кэш, брокер Celery             |

## Основной фронтенд (apps/web)

| Библиотека            | Версия | Назначение              |
| --------------------- | ------ | ----------------------- |
| React                 | 18.2   | UI фреймворк            |
| TypeScript            | 5.x    | Типизация               |
| Vite                  | 5.x    | Сборка                  |
| Zustand               | 4.4    | State management        |
| TailwindCSS           | 3.3    | Стилизация              |
| Fabric.js             | 5.3    | 2D Canvas (конструктор) |
| React Hook Form       | 7.48   | Формы                   |
| Zod                   | 3.22   | Валидация               |
| Recharts              | 2.10   | Графики (эпюры)         |
| shadcn/ui             | latest | Базовые UI-компоненты   |
| @react-pdf/renderer   | 3.2    | PDF генерация           |
| Axios                 | 1.6    | HTTP клиент             |
| @tanstack/react-query | 5.0    | Кэширование             |
| react-hot-toast       | 2.4    | Уведомления             |
| uuid                  | 9.0    | Генерация ID            |
| date-fns              | 2.30   | Работа с датами         |

## Дашборд обучения (apps/training-dashboard)

| Библиотека      | Версия | Назначение            |
| --------------- | ------ | --------------------- |
| React           | 18.2   | UI фреймворк          |
| TypeScript      | 5.x    | Типизация             |
| Vite            | 5.x    | Сборка                |
| Zustand         | 4.4    | State management      |
| Chart.js        | 4.4    | Графики обучения      |
| react-chartjs-2 | 5.2    | Обертка Chart.js      |
| shadcn/ui       | latest | Базовые UI-компоненты |
| Axios           | 1.6    | HTTP клиент           |
| React Hook Form | 7.48   | Формы                 |

## Бэкенд (apps/backend)

| Библиотека       | Версия | Назначение                 |
| ---------------- | ------ | -------------------------- |
| FastAPI          | 0.104  | Web фреймворк              |
| uvicorn          | 0.24   | ASGI сервер                |
| SQLAlchemy       | 2.0    | ORM                        |
| Alembic          | 1.12   | Миграции                   |
| Pydantic         | 2.4    | Валидация                  |
| NumPy            | 1.24   | Математика, МКЭ            |
| SciPy            | 1.11   | Решение систем уравнений   |
| PyTorch          | 2.1    | Нейросеть (или TensorFlow) |
| Celery           | 5.3    | Асинхронные задачи         |
| redis            | 5.0    | Клиент Redis               |
| asyncpg          | 0.29   | PostgreSQL драйвер         |
| python-multipart | 0.0.6  | Обработка форм             |
| ReportLab        | 4.0    | PDF генерация              |
| structlog        | 23.2   | Логирование                |
| pytest           | 7.4    | Тестирование               |
| httpx            | 0.25   | HTTP клиент для тестов     |

## Shared packages

### packages/shared-types

| Библиотека | Назначение                             |
| ---------- | -------------------------------------- |
| TypeScript | Типы, экспортируемые во все приложения |
| zod        | Схемы валидации для общих типов        |

### packages/ui-kit

| Библиотека               | Назначение                        |
| ------------------------ | --------------------------------- |
| React                    | UI компоненты                     |
| TailwindCSS              | Стили                             |
| class-variance-authority | Управление вариантами компонентов |

## Dev dependencies (общие)

| Инструмент   | Назначение                   |
| ------------ | ---------------------------- |
| ESLint       | Линтинг                      |
| Prettier     | Форматирование               |
| Husky        | Git hooks                    |
| lint-staged  | Линтинг staged файлов        |
| concurrently | Параллельный запуск скриптов |
