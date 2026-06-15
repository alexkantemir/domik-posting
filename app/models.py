from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False)  # editor | approver
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    content_items = relationship("ContentItem", back_populates="author", foreign_keys="ContentItem.created_by")


class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(Integer, primary_key=True)
    # text | url | photo | video | audio | photo_text
    type = Column(String(20), nullable=False)
    raw_text = Column(Text)
    file_paths = Column(Text)   # JSON-строка со списком путей
    source_url = Column(String(500))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    author = relationship("User", back_populates="content_items", foreign_keys=[created_by])
    generated_posts = relationship("GeneratedPost", back_populates="content_item")


class GeneratedPost(Base):
    __tablename__ = "generated_posts"

    id = Column(Integer, primary_key=True)
    content_item_id = Column(Integer, ForeignKey("content_items.id"))
    # telegram_channel | telegram_group | telegram_stories | vk | ok | yandex_maps | yandex_zen | instagram
    platform = Column(String(30), nullable=False)
    text = Column(Text)
    image_url = Column(String(500))
    extra_settings = Column(Text)  # JSON
    # draft | approved | rejected | published | failed
    status = Column(String(20), default="draft")
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    content_item = relationship("ContentItem", back_populates="generated_posts")
    approver = relationship("User", foreign_keys=[approved_by])
    publications = relationship("Publication", back_populates="generated_post")


class Publication(Base):
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True)
    generated_post_id = Column(Integer, ForeignKey("generated_posts.id"))
    platform = Column(String(30), nullable=False)
    published_at = Column(DateTime, nullable=True)
    platform_post_id = Column(String(200), nullable=True)
    post_url = Column(String(500), nullable=True)
    success = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)

    generated_post = relationship("GeneratedPost", back_populates="publications")
