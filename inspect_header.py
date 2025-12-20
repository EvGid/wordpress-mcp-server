import requests
import json
import sys
import os

sys.path.append(os.getcwd())
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

from mcp_sse_server import WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD

def inspect_header():
    auth = (WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
    # Note: ID from previous step was twentytwentyfive//header
    # We might need to handle the double slash in URL
    part_id = "twentytwentyfive//header"
    url = f"{WORDPRESS_URL}/wp-json/wp/v2/template-parts/{part_id}?context=edit"
    
    try:
        response = requests.get(url, auth=auth)
        if response.status_code == 404:
            # Try single slash just in case
            url = f"{WORDPRESS_URL}/wp-json/wp/v2/template-parts/twentytwentyfive/header?context=edit"
            response = requests.get(url, auth=auth)
            
        response.raise_for_status()
        data = response.json()
        
        print("Header Content (Raw):")
        print(data['content']['raw'])
            
    except Exception as e:
        print(f"Error: {e}")
        if 'response' in locals():
             print(f"Status: {response.status_code}")
             print(response.text[:200])

if __name__ == "__main__":
    inspect_header()
