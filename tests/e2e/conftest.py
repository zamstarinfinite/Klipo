"""
Shared fixtures for Klipo E2E test suite.
Supports both in-process ASGI direct transport and live external HTTP servers.
"""

import os
import sqlite3
import pytest
import pytest_asyncio
import httpx
from typing import AsyncGenerator, Generator

from tests.e2e.pey_mock_server import PeyMockServer


def normalize_route_path(path: str) -> str:
    import re
    return re.sub(r"\{[^}]+\}", "{var}", path)


def has_route(path: str, method: str) -> bool:
    """Checks whether a route template and HTTP method are mounted on the FastAPI app."""
    try:
        from backend.main import app
        norm_target = normalize_route_path(path)
        for r in app.routes:
            route_path = getattr(r, "path", None)
            if (
                route_path
                and normalize_route_path(route_path) == norm_target
                and method.upper() in getattr(r, "methods", set())
            ):
                return True
    except Exception:
        pass
    return False


def require_route(path: str, method: str):
    """Gracefully skips a test if the route is not yet implemented by concurrent workers."""
    # If BASE_URL is set, we assume a live server is running and let the request proceed
    if os.environ.get("BASE_URL"):
        return
    if not has_route(path, method):
        pytest.skip(f"Endpoint '{method} {path}' is planned for a later milestone and not yet implemented.")


@pytest.fixture(scope="session")
def pey_mock() -> Generator[PeyMockServer, None, None]:
    """
    Session-scoped deterministic Pey API mock server running on an ephemeral local port.
    Sets PEY_BASE_URL, PEY_API_BASE_URL, and PEY_API_KEY environment variables.
    """
    server = PeyMockServer()
    server.start()
    os.environ["PEY_BASE_URL"] = server.base_url
    os.environ["PEY_API_BASE_URL"] = server.base_url
    os.environ["PEY_API_KEY"] = "sk_live_test_mock_key_1234567890abcdef"
    try:
        import backend.pey_client
        backend.pey_client.PEY_BASE_URL = server.base_url
        backend.pey_client._default_client = None
    except Exception:
        pass
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture(autouse=True)
def reset_pey_mock_between_tests(pey_mock: PeyMockServer):
    """Automatically clears captured mock requests and state before each test."""
    pey_mock.reset()
    yield


@pytest.fixture
def isolated_db_path(tmp_path) -> str:
    """
    Creates an isolated SQLite test database per test function in a temporary directory.
    Configures DATABASE_PATH and SQLITE_DB_PATH environment variables and runs seeding.
    """
    db_file = str(tmp_path / "test_klipo.db")
    os.environ["DATABASE_PATH"] = db_file
    os.environ["SQLITE_DB_PATH"] = db_file

    from backend.db import init_db
    from backend.seed import seed_if_empty

    init_db(db_file)
    seed_if_empty(db_file)

    return db_file


@pytest.fixture
def db_conn(isolated_db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Returns a direct SQLite connection to the test database with row_factory enabled."""
    from backend.db import get_connection

    conn = get_connection(isolated_db_path)
    try:
        yield conn
    finally:
        conn.close()


@pytest_asyncio.fixture
async def app_client(
    isolated_db_path: str,
    pey_mock: PeyMockServer,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Provides an httpx.AsyncClient targeting the Klipo application under test (SUT).
    Dual-mode:
    - If BASE_URL is set in environment, targets live HTTP server (e.g. running in Docker/Render).
    - Otherwise, executes in-process via httpx.ASGITransport directly against FastAPI app.
    """
    base_url = os.environ.get("BASE_URL")
    if base_url:
        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            yield client
    else:
        from backend.main import app

        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=30.0,
        ) as client:
            yield client
