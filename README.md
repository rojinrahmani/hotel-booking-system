# Hotel Booking System

REST API for managing hotel rooms and booking them by requested features
(number of beds and view). Built with Django, Django REST Framework and PostgreSQL.

The system picks an available room that matches the request and guarantees that
a room never has overlapping bookings, also under concurrent requests.

Design decisions and assumptions are in [DECISIONS.md](DECISIONS.md).

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 13 or newer (the `btree_gist` extension must be available; it ships with PostgreSQL)

## Setup

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Create the environment file and fill in your values:

   ```bash
   cp .env.example .env
   ```

   | Variable | Description | Default |
   |---|---|---|
   | `DJANGO_SECRET_KEY` | Django secret key | required |
   | `DJANGO_DEBUG` | Debug mode | `False` |
   | `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
   | `DB_NAME` | Database name | required |
   | `DB_USER` | Database user | required |
   | `DB_PASSWORD` | Database password | required |
   | `DB_HOST` | Database host | `localhost` |
   | `DB_PORT` | Database port | `5432` |

   Keep `DJANGO_DEBUG=True` for local development. With `False`, `runserver` does
   not serve static files, so the admin and its styles do not display correctly.

3. Start PostgreSQL with one of these options.

   **Option A: Docker.** Set `DB_PORT=5433` in `.env`, then start the database:

   ```bash
   docker compose up -d db
   ```

   The other database values in `.env.example` already match `docker-compose.yml`.

   **Option B: local PostgreSQL.** Create the database user and database (values
   must match `.env`):

   ```bash
   sudo -u postgres psql
   ```

   ```sql
   CREATE USER hotel WITH PASSWORD 'your_password' CREATEDB;
   CREATE DATABASE hotel_booking OWNER hotel;
   ```

   `CREATEDB` is needed only to run the tests (pytest creates a test database).
   Superuser rights are not needed: `btree_gist` is a trusted extension, so the
   database owner can enable it.

4. Apply migrations (this also enables `btree_gist`):

   ```bash
   uv run python manage.py migrate
   ```

5. Create an admin user:

   ```bash
   uv run python manage.py createsuperuser
   ```

   This command also asks for `email`, `id_card`, `phone` and `gender` (`male` or
   `female`).

## Run

```bash
uv run python manage.py runserver
```

- API docs (Swagger UI): http://127.0.0.1:8000/api/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/
- Admin: http://127.0.0.1:8000/admin/

### Swagger UI

Swagger UI lists every API request with its fields and responses, and can send
requests with **Try it out**. The page needs internet access, because it loads
its assets from a CDN.

### Admin panel

Log in with the user from `createsuperuser` to manage rooms, bookings and users.
The database constraints also apply here, so the admin cannot save an overlapping
booking.

### Create a guest

A booking needs the `id` of an existing, active user. Create guests with
`POST /api/users/` (see [Users](#users)) or in the admin.

## Tests

PostgreSQL must be running, and the database user must be allowed to create
databases.

```bash
uv run pytest -q
```

Tests cover user and room CRUD and validation, staff account protection, room selection, overlap rules, input
validation, the database exclusion constraint, and a concurrency test where
several threads race for the last room.

## API

**Warning:** The API has no authentication. Any client can read and change guest
data, including ID card and phone numbers. Do not expose it publicly without
adding authentication.

Requests and responses use JSON.

List endpoints are paginated with 20 items per page. Use `?page=2` for the next
page:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{"id": 1, "label": "101", "beds": 2, "room_view": "sea"}]
}
```

Error responses:

| Status | Meaning | Example body |
|---|---|---|
| `400` | Invalid input | `{"beds": ["Ensure this value is less than or equal to 5."]}` |
| `404` | Object not found | `{"detail": "No Room matches the given query."}` |
| `409` | Request conflicts with current data | `{"detail": "Room has bookings and cannot be deleted."}` |

### Users

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/users/` | List guests (paginated, 20 per page) |
| `POST` | `/api/users/` | Create a guest |
| `GET` | `/api/users/{id}/` | Retrieve a guest |
| `PUT` | `/api/users/{id}/` | Replace a guest |
| `PATCH` | `/api/users/{id}/` | Partially update a guest |
| `DELETE` | `/api/users/{id}/` | Delete a guest (`409` if the guest has bookings) |

| Field | Description |
|---|---|
| `username` | Required, unique |
| `password` | Required on create, optional on update. Write-only, stored hashed, and checked by the Django password validators |
| `id_card` | Required, unique, up to 20 characters |
| `phone` | Required, unique, 10 to 15 digits with an optional leading `+` |
| `gender` | Required, `male` or `female` |
| `email`, `first_name`, `last_name` | Optional |
| `is_active` | Optional, default `true`. Inactive users cannot make new bookings |
| `id`, `date_joined` | Read-only |

```bash
curl -X POST http://127.0.0.1:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{
        "username": "guest1",
        "password": "correct-horse-battery",
        "id_card": "1234567890",
        "phone": "+989120000000",
        "gender": "female"
      }'
```

The API manages guests only. Staff accounts return `404` and do not appear in the
list, and the API cannot set `is_staff` or `is_superuser`. Manage staff accounts in
the admin.

To keep the booking history of a guest, set `is_active` to `false` instead of
deleting the guest.

### Rooms

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/rooms/` | List rooms (paginated, 20 per page) |
| `POST` | `/api/rooms/` | Create a room |
| `GET` | `/api/rooms/{id}/` | Retrieve a room |
| `PUT` | `/api/rooms/{id}/` | Replace a room |
| `PATCH` | `/api/rooms/{id}/` | Partially update a room |
| `DELETE` | `/api/rooms/{id}/` | Delete a room (`409` if it has bookings) |

Room fields: `label` (unique), `beds` (1-5), `room_view` (`sea`, `mountain`, `yard`).

```bash
curl -X POST http://127.0.0.1:8000/api/rooms/ \
  -H "Content-Type: application/json" \
  -d '{"label": "101", "beds": 2, "room_view": "sea"}'
```

### Bookings

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/bookings/` | Book an available room matching the requested features |
| `GET` | `/api/bookings/` | List bookings |
| `GET` | `/api/bookings/{id}/` | Retrieve a booking |

Request fields for `POST /api/bookings/`:

| Field | Description |
|---|---|
| `user_id` | `id` of an existing, active user |
| `beds` | Number of beds, 1-5. The room must have exactly this number |
| `room_view` | `sea`, `mountain` or `yard` |
| `check_in` | ISO 8601 datetime. Cannot be in the past |
| `check_out` | ISO 8601 datetime. Must be after `check_in` |

When several rooms match, the system books the room with the lowest `id`. A
booking includes `check_in` and excludes `check_out`, so a guest can check in at
the exact time the previous guest checks out.

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": 1,
        "beds": 2,
        "room_view": "sea",
        "check_in": "2026-12-10T14:00:00Z",
        "check_out": "2026-12-12T12:00:00Z"
      }'
```

Responses:

- `201 Created`: booking details with the assigned room.

  ```json
  {
    "id": 1,
    "user_id": 1,
    "room": {"id": 1, "label": "101", "beds": 2, "room_view": "sea"},
    "check_in": "2026-12-10T14:00:00Z",
    "check_out": "2026-12-12T12:00:00Z",
    "created_at": "2026-11-03T10:00:00Z"
  }
  ```

- `400 Bad Request`: invalid input (unknown user, `beds` out of range, unknown
  view, check-out not after check-in, check-in in the past).
- `409 Conflict`: no room with the requested features is free for that period.

## Project structure

```
config/      settings and root URLs
users/       custom user model (built-in user + id_card, phone, gender), user API
rooms/       Room model, serializer, CRUD viewset
bookings/    Booking model, allocation service, booking API
```

## Not implemented

Authentication and permissions, booking cancellation and updates, an availability
search, and room list filters are not implemented. [DECISIONS.md](DECISIONS.md)
explains how to add them.
