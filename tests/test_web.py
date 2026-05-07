"""Web API tests."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(tmp_path):
    from convaix.web import create_app
    return create_app(f"sqlite://{tmp_path}/test.db")


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data


def test_list_snapshots(client):
    r = client.get("/api/snapshots")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_sources(client):
    r = client.get("/api/sources")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_search(client):
    r = client.get("/api/search?q=test")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
