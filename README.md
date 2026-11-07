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

3. Create the PostgreSQL user and database (values must match `.env`):

   ```bash
   sudo -u postgres psql
   ```

   ```sql
   CREATE USER hotel WITH PASSWORD 'your_password';
   CREATE DATABASE hotel_booking OWNER hotel;
   ```

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

   This command also asks for `id_card`.

## Run

```bash
uv run python manage.py runserver
```

- API docs (Swagger UI): http://127.0.0.1:8000/api/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/
- Admin: http://127.0.0.1:8000/admin/

### Swagger UI

Swagger UI lists every API request, grouped into `rooms` and `bookings`, with its
fields and responses. Requests and error responses (`400`, `404`, `409`) include
example bodies. **Try it out** sends a real request as the logged-in user, so
[log in](#log-in) first and then reload the page. The page sends the CSRF token
for you. The page needs internet access, because it loads its assets from a CDN.

### Admin panel

Log in with the user from `createsuperuser` to manage rooms, bookings and users.

- **Rooms**: filter by beds and view, search by label.
- **Bookings**: filter by room view and beds, search by room label or by guest
  username, email or ID card, and browse by check-in date. The `user` and `room`
  fields search as you type.
- **Users**: the normal Django user pages plus `id_card`, `phone` and `gender`.
  Filter by gender, and search by username, email, ID card or phone.

The admin shows a form error for an overlapping booking or a check-out that is
not after check-in. A room that has bookings cannot be deleted. The admin does
not reject a check-in in the past, so staff can record past stays; the API does
reject it.

### Create a guest

A booking belongs to the logged-in user. There is no user management API (out of
scope), so create guests in the admin or in the shell:

```bash
uv run python manage.py shell -c '
from django.contrib.auth import get_user_model
get_user_model().objects.create_user(
    username="guest1",
    password="change-me",
    id_card="1234567890",
)
'
```

### Add dummy data

Add test users, rooms and bookings to the database:

```bash
uv run python manage.py seed
```

The command needs `DJANGO_DEBUG=True`, because its users have a known password. All
of them use the password `seed-pass-123`:

- `seed_admin`: admin user.
- `seed_guest1`, `seed_guest2`, `seed_guest3`: normal users with bookings.

You can run the command again. It only adds what is missing and does not change
existing data. Room labels start with `S-`. Room `S-302` is the only 5-bed room, so
booking 5 beds for its booked period returns `409`.

## Lint and format

```bash
uv run ruff check .
uv run ruff format .
```

The configuration is in `pyproject.toml`. Generated migrations are excluded.

## Log in

The API uses DRF session authentication. Bookings and reading rooms need a logged-in
user. Creating, updating and deleting rooms needs an admin user (`is_staff`). Without
the required access, the API returns `403`.

Log in at http://127.0.0.1:8000/api-auth/login/. Admin users can also log in at
`/admin/`. Unsafe requests (`POST`, `PUT`, `PATCH`, `DELETE`) also need a CSRF token.

With `curl`, keep the session in a cookie file and send the token in a header:

```bash
BASE=http://127.0.0.1:8000
curl -s -c cookies.txt "$BASE/api-auth/login/" -o /dev/null
TOKEN=$(awk '/csrftoken/ {print $7}' cookies.txt)
curl -s -b cookies.txt -c cookies.txt "$BASE/api-auth/login/" -o /dev/null \
  -d "username=guest1&password=change-me&csrfmiddlewaretoken=$TOKEN"
TOKEN=$(awk '/csrftoken/ {print $7}' cookies.txt)
```

## API

Requests and responses use JSON. See [Log in](#log-in) for authentication.

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
| `403` | Not logged in, not allowed, or CSRF token missing | `{"detail": "Authentication credentials were not provided."}` |
| `404` | Object not found | `{"detail": "No Room matches the given query."}` |
| `409` | Request conflicts with current data | `{"detail": "Room has bookings and cannot be deleted."}` |

### Rooms

`GET` needs a logged-in user. `POST`, `PUT`, `PATCH` and `DELETE` need an admin user.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/rooms/` | List rooms (paginated, 20 per page). `?label=` searches by label |
| `POST` | `/api/rooms/` | Create a room |
| `GET` | `/api/rooms/{id}/` | Retrieve a room |
| `PUT` | `/api/rooms/{id}/` | Replace a room |
| `PATCH` | `/api/rooms/{id}/` | Partially update a room |
| `DELETE` | `/api/rooms/{id}/` | Delete a room (`409` if it has bookings) |

Room fields: `label` (unique), `beds` (1-5), `room_view` (`sea`, `mountain`, `yard`).

```bash
curl -X POST http://127.0.0.1:8000/api/rooms/ -b cookies.txt \
  -H "X-CSRFToken: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"label": "101", "beds": 2, "room_view": "sea"}'
```

### Bookings

Logged-in users only. Users can list, retrieve and delete only their own bookings;
another user's booking returns `404`. Admin users can access all bookings.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/bookings/` | Book an available room matching the requested features |
| `GET` | `/api/bookings/` | List bookings |
| `GET` | `/api/bookings/{id}/` | Retrieve a booking |
| `DELETE` | `/api/bookings/{id}/` | Delete a booking and free its room for that period |

Request fields for `POST /api/bookings/`:

| Field | Description |
|---|---|
| `beds` | Number of beds, 1-5. The room must have exactly this number |
| `room_view` | `sea`, `mountain` or `yard` |
| `check_in` | ISO 8601 datetime. Cannot be in the past |
| `check_out` | ISO 8601 datetime. Must be after `check_in` |

The booking belongs to the logged-in user. The API ignores `user_id` in the
request. When several rooms match, the system books the room with the lowest `id`. A
booking includes `check_in` and excludes `check_out`, so a guest can check in at
the exact time the previous guest checks out.

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/ -b cookies.txt \
  -H "X-CSRFToken: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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

- `400 Bad Request`: invalid input (`beds` out of range, unknown
  view, check-out not after check-in, check-in in the past).
- `403 Forbidden`: not logged in, or CSRF token missing.
- `409 Conflict`: no room with the requested features is free for that period.

## Project structure

```
config/      settings, root URLs, shared Swagger responses
users/       custom user model (built-in user + id_card, phone, gender)
rooms/       Room model, serializer, CRUD viewset
bookings/    Booking model, allocation service, booking API, seed command
```

## Not implemented

Booking updates, cancellation history, an availability
search, and room list filters are not implemented. [DECISIONS.md](DECISIONS.md)
explains how to add them.
