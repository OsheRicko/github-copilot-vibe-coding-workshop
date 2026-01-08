from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
import secrets
import string


def generate_id(prefix: str) -> str:
    """Generate a random ID with the given prefix."""
    chars = string.ascii_letters + string.digits + "_-"
    random_part = ''.join(secrets.choice(chars) for _ in range(8))
    return f"{prefix}_{random_part}"


class Post(Base):
    __tablename__ = "posts"

    id = Column(String, primary_key=True, default=lambda: generate_id("p"))
    username = Column(String, nullable=False)
    content = Column(String, nullable=False)
    createdAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    updatedAt = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    likes = Column(Integer, nullable=False, default=0)

    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    liked_by = relationship("Like", back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(String, primary_key=True, default=lambda: generate_id("c"))
    postId = Column(String, ForeignKey("posts.id"), nullable=False)
    username = Column(String, nullable=False)
    content = Column(String, nullable=False)
    createdAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    updatedAt = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("Post", back_populates="comments")


class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    postId = Column(String, ForeignKey("posts.id"), nullable=False)
    username = Column(String, nullable=False)
    createdAt = Column(DateTime, nullable=False, default=datetime.utcnow)

    post = relationship("Post", back_populates="liked_by")

    __table_args__ = (
        UniqueConstraint('postId', 'username', name='unique_post_user_like'),
    )
