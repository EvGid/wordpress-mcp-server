import asyncio
import os
import sys
import json
import requests

# Ensure we can import from the directory
sys.path.append(os.getcwd())
    
# Force utf-8 for windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

from mcp_sse_server import WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD

def check_capabilities():
    auth = (WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
    
    print(f"Checking API at {WORDPRESS_URL}")
    
    # 1. Check Root to see routes
    try:
        response = requests.get(f"{WORDPRESS_URL}/wp-json/", auth=auth)
        response.raise_for_status()
        data = response.json()
        routes = data.get("routes", {}).keys()
        
        print(f"\nFound {len(routes)} routes.")
        
        css_routes = [r for r in routes if "css" in r or "style" in r or "theme" in r]
        if css_routes:
            print("Potential CSS/Theme routes found:")
            for r in css_routes:
                print(f" - {r}")
        else:
            print("No obvious CSS routes found in root discovery.")
            
    except Exception as e:
        print(f"Error fetching root: {e}")

    # 2. Check for usable endpoints
    endpoints = [
        "wp/v2/custom_css",
        "wp/v2/template-parts",
        "wp/v2/navigation",
        "wp/v2/blocks"
    ]
    
    for ep in endpoints:
        try:
            url = f"{WORDPRESS_URL}/wp-json/{ep}"
            print(f"checking {ep}...")
            response = requests.get(url, auth=auth)
            print(f" - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                count = len(data) if isinstance(data, list) else "dict"
                print(f" - Accessible! Found {count} items.")
        except Exception as e:
            print(f" - Error: {e}")

if __name__ == "__main__":
    check_capabilities()
