from rest_framework import serializers

from .models import Room


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "label", "beds", "room_view"]
        read_only_fields = ["id"]
