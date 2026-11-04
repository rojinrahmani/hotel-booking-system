from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "user", "check_in", "check_out", "created_at")
    list_filter = ("room__room_view", "room__beds")
    search_fields = ("room__label", "user__username", "user__email")
    list_select_related = ("room", "user")
    date_hierarchy = "check_in"
