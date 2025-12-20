import requests
import json
import sys
import os

sys.path.append(os.getcwd())
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

from mcp_sse_server import WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD

def inspect_nav():
    auth = (WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
    # Add context=edit to get raw content
    url = f"{WORDPRESS_URL}/wp-json/wp/v2/navigation?context=edit"
    
    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        
        for item in data:
            print(f"ID: {item['id']}")
            print(f"Title: {item['title']['raw']}") # Title also has raw in edit context
            if 'content' in item:
                print("Content keys:", item['content'].keys())
                if 'raw' in item['content']:
                    print("Content (Raw):")
                    print(item['content']['raw'])
                else:
                    print("No raw content found.")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error: {e}")
        if 'response' in locals():
            print(response.text[:500])

if __name__ == "__main__":
    inspect_nav()
