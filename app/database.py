import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = os.getenv(
    'DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/zametki_db'
)

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

# для работы с celery делаем синхронный движок
SYNC_DATABASE_URL = DATABASE_URL.replace('+asyncpg', '')
sync_engine = create_engine(SYNC_DATABASE_URL, echo=True)
sync_session_maker = sessionmaker(sync_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
