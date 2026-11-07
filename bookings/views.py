from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.schema import detail_error, not_logged_in, validation_error

from .models import Booking
from .serializers import BookingRequestSerializer, BookingSerializer
from .services import NoRoomAvailable, book_room

BOOKING_NOT_FOUND = detail_error(
    "Booking not found, or it belongs to another user.",
    "No Booking matches the given query.",
)


class BookingViewSet(viewsets.ViewSet):
    queryset = Booking.objects.select_related("room").order_by("check_in", "id")
    pagination_class = PageNumberPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(user=self.request.user)

    @extend_schema(
        tags=["bookings"],
        summary="Book a room",
        description=(
            "Book a free room for the logged-in user, with the requested beds and view "
            "for the given period. "
            "If several rooms match, the room with the lowest id is booked."
        ),
        request=BookingRequestSerializer,
        responses={
            201: BookingSerializer,
            400: validation_error(
                "Invalid input or period.",
                {"non_field_errors": ["Check-out must be after check-in."]},
            ),
            403: not_logged_in(),
            409: detail_error(
                "No matching room is free for this period.",
                "No room matches the requested features for this period.",
            ),
        },
        examples=[
            OpenApiExample(
                "Two beds, sea view",
                value={
                    "beds": 2,
                    "room_view": "sea",
                    "check_in": "2030-12-10T14:00:00Z",
                    "check_out": "2030-12-12T12:00:00Z",
                },
                request_only=True,
            ),
        ],
    )
    def create(self, request):
        request_serializer = BookingRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        try:
            booking = book_room(user=request.user, **request_serializer.validated_data)
        except NoRoomAvailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["bookings"],
        summary="List bookings",
        description=(
            "Return a paginated list of bookings, ordered by check-in. "
            "Users see their own bookings. Admin users see all bookings."
        ),
        responses={200: BookingSerializer(many=True), 403: not_logged_in()},
    )
    def list(self, request):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(self.get_queryset(), request)
        return paginator.get_paginated_response(BookingSerializer(page, many=True).data)

    @extend_schema(
        tags=["bookings"],
        summary="Get a booking",
        description=(
            "Return one booking by id, with its assigned room. "
            "Users can only get their own bookings. Admin users can get any booking."
        ),
        responses={
            200: BookingSerializer,
            403: not_logged_in(),
            404: BOOKING_NOT_FOUND,
        },
    )
    def retrieve(self, request, pk=None):
        booking = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(BookingSerializer(booking).data)

    @extend_schema(
        tags=["bookings"],
        summary="Delete a booking",
        description=(
            "Delete a booking. Its room becomes free for that period. "
            "Users can only delete their own bookings. Admin users can delete any booking."
        ),
        responses={
            204: OpenApiResponse(description="Booking deleted."),
            403: not_logged_in(),
            404: BOOKING_NOT_FOUND,
        },
    )
    def destroy(self, request, pk=None):
        booking = get_object_or_404(self.get_queryset(), pk=pk)
        booking.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
