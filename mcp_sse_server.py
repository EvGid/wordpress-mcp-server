#!/usr/bin/env python3
"""
WordPress MCP SSE Server - Unified Registry Edition
Supports 53 allowlisted tools with multi-site dispatching via 'site' argument.
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.types import Tool, TextContent
from sse_starlette.sse import EventSourceResponse
import uvicorn

# Import the unified registry
from mcp_tools_registry import registry

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ==================== MCP SERVER INSTANCE ====================
mcp_server = Server("wordpress-mcp-server")

@mcp_server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available MCP tools from registry"""
    return registry.get_tools_metadata()

@mcp_server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls using registry dispatcher"""
    try:
        logger.info(f"Tool call: {name} with args: {arguments}")
        result = await registry.dispatch(name, arguments)
        
        # If result is already a string (wrapped JSON), use it
        if isinstance(result, str):
            try:
                # Check if it's already JSON
                json.loads(result)
                text_out = result
            except json.JSONDecodeError:
                text_out = json.dumps({"result": result})
        else:
            text_out = json.dumps(result, ensure_ascii=False)
            
        return [TextContent(type="text", text=text_out)]
        
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
    logger.info("Starting WordPress MCP SSE Server (Unified Registry)...")
    yield
    logger.info("Shutting down WordPress MCP SSE Server...")
    await registry.close()

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
        "version": "2.0.0",
        "protocol": "MCP over SSE",
        "status": "online",
        "tools_count": len(tools),
        "endpoints": {
            "/": "Server information",
            "/health": "Health check",
            "/sse": "SSE endpoint",
            "/mcp": "MCP JSON-RPC endpoint"
        },
        "tools_list": [t.name for t in tools]
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "wordpress-mcp-sse-server",
        "registry_tools": len(registry.allowlist)
    }

@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint for MCP clients"""
    async def event_generator():
        host = request.headers.get("host", "localhost:8000")
        protocol = "https" if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https" else "http"
        prefix = request.headers.get("x-forwarded-prefix", "").rstrip("/")
        if prefix and not prefix.startswith("/"):
            prefix = "/" + prefix
        mcp_url = f"{protocol}://{host}{prefix}/mcp"
        
        yield {
            "event": "endpoint",
            "data": json.dumps({"url": mcp_url})
        }
        
        while True:
            if await request.is_disconnected():
                break
            yield {
                "event": "heartbeat",
                "data": json.dumps({"status": "alive"})
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
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {}
                    },
                    "serverInfo": {"name": "wordpress-mcp-server", "version": "2.0.0"}
                }
            }
        
        elif method == "tools/list":
            tools = await list_tools()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
                        for t in tools
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
                    "content": [{"type": r.type, "text": r.text} for r in results]
                }
            }
        
        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"resources": []}
            }
            
        elif method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"prompts": []}
            }
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }
    
    except Exception as e:
        logger.error(f"MCP error: {str(e)}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32603, "message": str(e)}
        }

if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", 8000))
    # Listen on all interfaces to allow external access (tunneling)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
