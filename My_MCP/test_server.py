"""
Test script for WordPress MCP Server
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from mcp_server import wp_client

async def test_connection():
    """Test WordPress API connection"""
    # Force UTF-8 output for Windows
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    
    print("Testing WordPress MCP Server...")
    print(f"URL: {wp_client.base_url}")
    print()
    
    try:
        # Test 1: Get site info
        print("Test 1: Getting site info...")
        response = await wp_client.client.get(f"{wp_client.base_url}/wp-json")
        response.raise_for_status()
        data = response.json()
        print(f"[OK] Site: {data.get('name')}")
        print(f"[OK] URL: {data.get('url')}")
        print()
        
        # Test 2: Get posts
        print("Test 2: Getting posts...")
        posts = await wp_client.request("GET", "posts?per_page=3")
        print(f"[OK] Found {len(posts)} posts:")
        for post in posts:
            print(f"   - {post['title']['rendered']}")
        print()
        
        # Test 3: Get categories
        print("Test 3: Getting categories...")
        categories = await wp_client.request("GET", "categories?per_page=5")
        print(f"[OK] Found {len(categories)} categories:")
        for cat in categories:
            print(f"   - {cat['name']} ({cat['count']} posts)")
        print()
        
        print("="*50)
        print("[SUCCESS] ALL TESTS PASSED!")
        print("="*50)
        print()
        print("Server is ready to use!")
        print("You can now:")
        print("1. Use it in Antigravity (stdio mode)")
        print("2. Use it in ChatGPT (run with --http flag)")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False
    finally:
        await wp_client.close()
    
    return True

if __name__ == "__main__":
    # Set event loop policy for Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
