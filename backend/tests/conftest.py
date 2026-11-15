import os
import shutil
import tempfile
from typing import AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio

from backend.db import get_connection, init_db
from backend.main import app, get_db
from backend.seed import seed_if_empty


@pytest.fixture(scope="function")
def test_db() -> Generator[str, None, None]:
    """Creates a temporary SQLite database initialized and seeded for each test."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_klipo.db")
    os.environ["DATABASE_PATH"] = db_path

    init_db(db_path)
    seed_if_empty(db_path)

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    yield db_path

    app.dependency_overrides.clear()
    if "DATABASE_PATH" in os.environ:
        del os.environ["DATABASE_PATH"]
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def async_client(test_db: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides an authenticated httpx AsyncClient mounted directly to the FastAPI app."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
