from datetime import datetime
from typing import Annotated
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import yaml

from database import get_db, init_db
from models import Post as DBPost, Comment as DBComment, Like as DBLike
from schemas import (
    Post, NewPost, UpdatePost,
    Comment, NewComment, UpdateComment,
    LikeRequest, ErrorResponse
)

# Load OpenAPI specification
with open("../openapi.yaml", "r") as f:
    openapi_spec = yaml.safe_load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (if needed)


# Create FastAPI app with custom OpenAPI
app = FastAPI(
    title=openapi_spec["info"]["title"],
    version=openapi_spec["info"]["version"],
    description=openapi_spec["info"]["description"],
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
DBSession = Annotated[Session, Depends(get_db)]


# Custom OpenAPI schema to match the spec exactly
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    # Use the loaded OpenAPI spec but update paths to include /api prefix
    openapi_schema = openapi_spec.copy()
    
    # Add the actual routes from the app
    from fastapi.openapi.utils import get_openapi
    generated = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Use the paths from our openapi.yaml
    openapi_schema["paths"] = openapi_spec["paths"]
    openapi_schema["components"] = openapi_spec["components"]
    openapi_schema["tags"] = openapi_spec.get("tags", [])
    openapi_schema["servers"] = [{"url": "http://localhost:8000/api", "description": "Local development server"}]
    openapi_schema["openapi"] = "3.0.1"
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Helper function to create error response
def error_response(code: str, message: str, status_code: int, details: dict = None):
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message, details=details).model_dump(exclude_none=True)
    )


# ==================== ROOT ENDPOINT ====================

@app.get("/")
def root():
    """Root endpoint - redirects to API documentation."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/docs")


# ==================== POST ENDPOINTS ====================

@app.get("/api/posts", response_model=list[Post], tags=["Posts"])
def list_posts(db: DBSession):
    """List all posts."""
    try:
        posts = db.query(DBPost).all()
        return posts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


@app.post("/api/posts", response_model=Post, status_code=status.HTTP_201_CREATED, tags=["Posts"])
def create_post(post: NewPost, db: DBSession):
    """Create a new post."""
    if not post.username or not post.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_REQUEST", "message": "Invalid input for required fields."}
        )
    
    try:
        db_post = DBPost(
            username=post.username,
            content=post.content
        )
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        return db_post
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


@app.get("/api/posts/{postId}", response_model=Post, tags=["Posts"])
def get_post(postId: str, db: DBSession):
    """Get a single post by ID."""
    post = db.query(DBPost).filter(DBPost.id == postId).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Post not found"}
        )
    return post


@app.patch("/api/posts/{postId}", response_model=Post, tags=["Posts"])
def update_post(postId: str, post_update: UpdatePost, db: DBSession):
    """Update an existing post."""
    post = db.query(DBPost).filter(DBPost.id == postId).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Post not found"}
        )
    
    if not post_update.username or not post_update.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_REQUEST", "message": "Invalid input for required fields."}
        )
    
    try:
        post.username = post_update.username
        post.content = post_update.content
        post.updatedAt = datetime.utcnow()
        db.commit()
        db.refresh(post)
        return post
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


@app.delete("/api/posts/{postId}", status_code=status.HTTP_204_NO_CONTENT, tags=["Posts"])
def delete_post(postId: str, db: DBSession):
    """Delete a post by ID."""
    post = db.query(DBPost).filter(DBPost.id == postId).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Post not found"}
        )
    
    try:
        db.delete(post)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


# ==================== COMMENT ENDPOINTS ====================

@app.get("/api/posts/{postId}/comments", response_model=list[Comment], tags=["Comments"])
def list_comments(postId: str, db: DBSession):
    """List all comments for a post."""
    post = db.query(DBPost).filter(DBPost.id == postId).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Post not found"}
        )
    
    try:
        comments = db.query(DBComment).filter(DBComment.postId == postId).all()
        return comments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


@app.post("/api/posts/{postId}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED, tags=["Comments"])
def create_comment(postId: str, comment: NewComment, db: DBSession):
    """Create a new comment on a post."""
    post = db.query(DBPost).filter(DBPost.id == postId).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Post not found"}
        )
    
    if not comment.username or not comment.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_REQUEST", "message": "Invalid input for required fields."}
        )
    
    try:
        db_comment = DBComment(
            postId=postId,
            username=comment.username,
            content=comment.content
        )
        db.add(db_comment)
        db.commit()
        db.refresh(db_comment)
        return db_comment
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


@app.get("/api/posts/{postId}/comments/{commentId}", response_model=Comment, tags=["Comments"])
def get_comment(postId: str, commentId: str, db: DBSession):
    """Get a specific comment."""
    comment = db.query(DBComment).filter(
        DBComment.id == commentId,
        DBComment.postId == postId
    ).first()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Comment not found"}
        )
    return comment


@app.patch("/api/posts/{postId}/comments/{commentId}", response_model=Comment, tags=["Comments"])
def update_comment(postId: str, commentId: str, comment_update: UpdateComment, db: DBSession):
    """Update an existing comment."""
    comment = db.query(DBComment).filter(
        DBComment.id == commentId,
        DBComment.postId == postId
    ).first()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Comment not found"}
        )
    
    if not comment_update.username or not comment_update.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_REQUEST", "message": "Invalid input for required fields."}
        )
    
    try:
        comment.username = comment_update.username
        comment.content = comment_update.content
        comment.updatedAt = datetime.utcnow()
        db.commit()
        db.refresh(comment)
        return comment
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


@app.delete("/api/posts/{postId}/comments/{commentId}", status_code=status.HTTP_204_NO_CONTENT, tags=["Comments"])
def delete_comment(postId: str, commentId: str, db: DBSession):
    """Delete a comment."""
    comment = db.query(DBComment).filter(
        DBComment.id == commentId,
        DBComment.postId == postId
    ).first()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Comment not found"}
        )
    
    try:
        db.delete(comment)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


# ==================== LIKE ENDPOINTS ====================

@app.post("/api/posts/{postId}/likes", response_model=Post, tags=["Likes"])
def like_post(postId: str, like_request: LikeRequest, db: DBSession):
    """Like a post."""
    post = db.query(DBPost).filter(DBPost.id == postId).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Post not found"}
        )
    
    if not like_request.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_REQUEST", "message": "Invalid input for required field 'username'."}
        )
    
    try:
        # Check if already liked
        existing_like = db.query(DBLike).filter(
            DBLike.postId == postId,
            DBLike.username == like_request.username
        ).first()
        
        if not existing_like:
            # Create new like
            db_like = DBLike(
                postId=postId,
                username=like_request.username
            )
            db.add(db_like)
            post.likes += 1
            db.commit()
            db.refresh(post)
        
        return post
    except IntegrityError:
        db.rollback()
        # Already liked, just return the post
        db.refresh(post)
        return post
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


@app.delete("/api/posts/{postId}/likes", response_model=Post, tags=["Likes"])
def unlike_post(postId: str, like_request: LikeRequest, db: DBSession):
    """Unlike a post."""
    post = db.query(DBPost).filter(DBPost.id == postId).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Post not found"}
        )
    
    if not like_request.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_REQUEST", "message": "Invalid input for required field 'username'."}
        )
    
    try:
        # Find and delete the like
        like = db.query(DBLike).filter(
            DBLike.postId == postId,
            DBLike.username == like_request.username
        ).first()
        
        if like:
            db.delete(like)
            post.likes = max(0, post.likes - 1)
            db.commit()
            db.refresh(post)
        
        return post
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
