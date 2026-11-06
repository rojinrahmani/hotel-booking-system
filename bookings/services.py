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


def validate_period(check_in, check_out):
    if check_out <= check_in:
        raise InvalidBookingPeriod("Check-out must be after check-in.")
    if check_in < timezone.now():
        raise InvalidBookingPeriod("Check-in cannot be in the past.")


def find_available_rooms(*, beds, room_view, check_in, check_out):
    busy_room_ids = Booking.objects.overlapping(check_in, check_out).values("room_id")
    return Room.objects.filter(beds=beds, room_view=room_view).exclude(id__in=busy_room_ids).order_by("id")


def book_room(*, user, beds, room_view, check_in, check_out):

    validate_period(check_in, check_out)

    candidate_ids = list(
        find_available_rooms(
            beds=beds, room_view=room_view, check_in=check_in, check_out=check_out
        ).values_list("id", flat=True)
    )

    for room_id in candidate_ids:
        try:
            with transaction.atomic():
                room = Room.objects.select_for_update().get(pk=room_id)
                if room.bookings.overlapping(check_in, check_out).exists():
                    continue

                return Booking.objects.create(
                    user=user,
                    room=room,
                    check_in=check_in,
                    check_out=check_out,
                )
        except Room.DoesNotExist:
            continue
        except IntegrityError:
            continue

    raise NoRoomAvailable("No room matches the requested features for this period.")
