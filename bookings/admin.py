from django import forms
from django.contrib import admin

from .models import Booking


class BookingAdminForm(forms.ModelForm):
    """Give clear form errors for a bad period or an overlap.

    Each error is set on a field, so Django skips the model constraints that use
    this field. Without this, a reversed period reaches the exclusion constraint
    check, and PostgreSQL rejects the range with a server error (HTTP 500).
    """

    class Meta:
        model = Booking
        fields = ["user", "room", "check_in", "check_out"]

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get("room")
        check_in = cleaned_data.get("check_in")
        check_out = cleaned_data.get("check_out")

        if not (check_in and check_out):
            return cleaned_data

        if check_out <= check_in:
            self.add_error("check_out", "Check-out must be after check-in.")
        elif room and room.bookings.overlapping(check_in, check_out).exclude(pk=self.instance.pk).exists():
            self.add_error("room", "This room already has a booking that overlaps this period.")

        return cleaned_data


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    form = BookingAdminForm
    list_display = ("id", "room", "user", "check_in", "check_out", "created_at")
    list_filter = ("room__room_view", "room__beds")
    search_fields = ("room__label", "user__username", "user__email", "user__id_card")
    list_select_related = ("room", "user")
    date_hierarchy = "check_in"
    autocomplete_fields = ("user", "room")
    readonly_fields = ("created_at",)
