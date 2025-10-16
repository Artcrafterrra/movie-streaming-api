from decimal import Decimal
from uuid import uuid4
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from database.session_sqlite import (
    AsyncSQLiteSessionLocal,
    reset_sqlite_database,
)
from database.models.movies import Movie, CertificationEnum
from routes import movies


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_db():
    """Reset SQLite database before each test"""
    await reset_sqlite_database()
    yield


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provide async session for DB operations"""
    async with AsyncSQLiteSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """Async test client for FastAPI"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def sample_movie(db_session):
    """Seed a sample movie into the database"""
    movie = Movie(
        movie_uuid=uuid4(),
        name="Test Movie",
        year=2024,
        time=120,
        imdb=8.5,
        votes=0,
        description="A test movie for integration testing.",
        price=Decimal("10.0"),
        certification=CertificationEnum.G,
    )
    db_session.add(movie)
    await db_session.commit()
    await db_session.refresh(movie)
    return movie


@pytest_asyncio.fixture
async def auth_headers():
    """Fake auth headers for authorized requests"""
    return {"Authorization": "Bearer fake_token"}


@pytest_asyncio.fixture(autouse=True)
def override_moderator_required():
    """Bypass moderator dependency"""

    async def fake_moderator_required():
        from database.models.accounts import UserModel

        return UserModel(id=1, email="fake@admin.com")

    app.dependency_overrides[movies.moderator_required] = (
        fake_moderator_required
    )
    yield
    app.dependency_overrides.pop(movies.moderator_required, None)
