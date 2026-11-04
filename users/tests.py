from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from bookings.models import Booking
from rooms.models import Room

User = get_user_model()

LIST_URL = "/api/users/"
PASSWORD = "correct-horse-battery"


def detail_url(user_id):
    return f"/api/users/{user_id}/"


def payload(**overrides):
    data = {
        "username": "guest",
        "password": PASSWORD,
        "email": "guest@example.com",
        "id_card": "1234567890",
        "phone": "+989120000000",
        "gender": "female",
    }
    data.update(overrides)
    return data


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def guest(db):
    return User.objects.create_user(
        username="existing",
        password=PASSWORD,
        id_card="1111111111",
        phone="09120000000",
        gender="male",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="boss",
        password=PASSWORD,
        email="boss@example.com",
        id_card="2222222222",
        phone="09130000000",
        gender="female",
    )


@pytest.mark.django_db
class TestUserCrud:
    def test_create_hashes_password_and_hides_it(self, client):
        response = client.post(LIST_URL, payload(), format="json")

        assert response.status_code == 201
        assert "password" not in response.data
        user = User.objects.get(pk=response.data["id"])
        assert user.check_password(PASSWORD)
        assert user.is_active

    def test_list(self, client, guest):
        response = client.get(LIST_URL)
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == guest.id
        assert "password" not in response.data["results"][0]

    def test_retrieve(self, client, guest):
        response = client.get(detail_url(guest.id))
        assert response.status_code == 200
        assert response.data["username"] == "existing"

    def test_retrieve_missing_returns_404(self, client):
        assert client.get(detail_url(9999)).status_code == 404

    def test_full_update_keeps_password_when_not_sent(self, client, guest):
        data = payload(username="renamed")
        del data["password"]

        response = client.put(detail_url(guest.id), data, format="json")

        assert response.status_code == 200
        guest.refresh_from_db()
        assert guest.username == "renamed"
        assert guest.check_password(PASSWORD)

    def test_partial_update(self, client, guest):
        response = client.patch(detail_url(guest.id), {"phone": "09121111111"}, format="json")
        assert response.status_code == 200
        guest.refresh_from_db()
        assert guest.phone == "09121111111"
        assert guest.username == "existing"

    def test_partial_update_changes_password(self, client, guest):
        new_password = "another-long-passphrase"
        response = client.patch(detail_url(guest.id), {"password": new_password}, format="json")
        assert response.status_code == 200
        guest.refresh_from_db()
        assert guest.check_password(new_password)

    def test_delete(self, client, guest):
        assert client.delete(detail_url(guest.id)).status_code == 204
        assert not User.objects.filter(id=guest.id).exists()

    def test_delete_user_with_booking_returns_409(self, client, guest):
        room = Room.objects.create(label="101", beds=2, room_view="sea")
        start = timezone.now() + timedelta(days=1)
        Booking.objects.create(user=guest, room=room, check_in=start, check_out=start + timedelta(days=2))

        response = client.delete(detail_url(guest.id))

        assert response.status_code == 409
        assert User.objects.filter(id=guest.id).exists()
        assert Booking.objects.count() == 1


@pytest.mark.django_db
class TestUserValidation:
    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"password": "short"}, "password"),
            ({"password": "12345678901"}, "password"),
            ({"phone": "abc"}, "phone"),
            ({"gender": "other"}, "gender"),
            ({"email": "not-an-email"}, "email"),
        ],
    )
    def test_invalid_fields_return_400(self, client, overrides, field):
        response = client.post(LIST_URL, payload(**overrides), format="json")
        assert response.status_code == 400
        assert field in response.data

    def test_missing_fields(self, client):
        response = client.post(LIST_URL, {}, format="json")
        assert response.status_code == 400
        assert set(response.data) == {"username", "password", "id_card", "phone", "gender"}

    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"username": "existing"}, "username"),
            ({"id_card": "1111111111"}, "id_card"),
            ({"phone": "09120000000"}, "phone"),
        ],
    )
    def test_duplicate_values_return_400(self, client, guest, overrides, field):
        response = client.post(LIST_URL, payload(**overrides), format="json")
        assert response.status_code == 400
        assert field in response.data

    def test_inactive_user_cannot_book(self, client, guest):
        client.patch(detail_url(guest.id), {"is_active": False}, format="json")
        start = timezone.now() + timedelta(days=1)

        response = client.post(
            "/api/bookings/",
            {
                "user_id": guest.id,
                "beds": 2,
                "room_view": "sea",
                "check_in": start.isoformat(),
                "check_out": (start + timedelta(days=1)).isoformat(),
            },
            format="json",
        )

        assert response.status_code == 400
        assert "user_id" in response.data


@pytest.mark.django_db
class TestStaffAccountsAreProtected:
    def test_staff_not_listed(self, client, admin_user):
        assert client.get(LIST_URL).data["count"] == 0

    def test_staff_cannot_be_retrieved(self, client, admin_user):
        assert client.get(detail_url(admin_user.id)).status_code == 404

    def test_staff_password_cannot_be_changed(self, client, admin_user):
        response = client.patch(detail_url(admin_user.id), {"password": "hacked-passphrase"}, format="json")
        assert response.status_code == 404
        admin_user.refresh_from_db()
        assert admin_user.check_password(PASSWORD)

    def test_staff_cannot_be_deleted(self, client, admin_user):
        assert client.delete(detail_url(admin_user.id)).status_code == 404
        assert User.objects.filter(id=admin_user.id).exists()

    @pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
    def test_api_cannot_grant_admin_access(self, client, guest, flag):
        created = client.post(LIST_URL, payload(**{flag: True}), format="json")
        patched = client.patch(detail_url(guest.id), {flag: True}, format="json")

        assert created.status_code == 201
        assert patched.status_code == 200
        guest.refresh_from_db()
        assert getattr(guest, flag) is False
        assert getattr(User.objects.get(pk=created.data["id"]), flag) is False
