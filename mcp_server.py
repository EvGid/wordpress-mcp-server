#!/usr/bin/env python3
"""
WordPress MCP Server - Comprehensive WordPress & Server Management
Built with official MCP Python SDK (FastMCP)
"""

# ==================== TRANSPORT SECURITY & SSE PATCH ====================
# The MCP SDK includes DNS rebinding protection that rejects Cloudflare Tunnel URLs.
# We apply a definitive patch to disable security checks and ADD AGGRESSIVE LOGGING.
try:
    import sys
    import logging
    import mcp.server.transport_security as ts
    import mcp.server.sse as mcp_sse
    from starlette.requests import Request
    from starlette.responses import Response

    # 1. Patch TransportSecurityMiddleware (The Gatekeeper)
    if hasattr(ts, "TransportSecurityMiddleware"):
        async def mock_validate(self, request: Request, is_post: bool = False) -> Response | None:
            # DEBUG: Log every validation attempt
            # We use print to stderr because logger might be filtered
            print(f"DEBUG: Security bypass for {request.method} {request.url.path}", file=sys.stderr)
            return None
        ts.TransportSecurityMiddleware.validate_request = mock_validate
        print("DEBUG: Successfully patched TransportSecurityMiddleware.validate_request", file=sys.stderr)

    # 2. Patch SseServerTransport.connect_sse (The Entrance) - This section is now handled by mcp.sse_app()
    #    The original patching logic for SseServerTransport.connect_sse is removed
    #    as mcp.sse_app() provides a more robust integration.
    #    The CloudflareOptimizationMiddleware and RequestDiagnosticMiddleware will be applied directly to the sse_app.

    # 3. Disable DNS rebinding in Settings
    if hasattr(ts, "TransportSecuritySettings"):
        try:
            ts.TransportSecuritySettings.model_fields['enable_dns_rebinding_protection'].default = False
        except:
            pass

    # 4. Functional ASGI Middleware (The Hybrid)
    # BaseHTTPMiddleware is broken for SSE in Starlette. 
    # We use a pure ASGI middleware to log and set headers safely.
    def diagnostic_middleware(app):
        async def asgi_app(scope, receive, send):
            if scope["type"] != "http":
                return await app(scope, receive, send)

            path = scope.get("path", "")
            method = scope.get("method", "")
            
            # 1. Redirect root to /sse to catch misconfigured clients (v1.2.0)
            if path == "/" and method == "GET":
                await send({
                    "type": "http.response.start", 
                    "status": 307,
                    "headers": [(b"location", b"/sse")]
                })
                await send({"type": "http.response.body", "body": b"", "more_body": False})
                print(f"DEBUG: Redirecting {method} {path} -> /sse", file=sys.stderr)
                return

            # Use a local flag to ensure padding is per-request (v1.2.0)
            request_state = {"padded": False}

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    # Add Cloudflare optimizations for SSE
                    if path == "/sse":
                        headers = list(message.get("headers", []))
                        headers.append((b"cache-control", b"no-cache, no-transform, no-store, must-revalidate"))
                        headers.append((b"x-accel-buffering", b"no"))
                        headers.append((b"x-content-type-options", b"nosniff"))
                        headers.append((b"connection", b"keep-alive"))
                        # Anti-compression: prevents Cloudflare from buffering to compress
                        headers.append((b"content-encoding", b"identity"))
                        # Force chunked encoding by removing content-length
                        headers = [h for h in headers if h[0].lower() != b"content-length"]
                        message["headers"] = headers
                    
                    status = message.get("status")
                    print(f"<-- {status} {path}", file=sys.stderr)
                
                # SSE Padding: Pulsed delivery 16KB (v1.2.0)
                if message["type"] == "http.response.body" and path == "/sse" and method == "GET":
                    if not request_state["padded"]:
                        # 16KB padding in 16 separate 1KB chunks
                        original_body = message.get("body") or b""
                        padding_chunk = b":" + b" " * 1024 + b"\n\n"
                        for i in range(15):
                            await send({"type": "http.response.body", "body": padding_chunk, "more_body": True})
                            await asyncio.sleep(0.01)
                        
                        # Use the original body from the app (the first byte of padding is already sent in chunks)
                        # We combine the LAST chunk with the original body to avoid ending the body prematurely
                        message["body"] = padding_chunk + original_body
                        request_state["padded"] = True
                        print(f"DEBUG: Sent 16KB pulsed padding to {method} {path}", file=sys.stderr)

                await send(message)

            print(f"--> {method} {path}" + (" (MCP Message)" if "/messages/" in path else ""), file=sys.stderr)
            return await app(scope, receive, send_wrapper)
        return asgi_app

    sys.modules['mcp.server.transport_security'] = ts
    sys.modules['mcp.server.sse'] = mcp_sse
except Exception as e:
    print(f"DEBUG: Critical patch failure: {e}", file=sys.stderr)

import asyncio
import json
from typing import Any, Dict, List, Optional
import httpx
from mcp.server.fastmcp import FastMCP, Context

# ==================== CONFIGURATION ====================
WORDPRESS_URL = "https://04travel.ru"
WORDPRESS_USERNAME = "oasis"
WORDPRESS_PASSWORD = "mfIk tKGA mJ0p gwSD KmkN N0Ve"

# ==================== LOGGING SETUP ====================
# Configure global logging to use stderr so it doesn't corrupt MCP stdio protocol
logging.basicConfig(
    level=logging.WARNING, # Only warnings and above to be safe
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True
)
logger = logging.getLogger(__name__)




# ==================== WORDPRESS CLIENT ====================
class WordPressClient:
    """Async WordPress REST API client"""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(
            auth=(username, password),
            timeout=30.0,
            headers={"Content-Type": "application/json"}
        )

    
    async def request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to WordPress API"""
        try:
            url = f"{self.base_url}/wp-json/wp/v2/{endpoint}"
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.text else {}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise
    
    async def close(self):
        await self.client.aclose()

# wp_client will be initialized lazily
wp_client = None

def get_wp_client():
    global wp_client
    if wp_client is None:
        wp_client = WordPressClient(WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
    return wp_client


# ==================== FASTMCP SERVER ====================
mcp = FastMCP("WordPress MCP Server")

# ==================== POST MANAGEMENT TOOLS ====================

@mcp.tool()
async def get_post(post_id: int = None, slug: str = None) -> str:
    """Get a single WordPress post by ID or slug
    
    Args:
        post_id: Post ID (optional)
        slug: Post slug (optional)
    """
    try:
        if post_id:
            data = await get_wp_client().request("GET", f"posts/{post_id}")
        elif slug:
            posts = await get_wp_client().request("GET", f"posts?slug={slug}")
            data = posts[0] if posts else None
        else:
            return json.dumps({"success": False, "message": "Provide post_id or slug"})
        
        if data:
            return json.dumps({
                "success": True,
                "post": {
                    "id": data["id"],
                    "title": data["title"]["rendered"],
                    "content": data["content"]["rendered"],
                    "status": data["status"],
                    "url": data["link"]
                }
            })
        return json.dumps({"success": False, "message": "Post not found"})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def create_post(
    title: str,
    content: str,
    excerpt: str = "",
    status: str = "publish",
    categories: List[int] = None,
    tags: List[int] = None
) -> str:
    """Create a new WordPress post
    
    Args:
        title: Post title
        content: Post content (HTML)
        excerpt: Post excerpt (optional)
        status: Post status (publish, draft, private)
        categories: List of category IDs (optional)
        tags: List of tag IDs (optional)
    """
    try:
        payload = {
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "status": status
        }
        if categories:
            payload["categories"] = categories
        if tags:
            payload["tags"] = tags
        
        data = await get_wp_client().request("POST", "posts", json=payload)
        return json.dumps({
            "success": True,
            "post_id": data["id"],
            "url": data["link"],
            "message": f"Post '{title}' created successfully"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def update_post(
    post_id: int,
    title: str = None,
    content: str = None,
    excerpt: str = None,
    status: str = None
) -> str:
    """Update an existing WordPress post
    
    Args:
        post_id: Post ID to update
        title: New title (optional)
        content: New content (optional)
        excerpt: New excerpt (optional)
        status: New status (optional)
    """
    try:
        payload = {}
        if title is not None:
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        if excerpt is not None:
            payload["excerpt"] = excerpt
        if status is not None:
            payload["status"] = status
        
        data = await get_wp_client().request("POST", f"posts/{post_id}", json=payload)
        return json.dumps({
            "success": True,
            "post_id": data["id"],
            "url": data["link"],
            "message": f"Post {post_id} updated successfully"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def delete_post(post_id: int, force: bool = True) -> str:
    """Delete a WordPress post permanently or move to trash
    
    Args:
        post_id: Post ID to delete
        force: If True, delete permanently. If False, move to trash
    """
    try:
        params = {"force": "true" if force else "false"}
        await get_wp_client().request("DELETE", f"posts/{post_id}", params=params)
        action = "deleted permanently" if force else "moved to trash"
        return json.dumps({
            "success": True,
            "post_id": post_id,
            "message": f"Post {post_id} {action}"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def get_posts(
    per_page: int = 10,
    page: int = 1,
    status: str = "publish",
    search: str = None
) -> str:
    """Get list of WordPress posts with filters
    
    Args:
        per_page: Number of posts per page (1-100)
        page: Page number
        status: Post status filter (publish, draft, private, any)
        search: Search term (optional)
    """
    try:
        params = {
            "per_page": min(per_page, 100),
            "page": page,
            "status": status
        }
        if search:
            params["search"] = search
        
        response = await get_wp_client().client.get(
            f"{get_wp_client().base_url}/wp-json/wp/v2/posts",
            params=params
        )
        response.raise_for_status()
        posts = response.json()
        total = int(response.headers.get("X-WP-Total", len(posts)))
        
        formatted_posts = [
            {
                "id": p["id"],
                "title": p["title"]["rendered"],
                "status": p["status"],
                "date": p["date"],
                "url": p["link"]
            }
            for p in posts
        ]
        
        return json.dumps({
            "success": True,
            "posts": formatted_posts,
            "count": len(formatted_posts),
            "total": total,
            "page": page,
            "per_page": per_page
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def publish_post(post_id: int) -> str:
    """Publish a draft post
    
    Args:
        post_id: Post ID to publish
    """
    try:
        data = await get_wp_client().request("POST", f"posts/{post_id}", json={"status": "publish"})
        return json.dumps({
            "success": True,
            "post_id": data["id"],
            "url": data["link"],
            "message": f"Post {post_id} published"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def unpublish_post(post_id: int) -> str:
    """Unpublish a post (move to draft)
    
    Args:
        post_id: Post ID to unpublish
    """
    try:
        data = await get_wp_client().request("POST", f"posts/{post_id}", json={"status": "draft"})
        return json.dumps({
            "success": True,
            "post_id": data["id"],
            "message": f"Post {post_id} moved to draft"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

# ==================== PAGE MANAGEMENT TOOLS ====================

@mcp.tool()
async def get_page(page_id: int = None, slug: str = None) -> str:
    """Get a single WordPress page by ID or slug
    
    Args:
        page_id: Page ID (optional)
        slug: Page slug (optional)
    """
    try:
        if page_id:
            data = await get_wp_client().request("GET", f"pages/{page_id}")
        elif slug:
            pages = await get_wp_client().request("GET", f"pages?slug={slug}")
            data = pages[0] if pages else None
        else:
            return json.dumps({"success": False, "message": "Provide page_id or slug"})
        
        if data:
            return json.dumps({
                "success": True,
                "page": {
                    "id": data["id"],
                    "title": data["title"]["rendered"],
                    "content": data["content"]["rendered"],
                    "status": data["status"],
                    "url": data["link"]
                }
            })
        return json.dumps({"success": False, "message": "Page not found"})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def create_page(
    title: str,
    content: str,
    status: str = "publish",
    parent: int = 0
) -> str:
    """Create a new WordPress page
    
    Args:
        title: Page title
        content: Page content (HTML)
        status: Page status (publish, draft, private)
        parent: Parent page ID (0 for top-level)
    """
    try:
        payload = {
            "title": title,
            "content": content,
            "status": status,
            "parent": parent
        }
        
        data = await get_wp_client().request("POST", "pages", json=payload)
        return json.dumps({
            "success": True,
            "page_id": data["id"],
            "url": data["link"],
            "message": f"Page '{title}' created successfully"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def update_page(
    page_id: int,
    title: str = None,
    content: str = None,
    status: str = None
) -> str:
    """Update an existing WordPress page
    
    Args:
        page_id: Page ID to update
        title: New title (optional)
        content: New content (optional)
        status: New status (optional)
    """
    try:
        payload = {}
        if title is not None:
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        if status is not None:
            payload["status"] = status
        
        data = await get_wp_client().request("POST", f"pages/{page_id}", json=payload)
        return json.dumps({
            "success": True,
            "page_id": data["id"],
            "url": data["link"],
            "message": f"Page {page_id} updated successfully"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def delete_page(page_id: int, force: bool = True) -> str:
    """Delete a WordPress page
    
    Args:
        page_id: Page ID to delete
        force: If True, delete permanently. If False, move to trash
    """
    try:
        params = {"force": "true" if force else "false"}
        await get_wp_client().request("DELETE", f"pages/{page_id}", params=params)
        action = "deleted permanently" if force else "moved to trash"
        return json.dumps({
            "success": True,
            "page_id": page_id,
            "message": f"Page {page_id} {action}"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

# ==================== CATEGORY & TAG MANAGEMENT ====================

@mcp.tool()
async def get_categories(per_page: int = 100) -> str:
    """Get list of WordPress categories
    
    Args:
        per_page: Number of categories to retrieve
    """
    try:
        data = await get_wp_client().request("GET", f"categories?per_page={per_page}")
        categories = [
            {
                "id": cat["id"],
                "name": cat["name"],
                "slug": cat["slug"],
                "count": cat["count"]
            }
            for cat in data
        ]
        return json.dumps({"success": True, "categories": categories})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def create_category(name: str, description: str = "", parent: int = 0) -> str:
    """Create a new WordPress category
    
    Args:
        name: Category name
        description: Category description (optional)
        parent: Parent category ID (0 for top-level)
    """
    try:
        payload = {
            "name": name,
            "description": description,
            "parent": parent
        }
        data = await get_wp_client().request("POST", "categories", json=payload)
        return json.dumps({
            "success": True,
            "category_id": data["id"],
            "name": data["name"],
            "slug": data["slug"]
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def get_tags(per_page: int = 100) -> str:
    """Get list of WordPress tags
    
    Args:
        per_page: Number of tags to retrieve
    """
    try:
        data = await get_wp_client().request("GET", f"tags?per_page={per_page}")
        tags = [
            {
                "id": tag["id"],
                "name": tag["name"],
                "slug": tag["slug"],
                "count": tag["count"]
            }
            for tag in data
        ]
        return json.dumps({"success": True, "tags": tags})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def create_tag(name: str, description: str = "") -> str:
    """Create a new WordPress tag
    
    Args:
        name: Tag name
        description: Tag description (optional)
    """
    try:
        payload = {
            "name": name,
            "description": description
        }
        data = await get_wp_client().request("POST", "tags", json=payload)
        return json.dumps({
            "success": True,
            "tag_id": data["id"],
            "name": data["name"],
            "slug": data["slug"]
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

# ==================== MEDIA MANAGEMENT ====================

@mcp.tool()
async def get_media(per_page: int = 10, page: int = 1) -> str:
    """Get list of media files
    
    Args:
        per_page: Number of media items per page
        page: Page number
    """
    try:
        params = {"per_page": per_page, "page": page}
        response = await get_wp_client().client.get(
            f"{get_wp_client().base_url}/wp-json/wp/v2/media",
            params=params
        )
        response.raise_for_status()
        media = response.json()
        
        formatted_media = [
            {
                "id": m["id"],
                "title": m["title"]["rendered"],
                "url": m["source_url"],
                "mime_type": m["mime_type"],
                "date": m["date"]
            }
            for m in media
        ]
        
        return json.dumps({
            "success": True,
            "media": formatted_media,
            "count": len(formatted_media)
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

# ==================== USER MANAGEMENT ====================

@mcp.tool()
async def get_users(per_page: int = 10) -> str:
    """Get list of WordPress users
    
    Args:
        per_page: Number of users to retrieve
    """
    try:
        data = await get_wp_client().request("GET", f"users?per_page={per_page}")
        users = [
            {
                "id": user["id"],
                "name": user["name"],
                "username": user["slug"],
                "email": user.get("email", ""),
                "roles": user.get("roles", [])
            }
            for user in data
        ]
        return json.dumps({"success": True, "users": users})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

# ==================== COMMENTS MANAGEMENT ====================

@mcp.tool()
async def get_comments(post_id: int = None, per_page: int = 10) -> str:
    """Get list of comments
    
    Args:
        post_id: Filter by post ID (optional)
        per_page: Number of comments to retrieve
    """
    try:
        endpoint = f"comments?per_page={per_page}"
        if post_id:
            endpoint += f"&post={post_id}"
        
        data = await get_wp_client().request("GET", endpoint)
        comments = [
            {
                "id": c["id"],
                "post_id": c["post"],
                "author": c["author_name"],
                "content": c["content"]["rendered"],
                "date": c["date"],
                "status": c["status"]
            }
            for c in data
        ]
        return json.dumps({"success": True, "comments": comments})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def approve_comment(comment_id: int) -> str:
    """Approve a comment
    
    Args:
        comment_id: Comment ID to approve
    """
    try:
        data = await get_wp_client().request("POST", f"comments/{comment_id}", json={"status": "approved"})
        return json.dumps({
            "success": True,
            "comment_id": data["id"],
            "message": f"Comment {comment_id} approved"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

@mcp.tool()
async def delete_comment(comment_id: int, force: bool = True) -> str:
    """Delete a comment
    
    Args:
        comment_id: Comment ID to delete
        force: If True, delete permanently. If False, move to trash
    """
    try:
        params = {"force": "true" if force else "false"}
        await get_wp_client().request("DELETE", f"comments/{comment_id}", params=params)
        action = "deleted permanently" if force else "moved to trash"
        return json.dumps({
            "success": True,
            "comment_id": comment_id,
            "message": f"Comment {comment_id} {action}"
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

# ==================== SITE INFORMATION ====================

@mcp.tool()
async def get_site_info() -> str:
    """Get WordPress site information"""
    try:
        response = await get_wp_client().client.get(f"{get_wp_client().base_url}/wp-json")
        response.raise_for_status()
        data = response.json()
        
        return json.dumps({
            "success": True,
            "site": {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "url": data.get("url", ""),
                "home": data.get("home", ""),
                "gmt_offset": data.get("gmt_offset", 0),
                "timezone_string": data.get("timezone_string", "")
            }
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

# ==================== MAIN ENTRY POINT ====================

async def cleanup():
    """Cleanup resources on shutdown"""
    await get_wp_client().close()

if __name__ == "__main__":
    import sys
    import logging
    
    # Determine transport based on arguments or default to stdio
    transport = "stdio"
    if len(sys.argv) > 1:
        if sys.argv[1] == "--http":
            transport = "streamable-http"
        elif sys.argv[1] == "--sse":
            transport = "sse"
    
    # Enable DEBUG logging to stderr for both stdio and network transports
    # This will help us see exactly what's failing in the SSE handshake
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr,
        force=True
    )
    
    logger.info(f"Starting WordPress MCP Server with {transport} transport")
    
    try:
        if transport == "sse":
            import uvicorn

            # Use the official sse_app() from FastMCP
            # This is more robust than manual transport management
            app = mcp.sse_app()
            
            # Wrap with our functional diagnostic middleware
            app = diagnostic_middleware(app)
            
            logger.info("Starting FastMCP SSE server on 0.0.0.0:8000")
            print("DEBUG: Server listening on 0.0.0.0:8000 for SSE transport", file=sys.stderr)
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        else:
            mcp.run(transport=transport)

    except Exception as e:
        logger.error(f"Server crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if transport == "stdio":
            import asyncio
            asyncio.run(cleanup())


