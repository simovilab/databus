"""API tests for WhichShapesView (`GET /api/which-shapes/`).

First step of the run-registration UI cascade: given a route, return the
distinct GeoShapes used by its stop sequence in the current feed.
"""

import pytest


@pytest.mark.django_db
def test_returns_shape_metadata_for_route(api_client, route, route_stop, geo_shape):
    """A route with one RouteStop returns its linked GeoShape's metadata."""
    response = api_client.get("/api/which-shapes/", {"route_id": route.route_id})

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "shape_id": geo_shape.shape_id,
            "shape_name": geo_shape.shape_name,
            "shape_desc": geo_shape.shape_desc,
            "shape_from": geo_shape.shape_from,
            "shape_to": geo_shape.shape_to,
        }
    ]


@pytest.mark.django_db
def test_returns_empty_list_for_unknown_route(api_client, current_feed):
    """An unresolvable route_id returns an empty list rather than erroring."""
    response = api_client.get("/api/which-shapes/", {"route_id": "ghost-route"})

    assert response.status_code == 200
    assert response.json() == []
