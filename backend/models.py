"""SQLite 数据模型（SQLAlchemy ORM）"""
from datetime import datetime
from sqlalchemy import Column, Integer, Text, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base
from db import engine

Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    topic_date = Column(String(10), nullable=False)         # YYYY-MM-DD
    topic_index = Column(String(4), nullable=False)         # 01, 02...
    topic_id = Column(String(64), unique=True, nullable=False)  # topic-YYYYMMDD-NN
    content_md = Column(Text, default="")                    # 含 {{IMG:xxx}} 占位的 Markdown
    image_plan = Column(JSON, default=list)                  # 阶段三产出的图片规划 JSON
    status = Column(String(20), default="draft")             # draft/improving/planning/ready
    humanized = Column(Integer, default=0)                   # 0/1 是否已拟人化
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = relationship("Image", back_populates="article", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="article", cascade="all, delete-orphan")


class Image(Base):
    __tablename__ = "images"
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    index = Column(Integer, nullable=False)                  # 0=封面，1..N=文中
    role = Column(String(10), nullable=False)                # cover / inline
    section = Column(String(255), default="")                # 对应段落小标题
    description = Column(Text, default="")                   # 中文画面描述
    prompt = Column(Text, default="")                        # 英文正向 prompt
    negative_prompt = Column(Text, default="")               # 英文负向 prompt
    size_preset = Column(String(20), default="inline_4_3")
    width = Column(Integer, default=768)
    height = Column(Integer, default=576)
    seed = Column(Integer, default=0)
    file_path = Column(String(512), default="")              # 相对 ARTICLE_ASSETS_DIR 的文件名
    comfyui_prompt_id = Column(String(64), default="")
    status = Column(String(20), default="pending")           # pending/generating/done/failed
    error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    article = relationship("Article", back_populates="images")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    role = Column(String(10), nullable=False)                # user / assistant
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    article = relationship("Article", back_populates="chat_messages")


def init_db():
    Base.metadata.create_all(engine)
