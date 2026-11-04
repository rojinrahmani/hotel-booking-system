import threading
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
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


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_never_double_book(user, start):
    """N threads race for one room: exactly one booking succeeds."""
    make_room("Only")
    threads_count = 8
    barrier = threading.Barrier(threads_count)
    results = []

    def attempt():
        try:
            barrier.wait()
            book_room(user=user, beds=2, room_view="sea", check_in=start, check_out=start + timedelta(days=2))
            results.append("ok")
        except NoRoomAvailable:
            results.append("full")
        finally:
            connection.close()  # each thread has its own DB connection

    threads = [threading.Thread(target=attempt) for _ in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 1
    assert results.count("full") == threads_count - 1
    assert Booking.objects.count() == 1
