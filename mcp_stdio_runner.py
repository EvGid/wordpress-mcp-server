import asyncio
import os
import sys
import logging

# Configure logging to write to file since stdout is used for MCP protocol
logging.basicConfig(
    filename='mcp_stdio.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Ensure we can import from the same directory
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)
os.chdir(script_dir)

try:
    import mcp_sse_server
except ImportError as e:
    logging.error(f"Failed to import mcp_sse_server: {e}")
    sys.exit(1)

async def main():
    try:
        # Initialize the global client manually since we aren't using the FastAPI lifespan
        logging.info("Initializing WordPressMCP client...")
        mcp_sse_server.wordpress_mcp = mcp_sse_server.WordPressMCP(
            mcp_sse_server.WORDPRESS_URL=https://04travel.ru
            mcp_sse_server.WORDPRESS_USERNAME=oasis
            mcp_sse_server.WORDPRESS_PASSWORD=mfIk tKGA mJ0p gwSD KmkN N0Ve
        )
        
        logging.info("Starting stdio server...")
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read, write):
            await mcp_sse_server.mcp_server.run(
                read, 
                write, 
                mcp_sse_server.mcp_server.create_initialization_options()
            )
    except Exception as e:
        logging.critical(f"Server crashed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
