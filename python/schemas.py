from datetime import datetime
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(None, description="Optional additional error context")


class PostBase(BaseModel):
    username: str = Field(..., min_length=1, examples=["alice"])
    content: str = Field(..., min_length=1, examples=["Hello Contoso community!"])


class NewPost(PostBase):
    pass


class UpdatePost(PostBase):
    pass


class Post(PostBase):
    id: str = Field(..., pattern=r"^[A-Za-z0-9_-]+$", examples=["p_123abc"])
    createdAt: datetime = Field(..., examples=["2025-05-30T12:34:56Z"])
    updatedAt: datetime = Field(..., examples=["2025-05-30T12:34:56Z"])
    likes: int = Field(..., ge=0, examples=[3])

    class Config:
        from_attributes = True


class CommentBase(BaseModel):
    username: str = Field(..., min_length=1, examples=["bob"])
    content: str = Field(..., min_length=1, examples=["Nice post!"])


class NewComment(CommentBase):
    pass


class UpdateComment(CommentBase):
    pass


class Comment(CommentBase):
    id: str = Field(..., pattern=r"^[A-Za-z0-9_-]+$", examples=["c_123abc"])
    postId: str = Field(..., pattern=r"^[A-Za-z0-9_-]+$", examples=["p_123abc"])
    createdAt: datetime = Field(..., examples=["2025-05-30T12:34:56Z"])
    updatedAt: datetime = Field(..., examples=["2025-05-30T12:34:56Z"])

    class Config:
        from_attributes = True


class LikeRequest(BaseModel):
    username: str = Field(..., min_length=1, examples=["alice"])
