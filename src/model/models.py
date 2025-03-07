# SQLAlchemy 模型定義
from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

class Base(DeclarativeBase):
    pass

class Article(Base):
    __tablename__ = 'articles'
    # 設定資料庫欄位
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String)
    link: Mapped[str] = mapped_column(String, unique=True)
    content: Mapped[Optional[str]] = mapped_column(String)
    published_at: Mapped[Optional[datetime]]
    source: Mapped[Optional[str]] = mapped_column(String)