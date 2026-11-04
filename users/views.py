from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import User
from .serializers import UserCreateSerializer, UserSerializer

INVALID_INPUT = OpenApiResponse(description="Invalid input.")
USER_NOT_FOUND = OpenApiResponse(description="User not found.")


class UserViewSet(viewsets.ViewSet):
    """CRUD for guests.

    list:     GET    /api/users/
    create:   POST   /api/users/
    retrieve: GET    /api/users/{id}/
    update:   PUT    /api/users/{id}/
    partial:  PATCH  /api/users/{id}/
    destroy:  DELETE /api/users/{id}/
    """

    # The API has no authentication. Excluding staff keeps admin accounts out of
    # reach: otherwise any client could change an admin password.
    queryset = User.objects.filter(is_staff=False, is_superuser=False)
    pagination_class = PageNumberPagination

    @extend_schema(
        tags=["users"],
        summary="List users",
        description="Return a paginated list of guests. Staff accounts are not included.",
        responses=UserSerializer(many=True),
    )
    def list(self, request):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(self.queryset.all(), request, view=self)
        return paginator.get_paginated_response(UserSerializer(page, many=True).data)

    @extend_schema(
        tags=["users"],
        summary="Create a user",
        description="Create a guest. The password is stored hashed and is never returned.",
        request=UserCreateSerializer,
        responses={201: UserSerializer, 400: INVALID_INPUT},
    )
    def create(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["users"],
        summary="Get a user",
        description="Return one guest by id.",
        responses={200: UserSerializer, 404: USER_NOT_FOUND},
    )
    def retrieve(self, request, pk=None):
        user = get_object_or_404(self.queryset, pk=pk)
        return Response(UserSerializer(user).data)

    @extend_schema(
        tags=["users"],
        summary="Replace a user",
        description="Update all fields of a guest. Send `password` only to change it.",
        request=UserSerializer,
        responses={200: UserSerializer, 400: INVALID_INPUT, 404: USER_NOT_FOUND},
    )
    def update(self, request, pk=None):
        return self._save(request, pk, partial=False)

    @extend_schema(
        tags=["users"],
        summary="Update part of a user",
        description="Update only the given fields. Set `is_active` to false to block new bookings.",
        request=UserSerializer(partial=True),
        responses={200: UserSerializer, 400: INVALID_INPUT, 404: USER_NOT_FOUND},
    )
    def partial_update(self, request, pk=None):
        return self._save(request, pk, partial=True)

    @extend_schema(
        tags=["users"],
        summary="Delete a user",
        description="Delete a guest with no bookings. To keep the history, set `is_active` to false instead.",
        responses={
            204: OpenApiResponse(description="User deleted."),
            404: USER_NOT_FOUND,
            409: OpenApiResponse(description="User has bookings and cannot be deleted."),
        },
    )
    def destroy(self, request, pk=None):
        user = get_object_or_404(self.queryset, pk=pk)
        # Booking.user uses on_delete=CASCADE: keep booking history intact.
        if user.bookings.exists():
            return Response(
                {"detail": "User has bookings and cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _save(self, request, pk, partial):
        user = get_object_or_404(self.queryset, pk=pk)
        serializer = UserSerializer(user, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
