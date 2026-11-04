from rest_framework import serializers

from .models import Room


class RoomSerializer(serializers.ModelSerializer):
    """Validation comes from the model: unique `label`, `beds` 1-5, `room_view` choices."""

    class Meta:
        model = Room
        fields = ["id", "label", "beds", "room_view"]
        read_only_fields = ["id"]
