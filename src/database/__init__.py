from sqlalchemy import create_engine, text, Column, Integer, String, Index
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column

from config import (
    RDB_USERNAME,
    RDB_PASSWORD,
    RDB_HOST,
    RDB_PORT,
    RDB_NAME
)

_url = f'postgresql+psycopg://{RDB_USERNAME}:{RDB_PASSWORD}@{RDB_HOST}:{RDB_PORT}/{RDB_NAME}'
sql_engine = create_async_engine(_url, pool_pre_ping=True)

Base = declarative_base()

class Record(Base):
    __tablename__ = "records"
    __table_args__ = (Index("idx_prompt_id", "prompt_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, nullable=False)
    comfy_filepath: Mapped[str | None] = mapped_column(String)
    s3_key: Mapped[str | None] = mapped_column(String)

    def to_dict(self):
        return {key: value for key, value in vars(self).items() if not key.startswith("_")}

    def __repr__(self):
        return (
            f"<Record(id={self.id}, prompt_id={self.prompt_id}, "
            f"comfy_path={self.comfy_filepath}, s3_key={self.s3_key})>"
        )

def init_rdb():
    engine = create_engine(_url, echo=True, pool_pre_ping=True)
    with engine.begin() as conn:
        # Base.metadata.drop_all(conn)
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS app"))
        Base.metadata.create_all(conn)