"""Shared OpenAPI response definitions for Swagger UI."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, inline_serializer
from rest_framework import serializers

_ERROR_DETAIL = inline_serializer("ErrorDetail", {"detail": serializers.CharField()})


def detail_error(description: str, detail: str) -> OpenApiResponse:
    """Response with the body `{"detail": "..."}` (404, 409)."""
    return OpenApiResponse(
        response=_ERROR_DETAIL,
        description=description,
        examples=[OpenApiExample("Error", value={"detail": detail}, response_only=True)],
    )


def not_logged_in() -> OpenApiResponse:
    """403 response: session authentication returns 403, not 401, without a login."""
    return detail_error(
        "Not logged in, or CSRF token missing.",
        "Authentication credentials were not provided.",
    )


def not_admin() -> OpenApiResponse:
    """403 response for endpoints that only admin users can call."""
    return detail_error(
        "Not logged in, not an admin user, or CSRF token missing.",
        "You do not have permission to perform this action.",
    )


def validation_error(description: str, example: dict) -> OpenApiResponse:
    """400 response: a list of messages per field, or in `non_field_errors`."""
    return OpenApiResponse(
        response=OpenApiTypes.OBJECT,
        description=description,
        examples=[OpenApiExample("Invalid input", value=example, response_only=True)],
    )
