"""Booking business logic.

Overlap is prevented in two layers:
1. Service layer (this module): lock the candidate room row, re-check overlap,
   then insert. This gives a clear error path and serialises concurrent
   requests for the same room.
2. Database: the `booking_no_overlap_per_room` exclusion constraint. It is the
   final guarantee, also covering writes that bypass this service.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from rooms.models import Room

from .models import Booking


class BookingError(Exception):
    """Base class for booking failures."""


class InvalidBookingPeriod(BookingError):
    pass


class NoRoomAvailable(BookingError):
    pass


def validate_period(check_in, check_out) -> None:
    if check_out <= check_in:
        raise InvalidBookingPeriod("Check-out must be after check-in.")
    if check_in < timezone.now():
        raise InvalidBookingPeriod("Check-in cannot be in the past.")


def find_available_rooms(*, beds, room_view, check_in, check_out):
    """Rooms matching the requested features with no overlapping booking."""
    busy_room_ids = Booking.objects.overlapping(check_in, check_out).values("room_id")
    return Room.objects.filter(beds=beds, room_view=room_view).exclude(id__in=busy_room_ids).order_by("id")


def book_room(*, user, beds, room_view, check_in, check_out) -> Booking:
    """Assign the first available matching room to `user` and create the booking.

    Raises InvalidBookingPeriod or NoRoomAvailable.
    """
    validate_period(check_in, check_out)

    candidate_ids = list(
        find_available_rooms(
            beds=beds, room_view=room_view, check_in=check_in, check_out=check_out
        ).values_list("id", flat=True)
    )

    for room_id in candidate_ids:
        try:
            with transaction.atomic():
                # Row lock: a concurrent request for this room waits here until
                # we commit or roll back.
                room = Room.objects.select_for_update().get(pk=room_id)

                # Re-check after taking the lock: another request may have
                # booked this room between the candidate query and the lock.
                if room.bookings.overlapping(check_in, check_out).exists():
                    continue

                return Booking.objects.create(
                    user=user,
                    room=room,
                    check_in=check_in,
                    check_out=check_out,
                )
        except Room.DoesNotExist:
            # Room deleted after the candidate query.
            continue
        except IntegrityError:
            # Exclusion constraint fired (write outside this service won the
            # race). The atomic block rolled back; try the next room.
            continue

    raise NoRoomAvailable("No room matches the requested features for this period.")
