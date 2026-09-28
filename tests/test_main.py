import json

import pytest
from fastapi.testclient import TestClient
from main import app, handler


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_home_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello"}


def test_about_route(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert response.json() == {"message": "This is the about page."}


def test_recommendations_and_input_limits(client):
    response = client.post("/recommend/", json={"preferences": {"category": "natural"}, "top_n": 3})
    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 3

    for top_n in (-1, 0, 21):
        response = client.post("/recommend/", json={"preferences": {}, "top_n": top_n})
        assert response.status_code == 422
    response = client.post("/recommend/", json={"preferences": {str(n): n for n in range(81)}})
    assert response.status_code == 422


def test_cors_only_allows_configured_origin(client):
    headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    response = client.options("/recommend/", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    response = client.options("/recommend/", headers={**headers, "Origin": "https://other.example"})
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_lambda_function_url_event():
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/recommend",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "requestContext": {"http": {"method": "POST", "path": "/recommend", "sourceIp": "127.0.0.1"}, "domainName": "example.lambda-url.us-east-1.on.aws", "stage": "$default"},
        "body": json.dumps({"preferences": {"category": "natural"}, "top_n": 2}),
        "isBase64Encoded": False,
    }
    response = handler(event, None)
    assert response["statusCode"] == 200
    assert len(json.loads(response["body"])["recommendations"]) == 2
