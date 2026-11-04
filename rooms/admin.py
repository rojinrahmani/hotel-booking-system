from django.contrib import admin

from .models import Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "beds", "room_view")
    list_filter = ("beds", "room_view")
    search_fields = ("label",)
