#!/usr/bin/env python3
"""
WordPress REST API Server for ChatGPT
Simple REST API wrapper around WordPress functionality
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import httpx
import logging

# ==================== CONFIGURATION ====================
WORDPRESS_URL = "https://04travel.ru"
WORDPRESS_USERNAME = "oasis"
WORDPRESS_PASSWORD = "mfIk tKGA mJ0p gwSD KmkN N0Ve"

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FASTAPI APP ====================
app = FastAPI(
    title="WordPress API for ChatGPT",
    description="REST API for managing WordPress content",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== WORDPRESS CLIENT ====================
client = httpx.AsyncClient(
    auth=(WORDPRESS_USERNAME, WORDPRESS_PASSWORD),
    timeout=30.0
)

# ==================== MODELS ====================
class CreatePostRequest(BaseModel):
    title: str
    content: str
    excerpt: Optional[str] = ""
    status: Optional[str] = "publish"

class UpdatePostRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    status: Optional[str] = None

# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """API Info"""
    return {
        "name": "WordPress API for ChatGPT",
        "version": "1.0.0",
        "endpoints": {
            "posts": "/posts",
            "create_post": "/posts (POST)",
            "update_post": "/posts/{post_id} (PUT)",
            "delete_post": "/posts/{post_id} (DELETE)",
            "categories": "/categories",
            "site_info": "/site-info"
        }
    }

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy"}

@app.get("/posts")
async def get_posts(per_page: int = 10, page: int = 1, search: Optional[str] = None):
    """Get list of posts"""
    try:
        params = {"per_page": per_page, "page": page}
        if search:
            params["search"] = search
        
        response = await client.get(
            f"{WORDPRESS_URL}/wp-json/wp/v2/posts",
            params=params
        )
        response.raise_for_status()
        posts = response.json()
        
        return {
            "success": True,
            "posts": [
                {
                    "id": p["id"],
                    "title": p["title"]["rendered"],
                    "excerpt": p["excerpt"]["rendered"],
                    "status": p["status"],
                    "date": p["date"],
                    "url": p["link"]
                }
                for p in posts
            ],
            "count": len(posts)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/posts")
async def create_post(request: CreatePostRequest):
    """Create a new post"""
    try:
        payload = {
            "title": request.title,
            "content": request.content,
            "excerpt": request.excerpt,
            "status": request.status
        }
        
        response = await client.post(
            f"{WORDPRESS_URL}/wp-json/wp/v2/posts",
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "post_id": data["id"],
            "url": data["link"],
            "message": f"Post '{request.title}' created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/posts/{post_id}")
async def update_post(post_id: int, request: UpdatePostRequest):
    """Update a post"""
    try:
        payload = {}
        if request.title:
            payload["title"] = request.title
        if request.content:
            payload["content"] = request.content
        if request.excerpt:
            payload["excerpt"] = request.excerpt
        if request.status:
            payload["status"] = request.status
        
        response = await client.post(
            f"{WORDPRESS_URL}/wp-json/wp/v2/posts/{post_id}",
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "post_id": data["id"],
            "url": data["link"],
            "message": f"Post {post_id} updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/posts/{post_id}")
async def delete_post(post_id: int, force: bool = True):
    """Delete a post"""
    try:
        response = await client.delete(
            f"{WORDPRESS_URL}/wp-json/wp/v2/posts/{post_id}",
            params={"force": "true" if force else "false"}
        )
        response.raise_for_status()
        
        return {
            "success": True,
            "post_id": post_id,
            "message": f"Post {post_id} deleted"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/categories")
async def get_categories():
    """Get list of categories"""
    try:
        response = await client.get(
            f"{WORDPRESS_URL}/wp-json/wp/v2/categories?per_page=100"
        )
        response.raise_for_status()
        categories = response.json()
        
        return {
            "success": True,
            "categories": [
                {
                    "id": cat["id"],
                    "name": cat["name"],
                    "slug": cat["slug"],
                    "count": cat["count"]
                }
                for cat in categories
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/site-info")
async def get_site_info():
    """Get WordPress site information"""
    try:
        response = await client.get(f"{WORDPRESS_URL}/wp-json")
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "site": {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "url": data.get("url", ""),
                "home": data.get("home", "")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
