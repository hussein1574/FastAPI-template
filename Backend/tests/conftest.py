import pytest
from app.tasks.cleanup_tokens import cleanup_expired_tokens
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.core.database import Base, get_db
from app.main import app
from app.api.v1.auth import limiter as auth_limiter
from unittest.mock import patch, AsyncMock

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Fixture to create the database engine and setup/teardown tables for the test session
@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    # Create tables once for the entire test session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    # Drop tables and dispose engine after test session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

# Fixture to provide a database session for each test, with transaction rollback for isolation
@pytest.fixture(scope="function")
async def db_session(db_engine):
    connection = await db_engine.connect()
    # Start a transaction for test isolation
    transaction = await connection.begin()
    
    # Create a new session bound to the connection
    session = AsyncSession(bind=connection, expire_on_commit=False)
    
    yield session
    
    # Rollback transaction and close session after test
    await session.close()
    await transaction.rollback()
    await connection.close()




@pytest.fixture(scope="function", autouse=True)
def setup_app_dependencies(db_session):

    # Override the get_db dependency to use the test database session
    async def override_get_db():
        yield db_session
    # Override get_db dependency so that it uses the test database session
    app.dependency_overrides[get_db] = override_get_db
    
    # Store original limiter states to restore after test
    app_limiter = getattr(app.state, "limiter", None) # A reference to the app-level limiter if it exists
    original_app_limiter_state = app_limiter.enabled if app_limiter else None
    original_auth_limiter = auth_limiter.enabled
    
    # Disable rate limiting for tests to avoid interference
    if original_app_limiter_state:
        app.state.limiter.enabled = False
    auth_limiter.enabled = False
    
    yield 
    
    # Cleanup after test
    app.dependency_overrides.clear()
    if original_app_limiter_state is not None:
        app.state.limiter.enabled = original_app_limiter_state
    auth_limiter.enabled = original_auth_limiter


@pytest.fixture(scope="function")
async def client(setup_app_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac



@pytest.fixture(scope="function", autouse=True)
async def intercept_cleanup(db_session):
    async def test_cleanup():
        await cleanup_expired_tokens(db_session)
    with patch("app.tasks.cleanup_tokens.cleanup_expired_tokens", side_effect=test_cleanup):
        yield