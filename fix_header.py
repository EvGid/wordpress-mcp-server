import requests
import json
import sys
import os

sys.path.append(os.getcwd())
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

from mcp_sse_server import WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD

def fix_header():
    auth = (WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
    part_id = "twentytwentyfive//header"
    url = f"{WORDPRESS_URL}/wp-json/wp/v2/template-parts/{part_id}?context=edit"
    
    try:
        # 1. Get current content
        print("Fetching header...")
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        current_raw = data['content']['raw']
        
        # 2. Prepare modification
        # Target: "layout":{"type":"flex","setCascadingProperties":true,"justifyContent":"right"}
        # Replacement: "layout":{"type":"flex","setCascadingProperties":true,"justifyContent":"right","flexWrap":"nowrap"}
        
        # We'll use string replacement to be safe with surrounding usage
        target_str = '"justifyContent":"right"}}'
        full_replacement = '"justifyContent":"right","flexWrap":"nowrap"}}'
        
        if target_str in current_raw:
            new_raw = current_raw.replace(target_str, full_replacement)
            print("Applying fix...")
        else:
            print("Could not find exact target string. Checking if already fixed...")
            if '"flexWrap":"nowrap"' in current_raw:
                print("Already fixed!")
                return
            print("Target string not found in raw content.")
            print(current_raw)
            return

        # 3. Save back
        save_url = f"{WORDPRESS_URL}/wp-json/wp/v2/template-parts/{part_id}"
        payload = {
            "content": new_raw
        }
        
        print("Saving changes...")
        save_response = requests.post(save_url, auth=auth, json=payload)
        save_response.raise_for_status()
        
        print("✅ Header updated successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        if 'save_response' in locals():
             print(f"Status: {save_response.status_code}")
             print(save_response.text[:200])

if __name__ == "__main__":
    fix_header()
