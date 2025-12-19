import asyncio
import os
import sys
import logging

# Ensure we can import from the directory
sys.path.append(os.getcwd())

from mcp_sse_server import WordPressMCP, WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verifier")

async def test_connection():
    print(f"Testing connection to: {WORDPRESS_URL}")
    print(f"Username: {WORDPRESS_USERNAME}")
    # Don't print password obviously
    if WORDPRESS_PASSWORD == "your-password":
        print("ERROR: Password appears to be the default 'your-password'. Please update configuration.")
        return

    mcp = WordPressMCP(WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
    
    try:
        # Try to fetch 1 post to verify auth works
        print("Attempting to fetch posts...")
        result = await mcp.get_posts(per_page=1)
        
        if result["success"]:
            print("[OK] Connection SUCCESSFUL!")
            print(f"Found {result['total']} posts.")
            print(f"Server returned: {result['message']}")
        else:
            print("[FAIL] Connection FAILED.")
            print(f"Error message: {result['message']}")
            
    except Exception as e:
        print(f"[ERROR] Connection CRASHED: {e}")
    finally:
        await mcp.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_connection())
