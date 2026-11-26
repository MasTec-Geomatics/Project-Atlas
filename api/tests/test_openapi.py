"""Tests for the OpenAPI schema's operation IDs."""

from collections import Counter

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.app import app, generate_operation_id

client = TestClient(app)


def operation_ids() -> list[str]:
    """Return every ``operationId`` in the API's OpenAPI schema."""
    schema = client.get("/openapi.json").json()
    return [
        operation["operationId"] for path in schema["paths"].values() for operation in path.values()
    ]


def test_operation_ids_are_tag_and_function_name() -> None:
    """Each operation ID is the route's first tag and its function name."""
    assert sorted(operation_ids()) == sorted(
        [
            "health-health_check",
            "reference-list_states",
            "reference-list_layers",
            "reference-list_loads",
            "reference-start_loads",
            "reference-list_sources",
            "reference-create_source",
            "reference-update_source",
            "reference-check_source",
            "reference-run_source_checks",
            "reference-list_source_checks",
        ]
    )


def test_operation_ids_are_unique() -> None:
    """No two operations share an operation ID."""
    duplicates = [name for name, count in Counter(operation_ids()).items() if count > 1]

    assert duplicates == []


def test_untagged_route_raises_error_naming_the_route() -> None:
    """A route in the schema without a tag fails with its method and path in the message."""
    untagged_app = FastAPI(generate_unique_id_function=generate_operation_id)

    with pytest.raises(ValueError, match=r"^Route GET /untagged has no tag"):

        @untagged_app.get("/untagged")
        def untagged() -> None:
            """Route with no tag."""


def test_route_left_out_of_schema_needs_no_tag() -> None:
    """A route left out of the schema uses its function name and needs no tag"""
    hidden_app = FastAPI(generate_unique_id_function=generate_operation_id)

    @hidden_app.get("/hidden", include_in_schema=False)
    def hidden() -> None:
        """Route left out of the schema."""

    route = hidden_app.routes[-1]

    assert isinstance(route, APIRoute)
    assert route.unique_id == "hidden"
