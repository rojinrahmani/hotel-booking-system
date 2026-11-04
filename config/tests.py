import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def schema(db):
    response = Client().get("/api/schema/?format=json")
    assert response.status_code == 200
    return json.loads(response.content)


def test_swagger_page_loads(db):
    assert Client().get("/api/docs/").status_code == 200


def test_schema_lists_only_api_endpoints(schema):
    assert sorted(schema["paths"]) == [
        "/api/bookings/",
        "/api/bookings/{id}/",
        "/api/rooms/",
        "/api/rooms/{id}/",
    ]


def test_schema_declares_no_authentication(schema):
    assert "securitySchemes" not in schema["components"]


@pytest.mark.parametrize(
    "path, method, status",
    [
        ("/api/bookings/", "post", "400"),
        ("/api/bookings/", "post", "409"),
        ("/api/bookings/{id}/", "get", "404"),
        ("/api/rooms/", "post", "400"),
        ("/api/rooms/{id}/", "get", "404"),
        ("/api/rooms/{id}/", "delete", "409"),
    ],
)
def test_error_responses_have_example_body(schema, path, method, status):
    content = schema["paths"][path][method]["responses"][status]["content"]["application/json"]
    assert content["examples"]


def test_booking_request_has_example(schema):
    request_body = schema["paths"]["/api/bookings/"]["post"]["requestBody"]
    assert request_body["content"]["application/json"]["examples"]


def test_post_works_while_logged_in_to_admin(db):
    """Swagger shares cookies with the admin; the API must not require a CSRF token."""
    staff = get_user_model().objects.create_superuser(username="boss", password="secret", id_card="999")
    client = Client(enforce_csrf_checks=True)
    client.force_login(staff)

    response = client.post(
        "/api/rooms/",
        {"label": "101", "beds": 2, "room_view": "sea"},
        content_type="application/json",
    )

    assert response.status_code == 201
