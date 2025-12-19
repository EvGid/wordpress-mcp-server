import asyncio
import os
import sys
import logging

# Ensure we can import from the directory
sys.path.append(os.getcwd())

from mcp_sse_server import WordPressMCP, WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD

async def show_first_page():
    mcp = WordPressMCP(WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
    try:
        print(f"Fetching posts from {WORDPRESS_URL}...\n")
        result = await mcp.get_posts(page=1, per_page=10)
        
        if result["success"]:
            posts = result["posts"]
            if not posts:
                print("No posts found.")
            
            for i, post in enumerate(posts, 1):
                title = post['title']
                status = post['status']
                date = post['date']
                print(f"{i}. [{status.upper()}] {title}")
                print(f"   Date: {date}")
                print(f"   Link: {post['url']}")
                print("-" * 40)
        else:
            print(f"Error: {result['message']}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mcp.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(show_first_page())
