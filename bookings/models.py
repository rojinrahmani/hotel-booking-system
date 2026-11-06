from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q
from psycopg.types.range import Range as DateTimeTZRange

PERIOD_BOUNDS = "[)"


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class BookingQuerySet(models.QuerySet):
    def overlapping(self, check_in, check_out):
        return self.annotate(period=TsTzRange("check_in", "check_out", models.Value(PERIOD_BOUNDS))).filter(
            period__overlap=DateTimeTZRange(check_in, check_out, PERIOD_BOUNDS)
        )


class Booking(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
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
            ExclusionConstraint(
                name="booking_no_overlap_per_room",
                expressions=[
                    ("room", RangeOperators.EQUAL),
                    (
                        TsTzRange("check_in", "check_out", models.Value(PERIOD_BOUNDS)),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def __str__(self):
        return f"Booking #{self.pk}: room {self.room_id} {self.check_in} -> {self.check_out}"
