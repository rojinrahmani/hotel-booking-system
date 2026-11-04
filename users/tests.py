import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_email_phone_and_gender_are_optional(self):
        user = User.objects.create_user(username="minimal", password="secret", id_card="1")

        assert user.email == ""
        assert user.phone is None
        assert user.gender == ""

    def test_several_users_can_have_no_phone(self):
        User.objects.create_user(username="first", password="secret", id_card="1")
        User.objects.create_user(username="second", password="secret", id_card="2")

        assert User.objects.filter(phone__isnull=True).count() == 2
