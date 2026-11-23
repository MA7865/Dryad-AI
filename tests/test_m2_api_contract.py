
"""
M2 vegetation FastAPI contract tests.

Checks:
- Registered endpoint
- OpenAPI response schema
- Full and filtered GeoJSON responses
- Invalid request handling
- Nullable anomaly detection
"""

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)

ENDPOINT = "/api/v1/layers/vegetation"


def test_endpoint_registered_in_openapi():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    specification = response.json()

    assert ENDPOINT in specification["paths"]

    get_operation = specification["paths"][
        ENDPOINT
    ]["get"]

    assert "200" in get_operation["responses"]

    response_schema = get_operation[
        "responses"
    ]["200"]["content"][
        "application/json"
    ]["schema"]

    assert (
        response_schema["$ref"]
        == "#/components/schemas/"
        "VegetationFeatureCollection"
    )


def test_full_layer_http_response():
    response = client.get(ENDPOINT)

    assert response.status_code == 200

    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2061

    for feature in data["features"]:
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Polygon"

        properties = feature["properties"]

        assert "patch_id" in properties
        assert "vegetation_class" in properties
        assert "anomaly_detected" in properties
        assert "detection_status" in properties


def test_multiple_patch_filter():
    response = client.get(
        ENDPOINT,
        params=[
            ("patch_id", "P_r000_c023"),
            ("patch_id", "P_r000_c024"),
        ],
    )

    assert response.status_code == 200

    returned_ids = {
        feature["properties"]["patch_id"]
        for feature in response.json()["features"]
    }

    assert returned_ids == {
        "P_r000_c023",
        "P_r000_c024",
    }


def test_unsupported_year_returns_400():
    response = client.get(
        ENDPOINT,
        params={"as_of": "2024"},
    )

    assert response.status_code == 400


def test_unknown_patch_returns_400():
    response = client.get(
        ENDPOINT,
        params={"patch_id": "INVALID_PATCH"},
    )

    assert response.status_code == 400


def test_detection_counts_and_nullability():
    response = client.get(ENDPOINT)

    assert response.status_code == 200

    properties = [
        feature["properties"]
        for feature in response.json()["features"]
    ]

    flagged = sum(
        p["anomaly_detected"] is True
        for p in properties
    )

    not_flagged = sum(
        p["anomaly_detected"] is False
        for p in properties
    )

    not_evaluated = sum(
        p["anomaly_detected"] is None
        for p in properties
    )

    assert flagged == 93
    assert not_flagged == 631
    assert not_evaluated == 1337

    for p in properties:
        if p["detection_status"] == "not_evaluated":
            assert p["anomaly_detected"] is None

        elif p["detection_status"] == "not_flagged":
            assert p["anomaly_detected"] is False

        elif p["detection_status"] == "negative_change_flagged":
            assert p["anomaly_detected"] is True


def test_missing_vegetation_class_preserved():
    response = client.get(ENDPOINT)

    assert response.status_code == 200

    properties = [
        feature["properties"]
        for feature in response.json()["features"]
    ]

    missing_classes = [
        p for p in properties
        if p["vegetation_class"] is None
    ]

    assert len(missing_classes) == 5

    # Missing LANDFIRE classification does not
    # imply missing Sentinel-2 measurements.
    assert all(
        p["NDVI"] is not None
        and p["NDMI"] is not None
        for p in missing_classes
    )
