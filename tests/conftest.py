import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock

from app.app import app
from app.database import get_session, Base
from app.tasks import generate_ai_tag

TEST_DB_URL = 'sqlite+aiosqlite:///:memory:'
engine = create_async_engine(TEST_DB_URL, echo=False)
testing_async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

@pytest_asyncio.fixture(scope='function')
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(autouse=True) # autouse=True значит "применять ко всем тестам автоматически"
def mock_celery():
    # Мы подменяем метод .delay на пустышку
    generate_ai_tag.delay = MagicMock(return_value=None)
    yield

@pytest_asyncio.fixture(scope='function')
async def client(init_db):
    async def override_get_session():
        async with testing_async_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        yield ac

    app.dependency_overrides.clear()
        