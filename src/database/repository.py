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
    async def retrieve_by_comfy_task_id(comfy_task_id: str) -> Record:
        async_session = async_sessionmaker(sql_engine)
        async with async_session() as session:
            stmt = select(Record).where(Record.comfy_task_id == comfy_task_id)
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
