import threading
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from bookings.models import Booking
from bookings.services import NoRoomAvailable, book_room
from rooms.models import Room

URL = "/api/bookings/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="guest", password="secret", id_card="1234567890", phone="09120000000", gender="female"
    )


@pytest.fixture
def start():
    # Fixed hour in the future keeps periods easy to reason about.
    return (timezone.now() + timedelta(days=7)).replace(hour=14, minute=0, second=0, microsecond=0)


def make_room(label, beds=2, room_view=Room.RoomView.SEA):
    return Room.objects.create(label=label, beds=beds, room_view=room_view)


def payload(user, start, days=2, beds=2, room_view="sea", **overrides):
    data = {
        "user_id": user.id,
        "beds": beds,
        "room_view": room_view,
        "check_in": start.isoformat(),
        "check_out": (start + timedelta(days=days)).isoformat(),
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestBookingApi:
    def test_books_matching_room(self, client, user, start):
        make_room("M1", beds=2, room_view="mountain")  # wrong view
        make_room("S3", beds=3, room_view="sea")  # wrong beds
        match = make_room("S2", beds=2, room_view="sea")

        response = client.post(URL, payload(user, start), format="json")

        assert response.status_code == 201
        assert response.data["room"]["id"] == match.id
        assert response.data["user_id"] == user.id
        assert Booking.objects.get(pk=response.data["id"]).room_id == match.id

    def test_picks_next_free_room_when_first_is_booked(self, client, user, start):
        first = make_room("A")
        second = make_room("B")

        r1 = client.post(URL, payload(user, start), format="json")
        r2 = client.post(URL, payload(user, start), format="json")

        assert r1.data["room"]["id"] == first.id
        assert r2.data["room"]["id"] == second.id

    def test_no_room_available_returns_409(self, client, user, start):
        make_room("A")
        assert client.post(URL, payload(user, start), format="json").status_code == 201

        # Overlaps the first booking by one day.
        response = client.post(URL, payload(user, start + timedelta(days=1)), format="json")

        assert response.status_code == 409
        assert Booking.objects.count() == 1

    def test_no_matching_room_returns_409(self, client, user, start):
        make_room("A", beds=1)
        assert client.post(URL, payload(user, start, beds=5), format="json").status_code == 409

    def test_back_to_back_bookings_share_room(self, client, user, start):
        room = make_room("A")
        r1 = client.post(URL, payload(user, start, days=2), format="json")
        # Check-in at exactly the previous check-out time.
        r2 = client.post(URL, payload(user, start + timedelta(days=2), days=1), format="json")

        assert r1.status_code == r2.status_code == 201
        assert r1.data["room"]["id"] == r2.data["room"]["id"] == room.id

    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"beds": 0}, "beds"),
            ({"beds": 6}, "beds"),
            ({"room_view": "lake"}, "room_view"),
            ({"user_id": 999999}, "user_id"),
        ],
    )
    def test_invalid_fields_return_400(self, client, user, start, overrides, field):
        response = client.post(URL, payload(user, start, **overrides), format="json")
        assert response.status_code == 400
        assert field in response.data

    def test_inactive_user_returns_400(self, client, user, start):
        user.is_active = False
        user.save()

        response = client.post(URL, payload(user, start), format="json")

        assert response.status_code == 400
        assert "user_id" in response.data

    def test_check_out_before_check_in_returns_400(self, client, user, start):
        data = payload(user, start, check_out=(start - timedelta(hours=1)).isoformat())
        assert client.post(URL, data, format="json").status_code == 400

    def test_check_in_in_past_returns_400(self, client, user):
        past = timezone.now() - timedelta(days=1)
        assert client.post(URL, payload(user, past), format="json").status_code == 400

    def test_list_and_retrieve(self, client, user, start):
        make_room("A")
        booking_id = client.post(URL, payload(user, start), format="json").data["id"]

        listed = client.get(URL)
        detail = client.get(f"{URL}{booking_id}/")

        assert listed.status_code == 200 and listed.data["count"] == 1
        assert detail.status_code == 200 and detail.data["id"] == booking_id


@pytest.mark.django_db
class TestDatabaseConstraint:
    def test_exclusion_constraint_blocks_overlap_outside_service(self, user, start):
        room = make_room("A")
        Booking.objects.create(user=user, room=room, check_in=start, check_out=start + timedelta(days=2))

        with pytest.raises(IntegrityError), transaction.atomic():
            Booking.objects.create(
                user=user, room=room, check_in=start + timedelta(days=1), check_out=start + timedelta(days=3)
            )


@pytest.mark.django_db
class TestBookingAdmin:
    ADD_URL = "/admin/bookings/booking/add/"

    @pytest.fixture
    def admin_client(self):
        staff = get_user_model().objects.create_superuser(username="boss", password="secret", id_card="999")
        django_client = Client()
        django_client.force_login(staff)
        return django_client

    @staticmethod
    def form(user, room, check_in, check_out):
        return {
            "user": user.id,
            "room": room.id,
            "check_in_0": check_in.strftime("%Y-%m-%d"),
            "check_in_1": check_in.strftime("%H:%M:%S"),
            "check_out_0": check_out.strftime("%Y-%m-%d"),
            "check_out_1": check_out.strftime("%H:%M:%S"),
        }

    def test_valid_booking_is_saved(self, admin_client, user, start):
        room = make_room("A")

        response = admin_client.post(self.ADD_URL, self.form(user, room, start, start + timedelta(days=2)))

        assert response.status_code == 302
        assert Booking.objects.filter(room=room, user=user).count() == 1

    def test_reversed_period_shows_form_error(self, admin_client, user, start):
        room = make_room("A")

        response = admin_client.post(self.ADD_URL, self.form(user, room, start, start - timedelta(days=2)))

        assert response.status_code == 200
        assert "Check-out must be after check-in." in response.content.decode()
        assert Booking.objects.count() == 0

    def test_overlap_shows_form_error(self, admin_client, user, start):
        room = make_room("A")
        Booking.objects.create(user=user, room=room, check_in=start, check_out=start + timedelta(days=2))

        response = admin_client.post(
            self.ADD_URL, self.form(user, room, start + timedelta(days=1), start + timedelta(days=3))
        )

        assert response.status_code == 200
        assert "overlaps this period" in response.content.decode()
        assert Booking.objects.count() == 1

    def test_editing_booking_does_not_overlap_itself(self, admin_client, user, start):
        room = make_room("A")
        booking = Booking.objects.create(
            user=user, room=room, check_in=start, check_out=start + timedelta(days=2)
        )
        new_check_out = start + timedelta(days=3)

        response = admin_client.post(
            f"/admin/bookings/booking/{booking.id}/change/", self.form(user, room, start, new_check_out)
        )

        assert response.status_code == 302
        booking.refresh_from_db()
        assert booking.check_out == new_check_out


def book_with_candidates(user, start, candidate_ids):
    """Call book_room() with a fixed candidate list, as if read before a race."""
    with patch("bookings.services.find_available_rooms") as find_rooms:
        find_rooms.return_value.values_list.return_value = candidate_ids
        check_out = start + timedelta(days=2)
        return book_room(user=user, beds=2, room_view="sea", check_in=start, check_out=check_out)


@pytest.mark.django_db
class TestBookRoomRaceBranches:
    """Each losing path in book_room(), forced without relying on thread timing."""

    def test_recheck_skips_room_booked_after_candidate_query(self, user, start):
        taken = make_room("A")
        free = make_room("B")
        Booking.objects.create(user=user, room=taken, check_in=start, check_out=start + timedelta(days=2))
        real_create = Booking.objects.create

        with patch("bookings.services.Booking.objects.create", side_effect=real_create) as create:
            booking = book_with_candidates(user, start, [taken.id, free.id])

        assert booking.room_id == free.id
        # The re-check rejects the room, so no insert reaches the constraint.
        assert create.call_count == 1

    def test_room_deleted_after_candidate_query_is_skipped(self, user, start):
        free = make_room("B")
        deleted_room_id = free.id + 1000

        booking = book_with_candidates(user, start, [deleted_room_id, free.id])

        assert booking.room_id == free.id

    def test_constraint_violation_tries_next_room(self, user, start):
        first = make_room("A")
        second = make_room("B")
        real_create = Booking.objects.create

        def create_conflict_on_first_room(**kwargs):
            if kwargs["room"].pk == first.pk:
                # A second identical insert gets a real error from the constraint.
                real_create(**kwargs)
            return real_create(**kwargs)

        with patch("bookings.services.Booking.objects.create", side_effect=create_conflict_on_first_room):
            booking = book_with_candidates(user, start, [first.id, second.id])

        assert booking.room_id == second.id
        # The atomic block rolled back both inserts on the first room.
        assert not Booking.objects.filter(room=first).exists()

    def test_constraint_violation_on_last_room_raises_no_room_available(self, user, start):
        room = make_room("A")
        real_create = Booking.objects.create

        def create_conflict(**kwargs):
            real_create(**kwargs)
            return real_create(**kwargs)

        with (
            patch("bookings.services.Booking.objects.create", side_effect=create_conflict),
            pytest.raises(NoRoomAvailable),
        ):
            book_with_candidates(user, start, [room.id])

        assert Booking.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_request_waits_for_room_lock_then_sees_committed_booking(user, start):
    """A request blocks on the room lock, then refuses the room after the holder commits."""
    room = make_room("Only")
    check_out = start + timedelta(days=2)
    results = []

    def attempt():
        try:
            book_room(user=user, beds=2, room_view="sea", check_in=start, check_out=check_out)
            results.append("ok")
        except NoRoomAvailable:
            results.append("full")
        finally:
            connection.close()  # each thread has its own DB connection

    thread = threading.Thread(target=attempt)
    with transaction.atomic():
        Room.objects.select_for_update().get(pk=room.pk)
        thread.start()
        thread.join(timeout=1)
        was_waiting = thread.is_alive()
        Booking.objects.create(user=user, room=room, check_in=start, check_out=check_out)
    thread.join()

    assert was_waiting
    assert results == ["full"]
    assert Booking.objects.count() == 1


def race_bookings(user, periods):
    """Call book_room() once per (check_in, check_out) period, all at the same time.

    Returns one result per period: "ok" or "full".
    """
    barrier = threading.Barrier(len(periods))
    results = []

    def attempt(check_in, check_out):
        try:
            barrier.wait()
            book_room(user=user, beds=2, room_view="sea", check_in=check_in, check_out=check_out)
            results.append("ok")
        except NoRoomAvailable:
            results.append("full")
        finally:
            connection.close()  # each thread has its own DB connection

    threads = [threading.Thread(target=attempt, args=period) for period in periods]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return results


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_never_double_book(user, start):
    """N threads race for one room: exactly one booking succeeds."""
    make_room("Only")

    results = race_bookings(user, [(start, start + timedelta(days=2))] * 8)

    assert results.count("ok") == 1
    assert results.count("full") == 7
    assert Booking.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_fall_through_to_next_free_room(user, start):
    """8 threads race for 3 rooms: each room is booked once, the rest are refused."""
    rooms = [make_room(label) for label in "ABC"]

    results = race_bookings(user, [(start, start + timedelta(days=2))] * 8)

    assert results.count("ok") == 3
    assert results.count("full") == 5
    booked_room_ids = sorted(Booking.objects.values_list("room_id", flat=True))
    assert booked_room_ids == [room.id for room in rooms]


@pytest.mark.django_db(transaction=True)
def test_concurrent_partly_overlapping_periods_never_double_book(user, start):
    """Different periods that all overlap each other still give one booking."""
    make_room("Only")
    periods = [(start + timedelta(hours=i), start + timedelta(days=2, hours=i)) for i in range(8)]

    results = race_bookings(user, periods)

    assert results.count("ok") == 1
    assert results.count("full") == 7
    assert Booking.objects.count() == 1
