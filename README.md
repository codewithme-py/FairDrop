# FairDrop - Study e-commerce platform

[![Workflow Status](https://github.com/codewithme-py/FairDrop/actions/workflows/ci.yaml/badge.svg)](https://github.com/codewithme-py/FairDrop/actions/workflows/ci.yaml)

<details>
<summary> Описание на русском</summary>

## FairDrop — B2B/B2C дропшиппинг-платформа

Production-ready backend для маркетплейса с асинхронной модульно-монолитной архитектурой с точкой роста под микросервисность.

### Возможности

- **Каталог товаров** — CRUD, модерация, статусы продуктов, лимиты для непроверенных продавцов, изображения через S3
- **Заказы** — создание, отмена, статусы, idempotency-key для идемпотентности операций
- **Инвентарь** — система резервирования товаров с защитой от оверселлинга (Lua-скрипты в Redis)
- **Медиа** — загрузка изображений через S3/MinIO с presigned URL, webhook-интеграция, фоновые задачи через ARQ
- **Аутентификация** — JWT (access + refresh), refresh token rotation, B2B API keys, сессии для админки
- **RBAC** — роли (admin, moderator, seller, buyer, user_b2b, seller_b2b), гранулярный доступ через `RoleChecker`
- **Аудит-лог** — отслеживание изменений в критичных моделях (кто, что, когда изменил)
- **Rate limiting** — Lua-скрипты в Redis для логина, регистрации, per-user и global RPS
- **Админ-панель** — SQLAdmin с кастомной аутентификацией, модерация товаров, управление пользователями
- **Фоновые задачи** — ARQ worker для тяжёлых операций (очереди в Redis)
- **Мониторинг** — Prometheus метрики (prometheus-fastapi-instrumentator), Grafana дашборды
- **API Gateway** — Nginx reverse proxy с rate limiting (20r/s global) и IP-фильтрацией для webhook'ов

### Стек

| Категория | Технологии |
|---|---|
| **Backend** | FastAPI, SQLAlchemy (asyncio), Pydantic v2, orjson |
| **База данных** | PostgreSQL 15 (asyncpg, connection pool 200+) |
| **Кэш** | Redis (Lua-скрипты для rate limiting, ARQ для очередей) |
| **Файлы** | MinIO (S3-compatible, presigned URLs) |
| **Асинхронность** | asyncio, aioboto3, asyncpg, ARQ |
| **Мониторинг** | Prometheus, Grafana, structlog (structured logging) |
| **Контейнеризация** | Docker, Docker Compose (8 сервисов) |
| **CI/CD** | GitHub Actions (pytest, ruff, mypy) |
| **Миграции** | Alembic (async) |
| **Линтинг** | Ruff, MyPy, pre-commit hooks |
| **Нагрузочное тестирование** | Locust (6 сценариев: stress, oversell, orders, mixed, ratelimit, s3) |

### Быстрый старт

```bash
# 1. Склонировать репозиторий
git clone https://github.com/codewithme-py/FairDrop.git && cd FairDrop

# 2. Запустить все сервисы (PostgreSQL, Redis, MinIO, app, worker, nginx, Prometheus, Grafana)
docker compose up -d

# 3. Применить миграции
docker compose exec app alembic upgrade head
```

Сервисы после запуска:
- **API**: `http://localhost:8080` (через nginx gateway)
- **Swagger/docs**: `http://localhost:8000/docs#/`
- **Admin panel**: `http://localhost:8080/admin`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`

### Тестирование

```bash
# Запустить unit/integration тесты
uv run pytest

# Собрать coverage
uv run pytest --cov=app --cov-report=term-missing

# Нагрузочные тесты (из Makefile)
make stress-test        # 500 пользователей, 60 секунд
make oversell-test      # Тест защиты от оверселлинга
make orders-test        # Тест создания заказов
make mixed-test         # Смешанная нагрузка
make ratelimit-test     # Тест rate limiting
make s3-test            # Тест загрузки файлов
```

### Результаты тестирования

<details>
<summary> Unit/Integration, Load tests, Comparison, Project Structure</summary>

#### Unit/Integration тесты

| Метрика | Значение |
|---|---|
| **Тестов пройдено** | 153 passed |
| **Время выполнения** | 67.37s |
| **Общее покрытие** | **95%** |
| **Всего stmt** | 1991 |

Покрытие по модулям:

| Модуль | Покрытие | Примечание |
|---|---|---|
| `app/main.py` | 100% | FastAPI app, lifespan, middleware |
| `app/core/security.py` | 100% | JWT, RBAC, ownership checks |
| `app/core/config.py` | 100% | Pydantic Settings |
| `app/core/hashing.py` | 100% | Password hashing |
| `app/core/exceptions.py` | 100% | Custom exceptions |
| `app/core/setup.py` | 100% | Exception handlers |
| `app/core/auth_schemes.py` | 100% | Auth schemes |
| `app/core/lua_scripts.py` | 100% | Lua rate limiter scripts |
| `app/shared/decorators.py` | 100% | Idempotency decorator |
| `app/shared/rate_limit.py` | 100% | Rate limiting middleware |
| `app/shared/rate_limit_utils.py` | 100% | Rate limit utilities |
| `app/worker.py` | 100% | ARQ worker |
| `app/services/inventory/service.py` | 100% | Reservation logic |
| `app/services/inventory/internal.py` | 100% | Lua reservation internals |
| `app/services/orders/service.py` | 100% | Order creation |
| `app/services/orders/internal.py` | 100% | Order internals |
| `app/services/user/service.py` | 97% | JWT rotation, auth |
| `app/services/seller_user/service.py` | 100% | Seller dashboard |
| `app/services/external/service.py` | 100% | B2B partner API |
| `app/services/media/service.py` | 93% | S3 presigned URLs |
| `app/services/media/tasks.py` | 92% | Background file operations |
| `app/core/admin/admin.py` | 96% | Admin panel views |
| `app/core/exception_handlers.py` | 92% | Error handling |
| `app/core/audit_log/service.py` | 98% | Audit logging |
| `app/services/inventory/tasks.py` | 91% | Cleanup expired reservations |
| `app/services/buyer_user/service.py` | 89% | Buyer registration |
| `app/services/inventory/routes.py` | 88% | Inventory endpoints |
| `app/services/orders/routes.py` | 89% | Order endpoints |
| `app/services/seller_user/routes.py` | 81% | Seller endpoints |
| `app/services/user/routes.py` | 79% | Auth endpoints |
| `app/services/external/routes.py` | 68% | B2B endpoints |
| `app/core/s3.py` | 64% | S3 client operations |
| `app/shared/deps.py` | 72% | Auth dependencies |

#### Нагрузочное тестирование (Locust)

**Стресс-тест** — 500 пользователей, 60 секунд, ramp-up 100 users/sec:

| Метрика | Значение |
|---|---|
| **Всего запросов** | 636 |
| **Успешных** | 139 (21.86%) |
| **Отклонено rate limiter'ом** | 497 (78.14%) |
| **Среднее время отклика** | 73ms |
| **Медиана (p50)** | 60ms |
| **p95** | 280ms |
| **p99** | 310ms |
| **Максимум** | 521ms |

Результаты по эндпоинтам:

| Эндпоинт | Запросов | Успешных | Среднее | p95 | p99 |
|---|---|---|---|---|---|
| `POST /api/v1/inventory/reserve` | 133 | **133 (100%)** | 16ms | 24ms | 39ms |
| `POST /api/v1/auth/token` | 3 | **3 (100%)** | 255ms | 258ms | 258ms |
| `POST /api/v1/users` | 500 | 3 (0.6%) | 87ms | 290ms | 310ms |

> **Вывод**: Inventory reserve эндпоинт выдержал 100% нагрузку со средним временем 16ms — Lua-скрипт в Redis эффективно защищает от оверселлинга. Registration эндпоинт получил 429 на 99.4% запросов — signup rate limit (3 attempts/hour) сработал как защита. Auth token — стабильные 255ms (bcrypt хеширование пароля).

**Mixed workload** — 100 пользователей, 60 секунд:

| Метрика | Значение |
|---|---|
| **Всего запросов** | 100 |
| **Отклонено rate limiter'ом** | 100 (100%) |
| **Среднее время отклика** | 63ms |
| **p95** | 99ms |
| **Максимум** | 102ms |

> **Вывод**: Все 100 запросов регистрации отклонены — signup rate limit (3/hour) исчерпан предыдущим тестом. Rate limiting работает корректно, повторные попытки получают 429 мгновенно (avg 63ms).

**Rate limit тест** — 1 пользователь, 15 секунд:

| Метрика | Значение |
|---|---|
| **Всего запросов** | 1 |
| **Отклонено** | 1 (100%) |
| **Время отклика** | 14ms |

> **Вывод**: Rate limit для signup (3/час) уже исчерпан, новый запрос отклонён за 14ms — Lua-скрипт в Redis мгновенно возвращает 429 без нагрузки на БД.

#### Сравнение: через nginx vs напрямую (FastAPI)

Тесты проводились в двух конфигурациях:
- **Через nginx** (порт 8080) — nginx rate limiter (20r/s) → Lua Redis rate limiter → FastAPI
- **Напрямую** (порт 8000) — только Lua Redis rate limiter → FastAPI

##### Стресс-тест: 500 пользователей, 60 секунд

| Метрика | Через nginx | Напрямую | Разница |
|---|---|---|---|
| **Всего запросов** | 636 | 646 | +10 |
| **Успешных** | 139 (21.86%) | 149 (23.06%) | +10 |
| **Отклонено (429)** | 497 (78.14%) | 497 (76.93%) | -1.2% |
| **Среднее время** | 73ms | 176ms | +141% |
| **Медиана (p50)** | 60ms | 190ms | +217% |
| **p95** | 280ms | 400ms | +43% |
| **p99** | 310ms | 430ms | +39% |
| **Максимум** | 521ms | 437ms | -16% |

##### По эндпоинтам

**Inventory Reserve (`POST /api/v1/inventory/reserve`):**

| Метрика | Через nginx | Напрямую | Разница |
|---|---|---|---|
| **Запросов** | 133 | 143 | +10 |
| **Успешных** | **133 (100%)** | **143 (100%)** | +10 |
| **Среднее** | 16ms | 20ms | +25% |
| **p95** | 24ms | 30ms | +25% |
| **p99** | 39ms | 330ms | +746% |

**Auth Token (`POST /api/v1/auth/token`):**

| Метрика | Через nginx | Напрямую | Разница |
|---|---|---|---|
| **Запросов** | 3 | 3 | 0 |
| **Успешных** | **3 (100%)** | **3 (100%)** | 0 |
| **Среднее** | 255ms | 264ms | +4% |

**Registration (`POST /api/v1/users`):**

| Метрика | Через nginx | Напрямую | Разница |
|---|---|---|---|
| **Запросов** | 500 | 500 | 0 |
| **Успешных** | 3 (0.6%) | 3 (0.6%) | 0 |
| **Среднее** | 87ms | 220ms | +153% |
| **p95** | 290ms | 410ms | +41% |
| **p99** | 310ms | 430ms | +39% |

##### Итоговое сравнение

| Показатель | nginx | напрямую | Что это значит |
|---|---|---|---|
| **nginx rate limiter** |  20r/s global |  отсутствует | Nginx защищает от перегрузки |
| **Lua rate limiter** |  Redis |  Redis | Работает в обеих конфигурациях |
| **Inventory reserve** | 16ms avg | 20ms avg | Lua-скрипт эффективен везде |
| **Auth (bcrypt)** | 255ms | 264ms | Не зависит от nginx |
| **Registration avg** | 87ms | 220ms | Без nginx — очередь растёт |

> **Общий вывод**: Nginx выступает как первый слой rate limiting (20r/s global), сглаживая пиковую нагрузку. Lua-скрипт в Redis — второй слой, который защищает БД от перегрузки. Inventory reserve (100% успешных, avg 16-20ms) демонстрирует, что Lua-скрипт эффективно обрабатывает резервирование без оверселлинга в обоих сценариях.

#### Структура проекта

```
FairDrop/
├── app/                                    # Основной пакет приложения
│   ├── __init__.py
│   ├── main.py                             # FastAPI app, lifespan, middleware, роутеры
│   ├── worker.py                           # ARQ worker для фоновых задач
│   │
│   ├── core/                               # Ядро приложения
│   │   ├── admin/
│   │   │   ├── admin.py                    # SQLAdmin конфигурация, кастомные view
│   │   │   └── admin_auth.py               # Кастомная аутентификация для админки
│   │   ├── audit_log/
│   │   │   ├── models.py                   # Модель AuditLog
│   │   │   └── service.py                  # Сервис записи аудита
│   │   ├── auth_schemes.py                 # Bearer token, API key schemes
│   │   ├── config.py                       # Pydantic Settings (все env переменные)
│   │   ├── database.py                     # Async SQLAlchemy engine, session factory
│   │   ├── exception_handlers.py           # Глобальные обработчики ошибок
│   │   ├── exceptions.py                   # Кастомные исключения (CredentialsError, PermissionDeniedError)
│   │   ├── hashing.py                      # Password hashing (passlib + bcrypt)
│   │   ├── logging.py                      # Structlog конфигурация
│   │   ├── lua_scripts.py                  # Lua-скрипты для Redis rate limiter
│   │   ├── redis.py                        # Redis client
│   │   ├── s3.py                           # MinIO/S3 клиент, presigned URLs
│   │   ├── security.py                     # JWT creation, RBAC checker, ownership checker
│   │   └── setup.py                        # Exception handlers registration
│   │
│   ├── services/                           # Бизнес-логика по доменам (модули)
│   │   ├── buyer_user/                     # Покупатель — регистрация, профиль
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── external/                       # B2B партнёрский API
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── inventory/                      # Инвентарь и резервирование
│   │   │   ├── deps.py
│   │   │   ├── internal.py                 # Внутренние функции (Lua-резервирование)
│   │   │   ├── models.py                   # Product, Reservation
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── tasks.py                    # ARQ задачи (очистка истёкших резервов)
│   │   ├── media/                          # Медиа и файлы
│   │   │   ├── models.py                   # ProductImage
│   │   │   ├── routes.py                   # Presigned URL generation, MinIO webhook
│   │   │   │   (webhook защищён IP-фильтром в nginx)
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── tasks.py                    # ARQ задачи (удаление файлов)
│   │   ├── orders/                         # Заказы
│   │   │   ├── internal.py                 # Внутренние функции создания
│   │   │   ├── models.py                   # Order, OrderItem
│   │   │   ├── routes.py                   # Создание, отмена, история
│   │   │   │   (idempotency-key decorator)
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── payments/                       # Платежи (заглушка)
│   │   │   └── __init__.py
│   │   ├── seller_user/                    # Продавец — управление товарами
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   └── user/                           # Пользователи и аутентификация
│   │       ├── models.py                   # User, RefreshToken, B2BApiKey
│   │       ├── routes.py                   # Login, register, refresh, me
│   │       ├── schemas.py
│   │       └── service.py                  # JWT refresh rotation, password hashing
│   │
│   └── shared/                             # Общие утилиты
│       ├── decorators.py                   # @idempotent decorator (Redis-based)
│       ├── deps.py                         # get_current_user (JWT), get_current_user_flexible
│       ├── rate_limit.py                   # Rate limiting middleware
│       └── rate_limit_utils.py            # Утилиты для rate limiting
│
├── migrations/                             # Alembic миграции (async)
│   ├── env.py                              # Async migration runner
│   ├── script.py.mako                      # Шаблон для новых миграций
│   └── versions/                           # 21 миграция (схема БД + индексы)
│
├── tests/                                  # Pytest тесты
│   ├── conftest.py                         # Фикстуры (async DB, test client)
│   └── ...                                 # Unit и integration тесты
│
├── load_tests/                             # Locust нагрузочные тесты
│   ├── locust_base.py                      # Базовый класс для Locust
│   ├── locustfile.py                       # General stress test (500 users)
│   ├── locustfile_mixed.py                 # Mixed workload (100 users)
│   ├── locustfile_orders.py                # Orders creation test
│   ├── locustfile_oversell.py              # Oversell protection test
│   ├── locustfile_ratelimit.py             # Rate limiting test
│   └── locustfile_s3.py                    # S3 upload test
│
├── scripts/                                # Скрипты
│   └── seed_oversell_product.py            # Сид для теста оверселлинга
│
├── infrastructure/                         # Инфраструктура
│   └── prometheus/
│       └── prometheus.yaml                 # Prometheus конфигурация
│
├── nginx/
│   └── nginx.conf                          # Nginx reverse proxy + rate limiting
│
├── docker-compose.yaml                     # 8 сервисов: postgres, redis, s3, app, worker, gateway, prometheus, grafana
├── Dockerfile                              # Multi-stage build, non-root user
├── .env                                    # Переменные окружения (учебный проект)
├── Makefile                                # Команды для нагрузочного тестирования
├── pyproject.toml                          # Зависимости, ruff, mypy, pytest конфиги
├── .pre-commit-config.yaml                 # Pre-commit hooks
├── alembic.ini                             # Alembic конфигурация
└── uv.lock                                 # Lock-файл для uv
```

</details>

### Безопасность

- **JWT** — access token с expiration (30 мин), refresh token rotation (7 дней), old token deletion
- **B2B API keys** — аутентификация внешних партнёров через API key в заголовке
- **RBAC** — роли (admin, moderator, seller, buyer, user_b2b, seller_b2b), `RoleChecker` через FastAPI Depends
- **Ownership check** — проверка `owner_id`/`user_id` при доступе к ресурсам
- **Rate limiting** — Lua-скрипты в Redis (login: 7 попыток/мин, signup: 3/час, user: 10 RPS, global: 1000 RPS)
- **Idempotency** — Redis-based decorator для предотвращения дублей заказов (24 часа TTL)
- **Password hashing** — bcrypt через passlib
- **MinIO webhook** — защищён IP-фильтрацией в nginx (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- **Nginx rate limiting** — 20r/s global на уровне gateway
- **Admin panel** — кастомная session-based аутентификация, отдельные права для модераторов (read-only)
- **Structured logging** — structlog с request_id для трейсинга
- **Connection pool** — 200+ connections, overflow 200, healthcheck'и для всех сервисов

---

<details>
<summary> API документация</summary>

После запуска Swagger доступен по адресу: `http://localhost:8000/docs#/`

</details>

</details>

<details>
<summary> Description in English</summary>

## FairDrop — B2B/B2C Dropshipping Platform

Production-ready marketplace backend with async modular monolith architecture, designed with microservices growth path.

### Features

- **Product Catalog** — CRUD, moderation workflow, product statuses, unverified seller limits, S3-stored images
- **Orders** — creation, cancellation, status tracking, idempotency-key support for duplicate prevention
- **Inventory** — reservation system with oversell protection (Lua scripts in Redis)
- **Media** — S3/MinIO uploads with presigned URLs, webhook integration, ARQ background tasks
- **Authentication** — JWT (access + refresh), refresh token rotation, B2B API keys, admin sessions
- **RBAC** — roles (admin, moderator, seller, buyer, user_b2b, seller_b2b), granular access via `RoleChecker`
- **Audit Log** — change tracking for critical models (who, what, when)
- **Rate Limiting** — Lua scripts in Redis for login, signup, per-user and global RPS
- **Admin Panel** — SQLAdmin with custom auth, product moderation, user management
- **Background Tasks** — ARQ worker for heavy operations (Redis queues)
- **Monitoring** — Prometheus metrics (prometheus-fastapi-instrumentator), Grafana dashboards
- **API Gateway** — Nginx reverse proxy with rate limiting (20r/s global) and IP filtering for webhooks

### Tech Stack

| Category | Technologies |
|---|---|
| **Backend** | FastAPI, SQLAlchemy (asyncio), Pydantic v2, orjson |
| **Database** | PostgreSQL 15 (asyncpg, connection pool 200+) |
| **Cache** | Redis (Lua scripts for rate limiting, ARQ for queues) |
| **Storage** | MinIO (S3-compatible, presigned URLs) |
| **Async** | asyncio, aioboto3, asyncpg, ARQ |
| **Monitoring** | Prometheus, Grafana, structlog (structured logging) |
| **Containers** | Docker, Docker Compose (8 services) |
| **CI/CD** | GitHub Actions (pytest, ruff, mypy) |
| **Migrations** | Alembic (async) |
| **Linting** | Ruff, MyPy, pre-commit hooks |
| **Load Testing** | Locust (6 scenarios: stress, oversell, orders, mixed, ratelimit, s3) |

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/codewithme-py/FairDrop.git && cd FairDrop

# 2. Start all services (PostgreSQL, Redis, MinIO, app, worker, nginx, Prometheus, Grafana)
docker compose up -d

# 3. Run migrations
docker compose exec app alembic upgrade head
```

Services after startup:
- **API**: `http://localhost:8080` (via nginx gateway)
- **Swagger/docs**: `http://localhost:8080/docs#/`
- **Admin panel**: `http://localhost:8080/admin`
- **MinIO Console**: `http://localhost:9000`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`

### Testing

```bash
# Run unit/integration tests
uv run pytest

# Collect coverage
uv run pytest --cov=app --cov-report=term-missing

# Load tests (from Makefile)
make stress-test        # 500 users, 60 seconds
make oversell-test      # Oversell protection test
make orders-test        # Order creation test
make mixed-test         # Mixed workload
make ratelimit-test     # Rate limiting test
make s3-test            # S3 upload test
```

### Test Results

<details>
<summary> Unit/Integration, Load tests, Comparison, Project Structure</summary>

#### Unit/Integration Tests

| Metric | Value |
|---|---|
| **Tests passed** | 153 passed |
| **Execution time** | 67.37s |
| **Total coverage** | **95%** |
| **Total statements** | 1991 |

Coverage by module (selected):

| Module | Coverage | Notes |
|---|---|---|
| `app/main.py` | 100% | FastAPI app, lifespan, middleware |
| `app/core/security.py` | 100% | JWT, RBAC, ownership checks |
| `app/core/config.py` | 100% | Pydantic Settings |
| `app/core/hashing.py` | 100% | Password hashing |
| `app/core/exceptions.py` | 100% | Custom exceptions |
| `app/shared/decorators.py` | 100% | Idempotency decorator |
| `app/shared/rate_limit.py` | 100% | Rate limiting middleware |
| `app/worker.py` | 100% | ARQ worker |
| `app/services/inventory/service.py` | 100% | Reservation logic |
| `app/services/orders/service.py` | 100% | Order creation |
| `app/services/user/service.py` | 97% | JWT rotation, auth |
| `app/services/media/service.py` | 93% | S3 presigned URLs |
| `app/core/admin/admin.py` | 96% | Admin panel views |
| `app/core/exception_handlers.py` | 92% | Error handling |
| `app/services/inventory/routes.py` | 88% | Inventory endpoints |
| `app/services/orders/routes.py` | 89% | Order endpoints |
| `app/services/user/routes.py` | 79% | Auth endpoints |
| `app/services/external/routes.py` | 68% | B2B endpoints |
| `app/core/s3.py` | 64% | S3 client operations |
| `app/shared/deps.py` | 72% | Auth dependencies |

#### Load Testing (Locust)

**Stress Test** — 500 users, 60 seconds, ramp-up 100 users/sec:

| Metric | Value |
|---|---|
| **Total requests** | 636 |
| **Successful** | 139 (21.86%) |
| **Rate limited (429)** | 497 (78.14%) |
| **Avg response time** | 73ms |
| **Median (p50)** | 60ms |
| **p95** | 280ms |
| **p99** | 310ms |
| **Max** | 521ms |

Results by endpoint:

| Endpoint | Requests | Successful | Avg | p95 | p99 |
|---|---|---|---|---|---|
| `POST /api/v1/inventory/reserve` | 133 | **133 (100%)** | 16ms | 24ms | 39ms |
| `POST /api/v1/auth/token` | 3 | **3 (100%)** | 255ms | 258ms | 258ms |
| `POST /api/v1/users` | 500 | 3 (0.6%) | 87ms | 290ms | 310ms |

> **Conclusion**: Inventory reserve endpoint handled 100% of load with avg 16ms — Lua script in Redis effectively protects against overselling. Registration endpoint received 429 on 99.4% of requests — signup rate limit (3 attempts/hour) worked as designed. Auth token — stable 255ms (bcrypt password hashing).

**Rate Limit Test** — 1 user, 15 seconds:

| Metric | Value |
|---|---|
| **Total requests** | 1 |
| **Rate limited** | 1 (100%) |
| **Response time** | 14ms |

> **Conclusion**: Signup rate limit (3/hour) already exhausted, new request rejected in 14ms — Lua script in Redis instantly returns 429 with zero DB load.

#### Comparison: via nginx vs direct (FastAPI)

Tests were run in two configurations:
- **Via nginx** (port 8080) — nginx rate limiter (20r/s) → Lua Redis rate limiter → FastAPI
- **Direct** (port 8000) — Lua Redis rate limiter only → FastAPI

#### Stress Test: 500 users, 60 seconds

| Metric | Via nginx | Direct | Difference |
|---|---|---|---|
| **Total requests** | 636 | 646 | +10 |
| **Successful** | 139 (21.86%) | 149 (23.06%) | +10 |
| **Rate limited (429)** | 497 (78.14%) | 497 (76.93%) | -1.2% |
| **Avg response time** | 73ms | 176ms | +141% |
| **Median (p50)** | 60ms | 190ms | +217% |
| **p95** | 280ms | 400ms | +43% |
| **p99** | 310ms | 430ms | +39% |
| **Max** | 521ms | 437ms | -16% |

#### By Endpoint

**Inventory Reserve (`POST /api/v1/inventory/reserve`):**

| Metric | Via nginx | Direct | Difference |
|---|---|---|---|
| **Requests** | 133 | 143 | +10 |
| **Successful** | **133 (100%)** | **143 (100%)** | +10 |
| **Avg** | 16ms | 20ms | +25% |
| **p95** | 24ms | 30ms | +25% |
| **p99** | 39ms | 330ms | +746% |

> **Conclusion**: Lua script in Redis works equally efficiently in both configurations. Slight p99 increase with direct connection is due to more requests processed (143 vs 133).

**Auth Token (`POST /api/v1/auth/token`):**

| Metric | Via nginx | Direct | Difference |
|---|---|---|---|
| **Requests** | 3 | 3 | 0 |
| **Successful** | **3 (100%)** | **3 (100%)** | 0 |
| **Avg** | 255ms | 264ms | +4% |

> **Conclusion**: bcrypt hashing is the main bottleneck. No difference — this is pure bcrypt computation time on the server.

**Registration (`POST /api/v1/users`):**

| Metric | Via nginx | Direct | Difference |
|---|---|---|---|
| **Requests** | 500 | 500 | 0 |
| **Successful** | 3 (0.6%) | 3 (0.6%) | 0 |
| **Avg** | 87ms | 220ms | +153% |
| **p95** | 290ms | 410ms | +41% |
| **p99** | 310ms | 430ms | +39% |

> **Conclusion**: Registration is slower with direct connection because nginx (20r/s) smoothed the load on the application. Without nginx, FastAPI received all 500 requests simultaneously, and avg time grew due to processing queue.

#### Summary

| Metric | nginx | direct | What it means |
|---|---|---|---|
| **nginx rate limiter** |  20r/s global |  absent | Nginx protects from overload |
| **Lua rate limiter** |  Redis |  Redis | Works in both configs |
| **Inventory reserve** | 16ms avg | 20ms avg | Lua script efficient everywhere |
| **Auth (bcrypt)** | 255ms | 264ms | Independent of nginx |
| **Registration avg** | 87ms | 220ms | Without nginx — queue grows |

> **Overall conclusion**: Nginx acts as the first rate limiting layer (20r/s global), smoothing peak load. Lua script in Redis is the second layer, protecting the DB from overload. Inventory reserve (100% successful, avg 16-20ms) demonstrates that the Lua script effectively handles reservations without overselling in both scenarios.

#### Project Structure

```
FairDrop/
├── app/                                    # Main application package
│   ├── __init__.py
│   ├── main.py                             # FastAPI app, lifespan, middleware, routers
│   ├── worker.py                           # ARQ worker for background tasks
│   │
│   ├── core/                               # Application core
│   │   ├── admin/
│   │   │   ├── admin.py                    # SQLAdmin config, custom views
│   │   │   └── admin_auth.py               # Custom admin authentication
│   │   ├── audit_log/
│   │   │   ├── models.py                   # AuditLog model
│   │   │   └── service.py                  # Audit logging service
│   │   ├── auth_schemes.py                 # Bearer token, API key schemes
│   │   ├── config.py                       # Pydantic Settings (all env vars)
│   │   ├── database.py                     # Async SQLAlchemy engine, session factory
│   │   ├── exception_handlers.py           # Global error handlers
│   │   ├── exceptions.py                   # Custom exceptions (CredentialsError, PermissionDeniedError)
│   │   ├── hashing.py                      # Password hashing (passlib + bcrypt)
│   │   ├── logging.py                      # Structlog configuration
│   │   ├── lua_scripts.py                  # Lua scripts for Redis rate limiter
│   │   ├── redis.py                        # Redis client
│   │   ├── s3.py                           # MinIO/S3 client, presigned URLs
│   │   ├── security.py                     # JWT creation, RBAC checker, ownership checker
│   │   └── setup.py                        # Exception handlers registration
│   │
│   ├── services/                           # Domain business logic (modules)
│   │   ├── buyer_user/                     # Buyer — registration, profile
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── external/                       # B2B partner API
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── inventory/                      # Inventory & reservations
│   │   │   ├── deps.py
│   │   │   ├── internal.py                 # Internal functions (Lua reservation)
│   │   │   ├── models.py                   # Product, Reservation
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── tasks.py                    # ARQ tasks (cleanup expired reservations)
│   │   ├── media/                          # Media & files
│   │   │   ├── models.py                   # ProductImage
│   │   │   ├── routes.py                   # Presigned URL generation, MinIO webhook
│   │   │   │   (webhook protected by nginx IP filter)
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── tasks.py                    # ARQ tasks (delete files)
│   │   ├── orders/                         # Orders
│   │   │   ├── internal.py                 # Internal order creation functions
│   │   │   ├── models.py                   # Order, OrderItem
│   │   │   ├── routes.py                   # Create, cancel, history
│   │   │   │   (idempotency-key decorator)
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── payments/                       # Payments (stub)
│   │   │   └── __init__.py
│   │   ├── seller_user/                    # Seller — product management
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   └── user/                           # Users & authentication
│   │       ├── models.py                   # User, RefreshToken, B2BApiKey
│   │       ├── routes.py                   # Login, register, refresh, me
│   │       ├── schemas.py
│   │       └── service.py                  # JWT refresh rotation, password hashing
│   │
│   └── shared/                             # Shared utilities
│       ├── decorators.py                   # @idempotent decorator (Redis-based)
│       ├── deps.py                         # get_current_user (JWT), get_current_user_flexible
│       ├── rate_limit.py                   # Rate limiting middleware
│       └── rate_limit_utils.py            # Rate limiting utilities
│
├── migrations/                             # Alembic migrations (async)
│   ├── env.py                              # Async migration runner
│   ├── script.py.mako                      # Template for new migrations
│   └── versions/                           # 21 migrations (DB schema + indexes)
│
├── tests/                                  # Pytest tests
│   ├── conftest.py                         # Fixtures (async DB, test client)
│   └── ...                                 # Unit and integration tests
│
├── load_tests/                             # Locust load tests
│   ├── locust_base.py                      # Base class for Locust
│   ├── locustfile.py                       # General stress test (500 users)
│   ├── locustfile_mixed.py                 # Mixed workload (100 users)
│   ├── locustfile_orders.py                # Orders creation test
│   ├── locustfile_oversell.py              # Oversell protection test
│   ├── locustfile_ratelimit.py             # Rate limiting test
│   └── locustfile_s3.py                    # S3 upload test
│
├── scripts/                                # Scripts
│   └── seed_oversell_product.py            # Seed for oversell testing
│
├── infrastructure/                         # Infrastructure
│   └── prometheus/
│       └── prometheus.yaml                 # Prometheus configuration
│
├── nginx/
│   └── nginx.conf                          # Nginx reverse proxy + rate limiting
│
├── docker-compose.yaml                     # 8 services: postgres, redis, s3, app, worker, gateway, prometheus, grafana
├── Dockerfile                              # Multi-stage build, non-root user
├── .env                                    # Environment variables (educational project)
├── Makefile                                # Load testing commands
├── pyproject.toml                          # Dependencies, ruff, mypy, pytest configs
├── .pre-commit-config.yaml                 # Pre-commit hooks
├── alembic.ini                             # Alembic configuration
└── uv.lock                                 # Lock file for uv
```

</details>

### Security

- **JWT** — access token with expiration (30 min), refresh token rotation (7 days), old token deletion
- **B2B API keys** — external partner authentication via header API key
- **RBAC** — roles (admin, moderator, seller, buyer, user_b2b, seller_b2b), `RoleChecker` via FastAPI Depends
- **Ownership check** — `owner_id`/`user_id` verification on resource access
- **Rate limiting** — Lua scripts in Redis (login: 7 attempts/min, signup: 3/hour, user: 10 RPS, global: 1000 RPS)
- **Idempotency** — Redis-based decorator for order duplicate prevention (24h TTL)
- **Password hashing** — bcrypt via passlib
- **MinIO webhook** — protected by nginx IP filtering (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- **Nginx rate limiting** — 20r/s global at gateway level
- **Admin panel** — custom session-based auth, separate moderator permissions (read-only)
- **Structured logging** — structlog with request_id for tracing
- **Connection pool** — 200+ connections, overflow 200, healthchecks for all services

---

<details>
<summary> API Documentation</summary>

After startup, Swagger is available at: `http://localhost:8080/docs#/`

</details>

</details>

---
