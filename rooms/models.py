from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Room(models.Model):
    MIN_BEDS = 1
    MAX_BEDS = 5

    class RoomView(models.TextChoices):
        SEA = "sea", "Sea"
        MOUNTAIN = "mountain", "Mountain"
        YARD = "yard", "Yard"

    label = models.CharField(max_length=50, unique=True)
    beds = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_BEDS), MaxValueValidator(MAX_BEDS)],
    )
    room_view = models.CharField(max_length=10, choices=RoomView.choices)

    class Meta:
        ordering = ["id"]
        constraints = [
            # Enforce domain rules at the DB level too, not only in validators.
            models.CheckConstraint(
                condition=models.Q(beds__gte=1) & models.Q(beds__lte=5),
                name="room_beds_between_1_and_5",
            ),
            models.CheckConstraint(
                condition=models.Q(room_view__in=["sea", "mountain", "yard"]),
                name="room_view_valid",
            ),
        ]
        indexes = [
            # Booking allocation filters rooms by (beds, room_view).
            models.Index(fields=["beds", "room_view"], name="room_beds_view_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.beds} beds, {self.get_room_view_display()} view)"
