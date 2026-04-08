# System Architecture

FairDrop uses a modular monolith architecture with nginx gateway, async FastAPI services, PostgreSQL, Redis, MinIO, and ARQ workers.

```mermaid
flowchart TB
    User["Client B2B"]
    Attacker["Botnet"]
    NginxHost["Nginx 20rps"]
    NginxDocker["Nginx proxy"]
    UserAPI["user module"]
    BuyerAPI["buyer_user module"]
    SellerAPI["seller_user module"]
    ExternalAPI["external module"]
    InvAPI["inventory module"]
    OrderAPI["orders module"]
    MediaAPI["media module"]
    Worker["ARQ worker"]
    Postgres[("PostgreSQL 15")]
    Redis[("Redis")]
    MinIO[("MinIO S3")]
    Prometheus["Prometheus"]
    Grafana["Grafana"]

    User --> NginxHost
    Attacker --> NginxHost
    NginxHost --> NginxDocker
    NginxDocker --> UserAPI
    NginxDocker --> BuyerAPI
    NginxDocker --> SellerAPI
    NginxDocker --> ExternalAPI
    NginxDocker --> InvAPI
    NginxDocker --> OrderAPI
    NginxDocker --> MediaAPI

    UserAPI --> Redis
    BuyerAPI --> Redis
    SellerAPI --> Redis
    ExternalAPI --> Redis
    InvAPI --> Redis
    OrderAPI --> Redis
    MediaAPI --> Redis

    UserAPI --> Postgres
    BuyerAPI --> Postgres
    SellerAPI --> Postgres
    ExternalAPI --> Postgres
    InvAPI --> Postgres
    OrderAPI --> Postgres
    MediaAPI --> Postgres

    Worker --> Redis
    Worker --> Postgres

    MediaAPI -.-> User
    User -.-> MinIO
    MinIO -.-> MediaAPI
    Worker -.-> Postgres
    Worker -.-> MinIO
    UserAPI -.-> Prometheus
    InvAPI -.-> Prometheus
    OrderAPI -.-> Prometheus
    MediaAPI -.-> Prometheus
    Prometheus --> Grafana
```

## Components

| Layer | Component | Description |
|---|---|---|
| **Perimeter** | Nginx Gateway | Rate limiting 20r/s, IP whitelist for webhooks |
| **App** | FastAPI | 8 modules: user, buyer_user, seller_user, external, inventory, orders, media, payments |
| **Background** | ARQ Worker | Cron cleanup expired reservations, image sanitization |
| **Storage** | PostgreSQL 15 | Async SQLAlchemy, pool 200+ |
| **Cache** | Redis | Lua rate limiting, ARQ queues, idempotency keys |
| **Storage** | MinIO S3 | Object storage for media |
| **Monitoring** | Prometheus + Grafana | Metrics via prometheus-fastapi-instrumentator |
