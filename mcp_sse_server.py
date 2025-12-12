#!/usr/bin/env python3
"""
WordPress MCP SSE Server for OpenAI and ChatGPT
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.types import Tool, TextContent
from sse_starlette.sse import EventSourceResponse
import uvicorn

# Load environment variables from .env file
load_dotenv()

# ==================== CONFIGURATION ====================
# Use environment variables with fallback to defaults
WORDPRESS_URL = os.getenv("WORDPRESS_URL", "https://your-wordpress-site.com/")
WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME", "your-username")
WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD", "your-password")

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== WORDPRESS MCP CLASS ====================
class WordPressMCP:
    """WordPress MCP client for managing posts via REST API"""
    
    def __init__(self, base_url: str, username: str, password: str):
        """
        Initialize WordPress MCP client
        
        Args:
            base_url: WordPress site URL (e.g., https://example.com/)
            username: WordPress username
            password: WordPress application password or user password
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.client = httpx.AsyncClient(
            auth=(username, password),
            timeout=30.0,
            headers={"Content-Type": "application/json"}
        )
        logger.info(f"WordPressMCP initialized for {base_url}")
    
    async def create_post(
        self,
        title: str,
        content: str,
        excerpt: str = "",
        status: str = "publish"
    ) -> Dict[str, Any]:
        """
        Create a new WordPress post
        
        Args:
            title: Post title
            content: Post content in HTML
            excerpt: Post excerpt (optional)
            status: Post status (publish, draft, private)
        
        Returns:
            Dict with success, post_id, url, message
        """
        try:
            url = f"{self.base_url}/wp-json/wp/v2/posts"
            payload = {
                "title": title,
                "content": content,
                "excerpt": excerpt,
                "status": status
            }
            
            logger.info(f"Creating post: {title[:50]}...")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            result = {
                "success": True,
                "post_id": data.get("id"),
                "url": data.get("link"),
                "message": f"Post '{title}' created successfully"
            }
            logger.info(f"Post created: ID={result['post_id']}, URL={result['url']}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating post: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "post_id": None,
                "url": None,
                "message": f"HTTP error: {e.response.status_code} - {e.response.text[:200]}"
            }
        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            return {
                "success": False,
                "post_id": None,
                "url": None,
                "message": f"Error: {str(e)}"
            }
    
    async def update_post(
        self,
        post_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        excerpt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing WordPress post
        
        Args:
            post_id: Post ID to update
            title: New title (optional)
            content: New content (optional)
            excerpt: New excerpt (optional)
        
        Returns:
            Dict with success, post_id, url, message
        """
        try:
            url = f"{self.base_url}/wp-json/wp/v2/posts/{post_id}"
            payload = {}
            
            if title is not None:
                payload["title"] = title
            if content is not None:
                payload["content"] = content
            if excerpt is not None:
                payload["excerpt"] = excerpt
            
            if not payload:
                return {
                    "success": False,
                    "post_id": post_id,
                    "url": None,
                    "message": "No fields to update"
                }
            
            logger.info(f"Updating post ID={post_id}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            result = {
                "success": True,
                "post_id": data.get("id"),
                "url": data.get("link"),
                "message": f"Post ID={post_id} updated successfully"
            }
            logger.info(f"Post updated: ID={result['post_id']}, URL={result['url']}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error updating post: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "post_id": post_id,
                "url": None,
                "message": f"HTTP error: {e.response.status_code} - {e.response.text[:200]}"
            }
        except Exception as e:
            logger.error(f"Error updating post: {str(e)}")
            return {
                "success": False,
                "post_id": post_id,
                "url": None,
                "message": f"Error: {str(e)}"
            }
    
    async def get_posts(
        self,
        per_page: int = 10,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Get list of WordPress posts
        
        Args:
            per_page: Number of posts per page (1-100)
            page: Page number
        
        Returns:
            Dict with success, posts, count, message
        """
        try:
            # Validate per_page
            per_page = max(1, min(100, per_page))
            page = max(1, page)
            
            url = f"{self.base_url}/wp-json/wp/v2/posts"
            params = {
                "per_page": per_page,
                "page": page
            }
            
            logger.info(f"Getting posts: page={page}, per_page={per_page}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            posts = response.json()
            total_posts = int(response.headers.get("X-WP-Total", len(posts)))
            
            # Format posts for response
            formatted_posts = []
            for post in posts:
                formatted_posts.append({
                    "id": post.get("id"),
                    "title": post.get("title", {}).get("rendered", ""),
                    "excerpt": post.get("excerpt", {}).get("rendered", ""),
                    "status": post.get("status"),
                    "url": post.get("link"),
                    "date": post.get("date")
                })
            
            result = {
                "success": True,
                "posts": formatted_posts,
                "count": len(formatted_posts),
                "total": total_posts,
                "page": page,
                "per_page": per_page,
                "message": f"Retrieved {len(formatted_posts)} posts"
            }
            logger.info(f"Retrieved {len(formatted_posts)} posts")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting posts: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "posts": [],
                "count": 0,
                "message": f"HTTP error: {e.response.status_code} - {e.response.text[:200]}"
            }
        except Exception as e:
            logger.error(f"Error getting posts: {str(e)}")
            return {
                "success": False,
                "posts": [],
                "count": 0,
                "message": f"Error: {str(e)}"
            }
    
    async def delete_post(self, post_id: int) -> Dict[str, Any]:
        """
        Delete a WordPress post
        
        Args:
            post_id: Post ID to delete
        
        Returns:
            Dict with success, post_id, message
        """
        try:
            url = f"{self.base_url}/wp-json/wp/v2/posts/{post_id}"
            
            logger.info(f"Deleting post ID={post_id}")
            response = await self.client.delete(url, params={"force": True})
            response.raise_for_status()
            
            result = {
                "success": True,
                "post_id": post_id,
                "message": f"Post ID={post_id} deleted successfully"
            }
            logger.info(f"Post deleted: ID={post_id}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error deleting post: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "post_id": post_id,
                "message": f"HTTP error: {e.response.status_code} - {e.response.text[:200]}"
            }
        except Exception as e:
            logger.error(f"Error deleting post: {str(e)}")
            return {
                "success": False,
                "post_id": post_id,
                "message": f"Error: {str(e)}"
            }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("WordPressMCP client closed")

# ==================== GLOBAL INSTANCES ====================
wordpress_mcp: Optional[WordPressMCP] = None
mcp_server = Server("wordpress-mcp-server")

# ==================== MCP TOOLS DEFINITION ====================
@mcp_server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available MCP tools"""
    return [
        Tool(
            name="create_post",
            description="Create a new WordPress post on your site",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Post title"
                    },
                    "content": {
                        "type": "string",
                        "description": "Post content in HTML"
                    },
                    "excerpt": {
                        "type": "string",
                        "description": "Post excerpt",
                        "default": ""
                    },
                    "status": {
                        "type": "string",
                        "enum": ["publish", "draft", "private"],
                        "default": "publish",
                        "description": "Post status"
                    }
                },
                "required": ["title", "content"]
            }
        ),
        Tool(
            name="update_post",
            description="Update an existing WordPress post",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Post ID to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New post title"
                    },
                    "content": {
                        "type": "string",
                        "description": "New post content in HTML"
                    },
                    "excerpt": {
                        "type": "string",
                        "description": "New post excerpt"
                    }
                },
                "required": ["post_id"]
            }
        ),
        Tool(
            name="get_posts",
            description="Get list of WordPress posts",
            inputSchema={
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of posts per page (1-100)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1
                    }
                }
            }
        ),
        Tool(
            name="delete_post",
            description="Delete a WordPress post",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Post ID to delete"
                    }
                },
                "required": ["post_id"]
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    global wordpress_mcp
    
    if wordpress_mcp is None:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "message": "WordPress MCP client not initialized"
            })
        )]
    
    try:
        logger.info(f"Tool call: {name} with args: {arguments}")
        
        if name == "create_post":
            result = await wordpress_mcp.create_post(
                title=arguments["title"],
                content=arguments["content"],
                excerpt=arguments.get("excerpt", ""),
                status=arguments.get("status", "publish")
            )
        elif name == "update_post":
            result = await wordpress_mcp.update_post(
                post_id=arguments["post_id"],
                title=arguments.get("title"),
                content=arguments.get("content"),
                excerpt=arguments.get("excerpt")
            )
        elif name == "get_posts":
            result = await wordpress_mcp.get_posts(
                per_page=arguments.get("per_page", 10),
                page=arguments.get("page", 1)
            )
        elif name == "delete_post":
            result = await wordpress_mcp.delete_post(
                post_id=arguments["post_id"]
            )
        else:
            result = {
                "success": False,
                "message": f"Unknown tool: {name}"
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(result)
        )]
        
    except KeyError as e:
        logger.error(f"Missing required argument: {str(e)}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "message": f"Missing required argument: {str(e)}"
            })
        )]
    except Exception as e:
        logger.error(f"Error calling tool {name}: {str(e)}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "message": f"Error: {str(e)}"
            })
        )]

# ==================== FASTAPI APP ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI"""
    global wordpress_mcp
    
    # Startup
    logger.info("Starting WordPress MCP SSE Server...")
    wordpress_mcp = WordPressMCP(
        WORDPRESS_URL,
        WORDPRESS_USERNAME,
        WORDPRESS_PASSWORD
    )
    logger.info("WordPress MCP Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down WordPress MCP SSE Server...")
    if wordpress_mcp:
        await wordpress_mcp.close()
    logger.info("WordPress MCP SSE Server stopped")

app = FastAPI(title="WordPress MCP SSE Server", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== FASTAPI ENDPOINTS ====================
@app.get("/")
async def root():
    """Server information endpoint"""
    tools = await list_tools()
    return {
        "name": "WordPress MCP SSE Server",
        "version": "1.0.0",
        "protocol": "MCP over SSE",
        "endpoints": {
            "/": "Server information",
            "/health": "Health check",
            "/sse": "SSE endpoint for ChatGPT",
            "/mcp": "MCP JSON-RPC endpoint"
        },
        "tools": [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in tools
        ]
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "wordpress-mcp-sse-server"
    }

@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint for ChatGPT"""
    async def event_generator():
        # Send endpoint information
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # Try to get the actual request host
        host = request.headers.get("host", f"{local_ip}:8000")
        protocol = "https" if request.url.scheme == "https" else "http"
        mcp_url = f"{protocol}://{host}/mcp"
        
        yield {
            "event": "endpoint",
            "data": json.dumps({"url": mcp_url})
        }
        
        # Send heartbeat every 15 seconds
        heartbeat_count = 0
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected")
                break
            
            heartbeat_count += 1
            yield {
                "event": "heartbeat",
                "data": json.dumps({"status": "alive", "count": heartbeat_count})
            }
            
            await asyncio.sleep(15)
    
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP JSON-RPC endpoint"""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        logger.info(f"MCP request: method={method}, id={request_id}")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "wordpress-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            tools = await list_tools()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in tools
                    ]
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_arguments = params.get("arguments", {})
            
            results = await call_tool(tool_name, tool_arguments)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": result.type,
                            "text": result.text
                        }
                        for result in results
                    ]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error"
            }
        }
    except Exception as e:
        logger.error(f"Error processing MCP request: {str(e)}")
        return {
            "jsonrpc": "2.0",
            "id": request_id if 'request_id' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

# ==================== MAIN ====================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("WordPress MCP SSE Server")
    logger.info("Version: 1.0.0")
    logger.info("=" * 50)
    
    # Validate configuration
    if WORDPRESS_URL == "https://your-wordpress-site.com/" or not WORDPRESS_URL:
        logger.warning("⚠️  WORDPRESS_URL not configured! Please set WORDPRESS_URL environment variable or edit .env file")
    
    if WORDPRESS_USERNAME == "your-username" or not WORDPRESS_USERNAME:
        logger.warning("⚠️  WORDPRESS_USERNAME not configured! Please set WORDPRESS_USERNAME environment variable or edit .env file")
    
    if WORDPRESS_PASSWORD == "your-password" or not WORDPRESS_PASSWORD:
        logger.warning("⚠️  WORDPRESS_PASSWORD not configured! Please set WORDPRESS_PASSWORD environment variable or edit .env file")
    
    logger.info(f"WordPress URL: {WORDPRESS_URL}")
    logger.info(f"WordPress Username: {WORDPRESS_USERNAME}")
    logger.info("=" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

