from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from app.conf import Settings

engine = create_async_engine(Settings.DATABASE_URL)
class Base(declarative_base):
    pass
SESSION = async_sessionmaker(bind=engine,autoflush=False,autocommit=False)

async def get_conn():
    try:
        async with SESSION() as session:
            yield session
            await session.commit()
    except Exception:
        await  session.rollback()
        raise

