from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from database import Record, sql_engine


class RecordRepository:
    @staticmethod
    async def create(record: Record) -> Record:
        async_session = async_sessionmaker(sql_engine)
        async with async_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record

    @staticmethod
    async def retrieve_by_prompt_id(prompt_id: str) -> Record:
        async_session = async_sessionmaker(sql_engine)
        async with async_session() as session:
            stmt = select(Record).where(Record.prompt_id == prompt_id)
            result = await session.execute(stmt)
            record = result.scalars().first()
            return record
    @staticmethod
    async def update(record: Record) -> Record:
        async_session = async_sessionmaker(sql_engine)
        async with async_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record
