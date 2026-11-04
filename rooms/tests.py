from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from bookings.models import Booking
from rooms.models import Room

LIST_URL = "/api/rooms/"


def detail_url(room_id):
    return f"/api/rooms/{room_id}/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def room(db):
    return Room.objects.create(label="101", beds=2, room_view=Room.RoomView.SEA)


@pytest.mark.django_db
class TestRoomCrud:
    def test_create(self, client):
        response = client.post(LIST_URL, {"label": "201", "beds": 3, "room_view": "mountain"}, format="json")
        assert response.status_code == 201
        assert response.data["label"] == "201"
        assert Room.objects.filter(label="201", beds=3, room_view="mountain").exists()

    def test_list(self, client, room):
        response = client.get(LIST_URL)
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == room.id

    def test_retrieve(self, client, room):
        response = client.get(detail_url(room.id))
        assert response.status_code == 200
        assert response.data == {"id": room.id, "label": "101", "beds": 2, "room_view": "sea"}

    def test_retrieve_missing_returns_404(self, client, db):
        assert client.get(detail_url(9999)).status_code == 404

    def test_full_update(self, client, room):
        response = client.put(
            detail_url(room.id), {"label": "101A", "beds": 4, "room_view": "yard"}, format="json"
        )
        assert response.status_code == 200
        room.refresh_from_db()
        assert (room.label, room.beds, room.room_view) == ("101A", 4, "yard")

    def test_partial_update(self, client, room):
        response = client.patch(detail_url(room.id), {"beds": 5}, format="json")
        assert response.status_code == 200
        room.refresh_from_db()
        assert room.beds == 5
        assert room.label == "101"

    def test_delete(self, client, room):
        assert client.delete(detail_url(room.id)).status_code == 204
        assert not Room.objects.filter(id=room.id).exists()

    def test_delete_room_with_booking_returns_409(self, client, room):
        user = get_user_model().objects.create_user(
            username="guest", password="x", id_card="123", phone="09120000000", gender="male"
        )
        start = timezone.now() + timedelta(days=1)
        Booking.objects.create(user=user, room=room, check_in=start, check_out=start + timedelta(days=2))

        response = client.delete(detail_url(room.id))
        assert response.status_code == 409
        assert Room.objects.filter(id=room.id).exists()


@pytest.mark.django_db
class TestRoomValidation:
    @pytest.mark.parametrize("beds", [0, 6, -1])
    def test_beds_out_of_range(self, client, beds):
        response = client.post(LIST_URL, {"label": "X", "beds": beds, "room_view": "sea"}, format="json")
        assert response.status_code == 400
        assert "beds" in response.data

    def test_invalid_view(self, client):
        response = client.post(LIST_URL, {"label": "X", "beds": 2, "room_view": "lake"}, format="json")
        assert response.status_code == 400
        assert "room_view" in response.data

    def test_duplicate_label(self, client, room):
        response = client.post(LIST_URL, {"label": "101", "beds": 1, "room_view": "yard"}, format="json")
        assert response.status_code == 400
        assert "label" in response.data

    def test_missing_fields(self, client):
        response = client.post(LIST_URL, {}, format="json")
        assert response.status_code == 400
        assert set(response.data) == {"label", "beds", "room_view"}
