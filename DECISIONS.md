# Technical Decisions and Assumptions

## Technical decisions

### PostgreSQL

The main correctness rule is "a room cannot have overlapping bookings".
PostgreSQL can enforce this in the database with an exclusion constraint,
which other common backends (SQLite, MySQL) cannot. This is why PostgreSQL is
required.

### Overlap prevention in two layers

1. **Service layer** (`bookings/services.py`). `book_room()`:
   - finds rooms with the requested `beds` and `room_view` and no overlapping
     booking, ordered by `id`;
   - for each candidate, opens a transaction and locks the room row with
     `SELECT ... FOR UPDATE`. A concurrent request for the same room waits;
   - checks overlap again after the lock (another request may have booked the
     room in the meantime), then creates the booking;
   - moves on to the next candidate if the room is taken, and raises
     `NoRoomAvailable` (HTTP `409`) if none is left.

2. **Database** (`bookings/models.py`). An exclusion constraint
   `booking_no_overlap_per_room` rejects any two rows with the same room and
   overlapping `tstzrange(check_in, check_out, '[)')`. It uses the `btree_gist`
   extension so one constraint can combine `room =` with range overlap `&&`.

The service gives clear errors and tries the next room. The constraint is the
final guarantee: it also covers writes that do not go through the service
(admin, shell, future code). If the constraint fires inside the service, the
service catches the `IntegrityError` and tries the next room.

Concurrency tests start 8 threads at the same time:

- `test_concurrent_requests_never_double_book`: all threads race for one room;
  exactly one booking is created.
- `test_concurrent_requests_fall_through_to_next_free_room`: threads race for 3
  rooms; each room is booked once and the other 5 requests are refused.
- `test_concurrent_partly_overlapping_periods_never_double_book`: threads race
  for one room with different periods that all overlap; exactly one booking is
  created.

These tests check the result, and the exclusion constraint alone could give the
same result. Separate tests check each mechanism:

- `test_request_waits_for_room_lock_then_sees_committed_booking`: a request
  blocks while another transaction holds the room lock.
- `TestBookRoomRaceBranches`: forces each losing path in `book_room()` without
  relying on thread timing (re-check, deleted room, constraint violation).

### Half-open periods

A booking covers `[check_in, check_out)`: check-in included, check-out
excluded. Two bookings overlap when
`existing.check_in < new.check_out AND existing.check_out > new.check_in`.
So a guest can check in at the exact time the previous guest checks out.

The service writes this check as `tstzrange(check_in, check_out, '[)') && <requested range>`
(`Booking.objects.overlapping()`), the same expression the exclusion constraint
uses. PostgreSQL can then answer the availability search from the constraint's
GiST index instead of scanning all bookings. With 100,000 bookings this changed
the plan from a sequential scan to a bitmap index scan on
`booking_no_overlap_per_room` (6.2 ms to 3.8 ms).

### Custom user model

`users.User` extends Django's `AbstractUser` and adds `id_card`, `phone` and
`gender`. Extending the built-in model keeps Django's authentication, password
hashing and admin, and avoids a separate profile table. It was set up before
the first migration, as Django requires.

### Business logic outside views

Allocation logic lives in `bookings/services.py`, not in views or serializers.
The view only validates input, calls `book_room()` and maps errors to HTTP
status codes. This keeps the logic easy to test and reuse.

### Plain `ViewSet`

Views extend `viewsets.ViewSet` and define each action explicitly, so each request
is visible in one place. `ModelViewSet` would need less code but would hide this
behaviour. Each action declares its schema with `extend_schema`, because a plain
`ViewSet` has no `serializer_class` for drf-spectacular to read.

### Validation at two levels

Room rules (`beds` 1-5, valid `room_view`, `check_out > check_in`) are checked
by model and serializer validators, and also by database check constraints.

The admin booking form checks the period and overlap itself. The model has no
`clean()`, and Django's constraint validation sends a reversed period to
PostgreSQL, which rejects the range with a server error. The form does not reject
a past check-in, so staff can record past stays.

### Configuration

Settings come from environment variables (`.env`, read by `django-environ`),
so no secrets are in the code.

## Assumptions

- **User identifier** is the primary key of an existing, active user. There is
  no user API; users are created in the admin or with `createsuperuser`.
- **Feature matching is exact**: a request for 2 beds gets a room with exactly
  2 beds, not more.
- **Room choice**: when several rooms match, the one with the lowest `id` is
  booked, so results are predictable.
- **No available room** returns `409 Conflict`.
- **Check-in in the past** is rejected. Check-out must be after check-in.
- **Datetimes** are stored in UTC. Inputs without a timezone are read as UTC.
- **Room deletion** is blocked (`409`) when the room has bookings, to keep
  booking history. Changing `beds` or `room_view` of a booked room is allowed;
  existing bookings keep their room.
- **No authentication or permissions** on the API, as the assignment does not
  ask for them. `DEFAULT_AUTHENTICATION_CLASSES` is empty, because DRF's default
  session authentication rejects POST requests from a browser that is logged in
  to the admin (CSRF error), which breaks Swagger's **Try it out**.
- **Gender** is optional, with two values, `male` and `female`. **Email** is
  optional. **Phone** is optional and unique when given; it is stored as `NULL`
  when not given, so several users can have no phone. **ID card** is a required,
  unique string up to 20 characters, with no country-specific format check.

## Not implemented / possible next steps

- **Authentication and permissions**: e.g. token or JWT auth; only staff manage
  rooms; a user books only for themselves (take the user from the request
  instead of `user_id`).
- **Booking cancellation and updates**: add a `status` field (`active`,
  `cancelled`) and limit the exclusion constraint to active bookings with a
  `condition`.
- **Availability search**: a read-only endpoint listing free rooms for a period,
  reusing `find_available_rooms()`.
- **Room list filters** by `beds` and `room_view`.
- **Docker**: the project has no Docker files. It runs with a local PostgreSQL.
