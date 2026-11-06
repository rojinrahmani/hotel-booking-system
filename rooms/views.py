from django.db.models import ProtectedError
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from config.schema import detail_error, validation_error

from .models import Room
from .serializers import RoomSerializer

INVALID_INPUT = validation_error(
    "Invalid input.",
    {"beds": ["Ensure this value is less than or equal to 5."]},
)
ROOM_NOT_FOUND = detail_error("Room not found.", "No Room matches the given query.")
ROOM_EXAMPLE = OpenApiExample(
    "Sea view room",
    value={"label": "101", "beds": 2, "room_view": "sea"},
    request_only=True,
)


class RoomViewSet(viewsets.ViewSet):
    queryset = Room.objects.all()
    pagination_class = PageNumberPagination

    @extend_schema(
        tags=["rooms"],
        summary="List rooms",
        description="Return a paginated list of all rooms.",
        responses=RoomSerializer(many=True),
    )
    def list(self, request):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(self.queryset.all(), request, view=self)
        return paginator.get_paginated_response(RoomSerializer(page, many=True).data)

    @extend_schema( 
        tags=["rooms"],
        summary="Create a room",
        description="Create a room with a unique label, 1-5 beds and a view.",
        request=RoomSerializer,
        responses={201: RoomSerializer, 400: INVALID_INPUT},
        examples=[ROOM_EXAMPLE],
    )
    def create(self, request):
        serializer = RoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["rooms"],
        summary="Get a room",
        description="Return one room by id.",
        responses={200: RoomSerializer, 404: ROOM_NOT_FOUND},
    )
    def retrieve(self, request, pk=None):
        room = get_object_or_404(self.queryset, pk=pk)
        return Response(RoomSerializer(room).data)

    @extend_schema(
        tags=["rooms"],
        summary="Replace a room",
        description="Update all fields of a room. Existing bookings keep this room.",
        request=RoomSerializer,
        responses={200: RoomSerializer, 400: INVALID_INPUT, 404: ROOM_NOT_FOUND},
        examples=[ROOM_EXAMPLE],
    )
    def update(self, request, pk=None):
        return self._save(request, pk, partial=False)

    @extend_schema(
        tags=["rooms"],
        summary="Update part of a room",
        description="Update only the given fields. Existing bookings keep this room.",
        request=RoomSerializer(partial=True),
        responses={200: RoomSerializer, 400: INVALID_INPUT, 404: ROOM_NOT_FOUND},
        examples=[OpenApiExample("Change beds", value={"beds": 3}, request_only=True)],
    )
    def partial_update(self, request, pk=None):
        return self._save(request, pk, partial=True)

    @extend_schema(
        tags=["rooms"],
        summary="Delete a room",
        description="Delete a room that has no bookings.",
        responses={
            204: OpenApiResponse(description="Room deleted."),
            404: ROOM_NOT_FOUND,
            409: detail_error(
                "Room has bookings and cannot be deleted.",
                "Room has bookings and cannot be deleted.",
            ),
        },
    )
    def destroy(self, request, pk=None):
        room = get_object_or_404(self.queryset, pk=pk)
        try:
            room.delete()
        except ProtectedError:
            return Response(
                {"detail": "Room has bookings and cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _save(self, request, pk, partial):
        room = get_object_or_404(self.queryset, pk=pk)
        serializer = RoomSerializer(room, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
