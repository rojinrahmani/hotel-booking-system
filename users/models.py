from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r"^\+?\d{10,15}$",
    message="Phone number must contain 10 to 15 digits, optionally starting with '+'.",
)


class User(AbstractUser):
    """Django's built-in user plus hotel-specific fields.

    Inherited from AbstractUser: username, password (hashed), email,
    first_name, last_name, is_active, is_staff, is_superuser, date_joined,
    groups, permissions, and the default UserManager.
    """

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    id_card = models.CharField("ID card number", max_length=20, unique=True)
    phone = models.CharField(max_length=16, unique=True, validators=[phone_validator])
    gender = models.CharField(max_length=10, choices=Gender.choices)

    # Extra prompts for `createsuperuser` (username and password are always asked).
    REQUIRED_FIELDS = ["email", "id_card", "phone", "gender"]

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(gender__in=["male", "female"]),
                name="user_gender_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.username
