# flare-backend

REST API and real-time WebSocket server for **Flare** — a hyper-local, ephemeral chat platform.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | Django 5 + Django REST Framework |
| Real-time | Django Channels + Redis Pub/Sub |
| Database | PostgreSQL |
| Task Queue | Celery + Celery Beat |
| Cache | Redis |
| Auth | JWT (SimpleJWT) + Email OTP |
| Server | Uvicorn (dev) / Daphne (prod) |

---

## Features

- **Two-tier auth** — guests enter with a username only; email OTP grants a verified badge and room creation rights
- **Geo-based discovery** — rooms are filtered by GPS radius using Haversine distance queries
- **Ephemeral rooms** — destroyed automatically on timer expiry or after an empty-room grace period via Celery
- **Zero message persistence** — all chat messages live in Redis only and are wiped when a room closes
- **Waitlist queue** — rooms at capacity place users in a queue; the next person is admitted automatically when a slot opens
- **Flag & auto-kick** — any user can report a message; three flags in one room triggers an automatic removal
- **Real-time events** — WebSocket broadcasts for messages, user join/leave, kicks, and room closure

---

## API

### Auth — `/api/v1/auth/`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/guest/` | Enter as guest — returns JWT |
| POST | `/otp/request/` | Send OTP to email |
| POST | `/otp/verify/` | Verify OTP — returns verified JWT |
| GET | `/me/` | Current user details |

### Rooms — `/api/v1/rooms/`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Discover rooms by GPS radius |
| POST | `/create/` | Create a room (verified only) |
| GET | `/<id>/` | Room details |
| DELETE | `/<id>/` | Close room (creator only) |
| POST | `/<id>/join/` | Join a room or enter waitlist |
| POST | `/<id>/leave/` | Leave a room |

### Moderation — `/api/v1/moderation/`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/flag/` | Report a message |

### WebSocket

```
ws://host/ws/rooms/<room_id>/?token=<jwt>
```

**Client → Server**
```json
{ "type": "message", "text": "hello" }
{ "type": "kick", "session_id": "<id>" }
```

**Server → Client**
```json
{ "type": "message", "username": "...", "role": "guest|verified", "text": "...", "timestamp": "..." }
{ "type": "user_joined", "username": "...", "role": "..." }
{ "type": "user_left", "username": "..." }
{ "type": "user_kicked", "session_id": "...", "kicked_by": "..." }
{ "type": "room_closed", "reason": "timer_expired|empty_room|creator_closed" }
```

---

## Getting Started

**Requirements:** Python 3.12, Docker Desktop

```bash
git clone https://github.com/karunakar78/flare-backend.git
cd flare-backend
python -m venv venv && source venv/bin/activate
pip install -r requirements/development.txt
cp .env.example .env        # fill in SECRET_KEY
docker compose up -d        # starts PostgreSQL + Redis
python manage.py migrate
python manage.py createsuperuser
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
```

Celery (separate terminals):
```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for development |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL config |
| `REDIS_URL` | Redis connection URL |
| `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP config (production) |

---

## Design Decisions

- **Messages never touch PostgreSQL.** All chat is stored in Redis with a 100-message rolling window per room. On room destruction, the cache key is deleted — no recovery by design.
- **GPS coordinates are never stored.** Location data is used in-flight for radius filtering and discarded immediately.
- **Room lifecycle is creator-independent.** Once created, a room runs on its own timer regardless of the creator's presence.

---

## Related

[flare-frontend](https://github.com/karunakar78/flare-frontend) — React Native mobile app
