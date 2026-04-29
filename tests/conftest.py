"""Shared fixtures."""
import os
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sqlite_store(tmp_path):
    from convaix.db import get_store
    store = get_store(f"sqlite://{tmp_path}/test.db")
    yield store
    store.close()


@pytest.fixture
def pg_store():
    url = os.getenv("CONVAIX_TEST_PG_URL")
    if not url:
        pytest.skip("CONVAIX_TEST_PG_URL not set")
    from convaix.db import get_store
    store = get_store(url)
    yield store
    store.close()


@pytest.fixture(params=["sqlite"])
def store(request, sqlite_store, pg_store):
    if request.param == "sqlite":
        return sqlite_store
    return pg_store
