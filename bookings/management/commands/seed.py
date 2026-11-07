"""Add dummy users, rooms and bookings for manual testing.

Run it again at any time: it only adds what is missing and never changes existing data.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from rooms.models import Room

PASSWORD = "seed-pass-123"

# username, id_card, phone, gender, is_admin
# passwrord: seed-pass-123
USERS = [
    ("seed_admin", "9000000001", "09000000001", "female", True),
    ("seed_guest1", "9000000002", "09000000002", "female", False),
    ("seed_guest2", "9000000003", "09000000003", "male", False),
    ("seed_guest3", "9000000004", None, "", False),
]

# label, beds, room_view
ROOMS = [
    ("S-101", 1, Room.RoomView.SEA),
    ("S-102", 2, Room.RoomView.SEA),
    ("S-103", 2, Room.RoomView.SEA),
    ("S-201", 2, Room.RoomView.MOUNTAIN),
    ("S-202", 3, Room.RoomView.MOUNTAIN),
    ("S-301", 4, Room.RoomView.YARD),
    ("S-302", 5, Room.RoomView.YARD),
]

# username, room label, days from today to check-in, nights
BOOKINGS = [
    ("seed_guest1", "S-102", -10, 2),  # past stay
    ("seed_guest1", "S-201", 7, 3),
    ("seed_guest2", "S-102", 7, 2),
    ("seed_guest2", "S-302", 14, 4),  # the only 5-bed room: same period returns 409
    ("seed_guest3", "S-101", 30, 1),
]


class Command(BaseCommand):
    help = "Add dummy users, rooms and bookings for manual testing. Needs DJANGO_DEBUG=True."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed creates users with a known password. It needs DJANGO_DEBUG=True.")

        with transaction.atomic():
            users = self._seed_users()
            rooms = self._seed_rooms()
            added_bookings = self._seed_bookings(users, rooms)

        self.stdout.write(self.style.SUCCESS(f"Added {added_bookings} bookings."))
        self.stdout.write(f"Log in as {', '.join(users)} with password: {PASSWORD}")

    def _seed_users(self):
        model = get_user_model()
        users = {}
        added = 0
        for username, id_card, phone, gender, is_admin in USERS:
            user = model.objects.filter(username=username).first()
            if user is None:
                user = model.objects.create_user(
                    username=username,
                    password=PASSWORD,
                    id_card=id_card,
                    phone=phone,
                    gender=gender,
                    is_staff=is_admin,
                    is_superuser=is_admin,
                )
                added += 1
            users[username] = user
        self.stdout.write(f"Added {added} users.")
        return users

    def _seed_rooms(self):
        rooms = {}
        added = 0
        for label, beds, room_view in ROOMS:
            rooms[label], created = Room.objects.get_or_create(
                label=label, defaults={"beds": beds, "room_view": room_view}
            )
            added += created
        self.stdout.write(f"Added {added} rooms.")
        return rooms

    def _seed_bookings(self, users, rooms):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        added = 0
        for username, label, days_from_today, nights in BOOKINGS:
            user, room = users[username], rooms[label]
            if Booking.objects.filter(user=user, room=room).exists():
                continue

            check_in = today + timedelta(days=days_from_today, hours=14)
            check_out = today + timedelta(days=days_from_today + nights, hours=12)
            if room.bookings.overlapping(check_in, check_out).exists():
                self.stdout.write(self.style.WARNING(f"Skipped {username} in {label}: period is taken."))
                continue

            Booking.objects.create(user=user, room=room, check_in=check_in, check_out=check_out)
            added += 1
        return added
