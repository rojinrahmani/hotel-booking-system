from django.contrib.auth import get_user_model
from rest_framework import serializers

from rooms.models import Room
from rooms.serializers import RoomSerializer

from .models import Booking
from .services import InvalidBookingPeriod, validate_period


class BookingRequestSerializer(serializers.Serializer):
    """Input for POST /api/bookings/: who books, which room features, which period."""

    user_id = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(is_active=True),
        source="user",
        help_text="Id of an existing, active user.",
    )
    beds = serializers.IntegerField(
        min_value=Room.MIN_BEDS,
        max_value=Room.MAX_BEDS,
        help_text="The room must have exactly this number of beds.",
    )
    room_view = serializers.ChoiceField(choices=Room.RoomView.choices)
    check_in = serializers.DateTimeField(help_text="Included in the booking. Cannot be in the past.")
    check_out = serializers.DateTimeField(help_text="Excluded from the booking. Must be after check-in.")

    def validate(self, attrs):
        try:
            validate_period(attrs["check_in"], attrs["check_out"])
        except InvalidBookingPeriod as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs


class BookingSerializer(serializers.ModelSerializer):
    """Output: booking details with the assigned room."""

    user_id = serializers.IntegerField(read_only=True)
    room = RoomSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "user_id", "room", "check_in", "check_out", "created_at"]
        read_only_fields = fields
