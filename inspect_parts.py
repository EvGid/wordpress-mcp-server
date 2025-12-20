import requests
import json
import sys
import os

sys.path.append(os.getcwd())
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

from mcp_sse_server import WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD

def inspect_parts():
    auth = (WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
    url = f"{WORDPRESS_URL}/wp-json/wp/v2/template-parts?context=edit"
    
    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        
        for item in data:
            print(f"ID: {item['id']}")
            print(f"Slug: {item['slug']}")
            print(f"Title: {item['title']['raw']}")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_parts()
