# Request Flow — Inventory Reservation

Sequence diagram showing the complete inventory reservation flow including rate limiting, idempotency, and ARQ cleanup.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant N as Nginx Gateway
    participant A as FastAPI App
    participant R as Redis
    participant DB as Postgres

    Note over C,N: Rate Limiting Nginx layer
    C->>N: POST /api/v1/inventory/reserve
    N->>N: limit_req_zone 20r/s global
    alt Rate exceeded at Nginx
        N-->>C: 429 Too Many Requests
    else OK
        N->>A: Forward to app port 8000
    end

    Note over A,R: Rate Limiting Lua layer
    A->>R: Lua script per-user and global
    R-->>A: OK limit not reached

    Note over A,R: Idempotency check
    A->>R: GET idempotency key 24h TTL
    alt Key exists
        R-->>A: Return cached response
        A-->>C: 200 OK cached
    else
        A->>R: SET idempotency key
    end

    Note over A,DB: Reserve transaction
    A->>DB: BEGIN Transaction
    A->>DB: SELECT Product FOR UPDATE
    alt Stock Available
        A->>DB: INSERT Reservation status PENDING expires 15 min
        A->>DB: UPDATE Product qty_available minus qty_reserved
        A->>DB: COMMIT Transaction
        A->>R: Cache response
        A-->>C: 201 Created reserved 15 min
    else Out of Stock
        A->>DB: ROLLBACK
        A-->>C: 409 Conflict Sold Out
    end

    Note over A,DB: ARQ Worker cleanup expired reservations
    loop Cron every 60 seconds
        A->>DB: SELECT Reservation status PENDING expired
        alt Found expired
            A->>DB: FOR UPDATE Reservation plus Product
            A->>DB: Product.qty_available plus Reservation.qty_reserved
            A->>DB: Reservation.status equals EXPIRED
            opt order_id is set
                A->>DB: cancel_order_by_system
            end
            A->>DB: COMMIT
        end
    end
```

## Flow Steps

1. **Nginx rate limit** — global 20r/s filter at gateway level
2. **Lua rate limit** — per-user 10 RPS + global 1000 RPS in Redis
3. **Idempotency check** — Redis cache with 24h TTL prevents duplicate orders
4. **Reserve transaction** — `SELECT FOR UPDATE` locks product row, creates PENDING reservation for 15 min
5. **ARQ cleanup** — cron job runs every 60 seconds, releases expired reservations and returns stock
