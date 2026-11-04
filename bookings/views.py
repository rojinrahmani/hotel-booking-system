from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from config.schema import detail_error, validation_error

from .models import Booking
from .serializers import BookingRequestSerializer, BookingSerializer
from .services import NoRoomAvailable, book_room


class BookingViewSet(viewsets.ViewSet):
    """Book a room by features; list and inspect bookings.

    create:   POST /api/bookings/
    list:     GET  /api/bookings/
    retrieve: GET  /api/bookings/{id}/
    """

    queryset = Booking.objects.select_related("room").order_by("check_in", "id")
    pagination_class = PageNumberPagination

    @extend_schema(
        tags=["bookings"],
        summary="Book a room",
        description=(
            "Book a free room with the requested beds and view for the given period. "
            "If several rooms match, the room with the lowest id is booked."
        ),
        request=BookingRequestSerializer,
        responses={
            201: BookingSerializer,
            400: validation_error(
                "Invalid input or period.",
                {"non_field_errors": ["Check-out must be after check-in."]},
            ),
            409: detail_error(
                "No matching room is free for this period.",
                "No room matches the requested features for this period.",
            ),
        },
        examples=[
            OpenApiExample(
                "Two beds, sea view",
                value={
                    "user_id": 1,
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
            booking = book_room(**request_serializer.validated_data)
        except NoRoomAvailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["bookings"],
        summary="List bookings",
        description="Return a paginated list of bookings, ordered by check-in.",
        responses=BookingSerializer(many=True),
    )
    def list(self, request):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(self.queryset.all(), request, view=self)
        return paginator.get_paginated_response(BookingSerializer(page, many=True).data)

    @extend_schema(
        tags=["bookings"],
        summary="Get a booking",
        description="Return one booking by id, with its assigned room.",
        responses={
            200: BookingSerializer,
            404: detail_error("Booking not found.", "No Booking matches the given query."),
        },
    )
    def retrieve(self, request, pk=None):
        booking = get_object_or_404(self.queryset, pk=pk)
        return Response(BookingSerializer(booking).data)
