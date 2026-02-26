import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.core.database import Base, get_db
from app.main import app
from app.api.v1.auth import limiter as auth_limiter

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
    # Override get_db dependency so that it uses the test database session
    app.dependency_overrides[get_db] = lambda: db_session
    
    # Store original limiter states to restore after test
    original_app_limiter = getattr(app.state, "limiter", None)
    original_auth_limiter = auth_limiter.enabled
    
    # Disable rate limiting for tests to avoid interference
    if original_app_limiter:
        app.state.limiter.enabled = False
    auth_limiter.enabled = False
    
    yield 
    
    # Cleanup after test
    app.dependency_overrides.clear()
    if original_app_limiter:
        app.state.limiter.enabled = original_app_limiter.enabled
    auth_limiter.enabled = original_auth_limiter


@pytest.fixture(scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac