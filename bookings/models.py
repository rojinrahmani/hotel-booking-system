from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q


class TsTzRange(Func):
    """SQL `tstzrange(lower, upper, '[)')` built from two datetime columns."""

    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class BookingQuerySet(models.QuerySet):
    def overlapping(self, check_in, check_out):
        """Bookings whose [check_in, check_out) period overlaps the given one.

        Two half-open periods overlap when each starts before the other ends.
        Strict comparisons mean back-to-back stays (12:00 out, 12:00 in) do not overlap.
        """
        return self.filter(check_in__lt=check_out, check_out__gt=check_in)


class Booking(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    # PROTECT: a room with bookings cannot be deleted silently.
    room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    check_in = models.DateTimeField()
    check_out = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BookingQuerySet.as_manager()

    class Meta:
        ordering = ["check_in"]
        constraints = [
            models.CheckConstraint(
                condition=Q(check_out__gt=F("check_in")),
                name="booking_check_out_after_check_in",
            ),
            # A room can never have two overlapping bookings. The range is
            # half-open [check_in, check_out), so back-to-back stays are allowed.
            ExclusionConstraint(
                name="booking_no_overlap_per_room",
                expressions=[
                    ("room", RangeOperators.EQUAL),
                    (
                        TsTzRange("check_in", "check_out", models.Value("[)")),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def __str__(self) -> str:
        return f"Booking #{self.pk}: room {self.room_id} {self.check_in} -> {self.check_out}"
