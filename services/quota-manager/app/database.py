import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

# DB_URL format: postgresql+asyncpg://user:password@host/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/medical_booking_db")

engine = None
AsyncSessionLocal = None

@asynccontextmanager
async def get_db():
    if os.getenv("PROJECT_ID") == "local-project":
        class MockDB:
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc, tb): pass
            async def execute(self, query, params=None): return None
            async def commit(self): pass
        yield MockDB()
        return

    global engine, AsyncSessionLocal
    if engine is None:
        engine = create_async_engine(DATABASE_URL, echo=True)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        yield session
