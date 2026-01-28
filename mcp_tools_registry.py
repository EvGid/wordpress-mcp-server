import os
import json
import logging
import asyncio
import httpx
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional
from mcp.types import Tool, TextContent

# Configure logging
logger = logging.getLogger(__name__)

# ==================== WORDPRESS CLIENT ====================
class WordPressClient:
    """Async WordPress REST API client"""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(
            auth=(username, password),
            timeout=120.0,
            headers={"Content-Type": "application/json"},
            verify=False
        )
        logger.info(f"WordPressClient initialized for {self.base_url}")

    async def request(self, method: str, endpoint: str, **kwargs) -> Any:
        try:
            url = f"{self.base_url}/wp-json{endpoint}"
            # Ensure lead /
            if not endpoint.startswith('/'):
                url = f"{self.base_url}/wp-json/{endpoint}"
                
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.text else {}
        except Exception as e:
            logger.error(f"WP Request Error ({method} {endpoint}): {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                 logger.error(f"Response: {e.response.text[:500]}")
            raise

    async def close(self):
        await self.client.aclose()

# ==================== TOOLS REGISTRY ====================
class ToolsRegistry:
    def __init__(self):
        load_dotenv()  # Ensure environment variables are loaded
        self.clients = {}
        self.allowlist = set()
        self._load_allowlist()
        self._init_clients()
        
    def _load_allowlist(self):
        path = "/opt/wordpress-mcp-server/tools_allowlist.txt"
        if os.path.exists(path):
            with open(path, "r") as f:
                self.allowlist = {line.strip() for line in f if line.strip() and not line.startswith("#")}
        else:
            logger.warning(f"Allowlist not found at {path}")

    def _init_clients(self):
        # MAIN
        main_url = os.getenv("WORDPRESS_MAIN_URL") or os.getenv("WORDPRESS_URL")
        main_user = os.getenv("WORDPRESS_MAIN_USERNAME") or os.getenv("WORDPRESS_USERNAME")
        main_pass = os.getenv("WORDPRESS_MAIN_PASSWORD") or os.getenv("WORDPRESS_PASSWORD")
        
        if main_url and main_user and main_pass:
            self.clients["main"] = WordPressClient(main_url, main_user, main_pass)
            
        # BLOG
        blog_url = os.getenv("WORDPRESS_BLOG_URL")
        blog_user = os.getenv("WORDPRESS_BLOG_USERNAME") or main_user
        blog_pass = os.getenv("WORDPRESS_BLOG_PASSWORD") or main_pass
        
        if blog_url:
            self.clients["blog"] = WordPressClient(blog_url, blog_user, blog_pass)

    def get_client(self, site: str = "main") -> WordPressClient:
        client = self.clients.get(site)
        if not client:
            raise RuntimeError(f"WordPress client for site '{site}' not configured")
        return client

    async def close(self):
        for client in self.clients.values():
            await client.close()

    def get_tools_metadata(self) -> List[Tool]:
        """Returns list of Tool objects for allowlisted tools"""
        tools = []
        all_defs = self._get_all_definitions()
        
        for name in self.allowlist:
            if name in all_defs:
                spec = all_defs[name]
                tools.append(Tool(
                    name=name,
                    description=spec["description"],
                    inputSchema=spec["inputSchema"]
                ))
        return tools

    def _get_wp_schema_with_site(self, properties: dict, required: list = None):
        props = properties.copy()
        props["site"] = {
            "type": "string", 
            "enum": ["main", "blog"], 
            "default": "main", 
            "description": "Target WordPress site"
        }
        return {
            "type": "object",
            "properties": props,
            "required": required or []
        }

    def _get_all_definitions(self) -> Dict[str, Dict]:
        from tools_spec import TOOLS as WP_SPEC
        defs = {}
        
        # 1. Dynamic WordPress Tools from tools_spec.py
        for name, (method, path, mode) in WP_SPEC.items():
            props = {}
            # Detect path parameters like {id}, {taxonomy}, etc.
            import re
            params = re.findall(r'\{([a-zA-Z0-9_]+)\}', path)
            for p in params:
                 # Standard types for common params
                 if p in ["id", "post_id", "page_id", "media_id", "menu_id"]:
                     props[p] = {"type": "integer"}
                 else:
                     props[p] = {"type": "string"}
            
            # Add some common query params for GET
            if method == "GET":
                props.update({
                    "per_page": {"type": "integer", "default": 20},
                    "page": {"type": "integer", "default": 1}
                })
            
            # Special case for content creation/update (very basic schema)
            if method == "POST" and name.startswith(("create_", "update_")):
                props.update({
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "status": {"type": "string"}
                })

            defs[name] = {
                "description": f"WordPress {name} tool (Auto-generated from spec)",
                "inputSchema": self._get_wp_schema_with_site(props)
            }

        # 2. Advanced / Overridden WordPress Tools
        # Override some auto-generated ones with better schemas
        defs["get_site_info"] = {"description": "Get WordPress site information", "inputSchema": self._get_wp_schema_with_site({})}
        defs["get_posts"] = {"description": "Get list of WordPress posts", "inputSchema": self._get_wp_schema_with_site({"per_page": {"type": "integer", "default": 10}, "page": {"type": "integer", "default": 1}, "search": {"type": "string"}})}
        defs["get_post"] = {"description": "Get a single WordPress post by ID (id) or slug (slug)", "inputSchema": self._get_wp_schema_with_site({"id": {"type": "integer"}, "slug": {"type": "string"}})}
        
        # Add the new specific ones I added earlier
        defs["wordpress_bulk_update_posts"] = {"description": "Массовое обновление записей", "inputSchema": self._get_wp_schema_with_site({"post_ids": {"type": "array", "items": {"type": "integer"}}, "data": {"type": "object"}}, ["post_ids", "data"])}
        defs["wordpress_create_article"] = {"description": "Создание статьи (через кастомный тип)", "inputSchema": self._get_wp_schema_with_site({"title": {"type": "string"}, "content": {"type": "string"}, "post_type": {"type": "string", "default": "post"}, "status": {"type": "string", "default": "publish"}}, ["title", "content"])}
        defs["wordpress_set_featured_image"] = {"description": "Установка обложки (featured image) для записи", "inputSchema": self._get_wp_schema_with_site({"post_id": {"type": "integer"}, "media_id": {"type": "integer"}}, ["post_id", "media_id"])}
        defs["wordpress_search_posts"] = {"description": "Поиск записей (posts) в WordPress", "inputSchema": self._get_wp_schema_with_site({"query": {"type": "string"}}, ["query"])}
        defs["wordpress_search_pages"] = {"description": "Поиск страниц (pages) в WordPress", "inputSchema": self._get_wp_schema_with_site({"query": {"type": "string"}}, ["query"])}
        defs["wordpress_upload_image_from_url"] = {"description": "Загрузка картинки по прямой ссылке", "inputSchema": self._get_wp_schema_with_site({"url": {"type": "string"}, "title": {"type": "string"}, "alt_text": {"type": "string"}}, ["url"])}
        defs["wordpress_delete_comment"] = {"description": "Удаление комментария", "inputSchema": self._get_wp_schema_with_site({"id": {"type": "integer"}, "force": {"type": "boolean", "default": True}}, ["id"])}
        defs["wordpress_moderate_comment"] = {"description": "Модерация комментария", "inputSchema": self._get_wp_schema_with_site({"id": {"type": "integer"}, "status": {"type": "string", "enum": ["approve", "hold", "spam", "trash"]}}, ["id", "status"])}
        defs["wordpress_create_category"] = {"description": "Создание новой категории", "inputSchema": self._get_wp_schema_with_site({"name": {"type": "string"}}, ["name"])}
        defs["wordpress_create_tag"] = {"description": "Создание нового тега", "inputSchema": self._get_wp_schema_with_site({"name": {"type": "string"}}, ["name"])}
        
        # 3. Wordstat Tools
        defs["wordstat_auth_status"] = {"description": "Check Wordstat API connection status", "inputSchema": {"type": "object", "properties": {}}}
        defs["wordstat_suggest"] = {"description": "Get suggestions based on Wordstat", "inputSchema": {"type": "object", "properties": {"seed_keywords": {"type": "array", "items": {"type": "string"}}, "region_id": {"type": "integer", "default": 225}}, "required": ["seed_keywords"]}}
        defs["wordstat_related"] = {"description": "Get related phrases from Wordstat", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "region_id": {"type": "integer", "default": 225}}, "required": ["query"]}}
        defs["wordstat_stats"] = {"description": "Get stats for queries from Wordstat", "inputSchema": {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}}, "region_id": {"type": "integer", "default": 225}}, "required": ["queries"]}}
        defs["wordstat_get_top_requests"] = {"description": "Get raw topRequests data from Wordstat", "inputSchema": {"type": "object", "properties": {"phrase": {"type": "string"}, "region_id": {"type": "integer", "default": 225}}, "required": ["phrase"]}}
        defs["wordstat_get_dynamics"] = {"description": "Get dynamics of requests for a phrase", "inputSchema": {"type": "object", "properties": {"phrase": {"type": "string"}, "region_id": {"type": "integer", "default": 225}}, "required": ["phrase"]}}
        defs["wordstat_get_regions"] = {"description": "Get statistics by regions", "inputSchema": {"type": "object", "properties": {"phrase": {"type": "string"}}, "required": ["phrase"]}}
        defs["wordstat_get_regions_tree"] = {"description": "Get Yandex.Wordstat regions tree", "inputSchema": {"type": "object", "properties": {}}}
        defs["wordstat_get_user_info"] = {"description": "Get Yandex.Wordstat account info", "inputSchema": {"type": "object", "properties": {}}}
        
        # 4. Automation & Content
        defs["content_plan_generate"] = {"description": "Generate a structure for content plan", "inputSchema": {"type": "object", "properties": {"clusters": {"type": "array", "items": {"type": "object"}}, "business_type": {"type": "string"}, "goals": {"type": "string"}, "tone": {"type": "string"}}, "required": ["clusters", "business_type", "goals", "tone"]}}
        defs["seo_article_generate"] = {"description": "Generate article structure/prompt for ChatGPT", "inputSchema": {"type": "object", "properties": {"cluster": {"type": "object"}, "primary_keyword": {"type": "string"}, "secondary_keywords": {"type": "array", "items": {"type": "string"}}, "audience": {"type": "string"}, "tone": {"type": "string"}, "length": {"type": "string"}, "structure_rules": {"type": "string"}}, "required": ["cluster", "primary_keyword", "secondary_keywords", "audience", "tone", "length", "structure_rules"]}}
        
        defs["social_posts_generate"] = {
            "description": "Generate draft social posts",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "platforms": {"type": "array", "items": {"type": "string"}},
                    "style": {"type": "string"},
                    "length": {"type": "string"},
                    "cta": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["topic", "keywords", "platforms", "style", "length", "cta"]
            }
        }
        defs["tg_post"] = {"description": "Publish to Telegram", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}
        defs["vk_post"] = {"description": "Publish to VK", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}
        
        # 5. Misc & Utils
        defs["rest_call"] = {"description": "Universal WP REST API call", "inputSchema": self._get_wp_schema_with_site({"method": {"type": "string"}, "path": {"type": "string"}}, ["method", "path"])}
        defs["call_tool"] = defs["rest_call"]
        defs["execute_shell_command"] = {"description": "Execute shell command", "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}
        defs["emergency_sql_command"] = {"description": "Emergency SQL command", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}
        
        return defs

    async def dispatch(self, name: str, arguments: Dict) -> Any:
        import content_automation_tools
        site = arguments.pop("site", "main")
        
        # Wordstat Tools
        if name.startswith("wordstat_"):
            if name == "wordstat_auth_status": return await content_automation_tools.wordstat_auth_status()
            if name == "wordstat_get_regions_tree": return await content_automation_tools.wordstat_get_regions_tree()
            if name == "wordstat_get_user_info": return await content_automation_tools.wordstat_get_user_info()
            method = getattr(content_automation_tools, name)
            return await method(**arguments)
            
        # Optimization & Content
        if name in ["content_plan_generate", "seo_article_generate", "social_posts_generate", "tg_post", "vk_post"]:
            method = getattr(content_automation_tools, name)
            return await method(**arguments)
            
        # Emergency & Shell
        if name in ["execute_shell_command", "emergency_sql_command", "read_theme_file", "write_theme_file", "fix_theme_css"]:
            method = getattr(self, f"_{name}") if hasattr(self, f"_{name}") else getattr(self, name)
            return await method(**arguments)

        # WordPress Tools
        client = self.get_client(site)
        if name == "call_tool": return await self._dispatch_wp_tool(client, "rest_call", arguments)
        return await self._dispatch_wp_tool(client, name, arguments)

    async def _dispatch_wp_tool(self, client: WordPressClient, name: str, args: Dict) -> Any:
        from tools_spec import TOOLS as WP_SPEC
        
        if name in WP_SPEC:
            method, path_tmpl, mode = WP_SPEC[name]
            params, body = {}, {}
            path = path_tmpl
            for k in list(args.keys()):
                token = "{%s}" % k
                if token in path: path = path.replace(token, str(args.pop(k)))
            if method == "GET": params.update(args)
            else: body.update(args)
            if mode == "trash": params["force"] = False
            if mode == "delete": params["force"] = args.get("force", True)
            if mode == "publish": body["status"] = "publish"
            if mode == "schedule": body["status"] = "future"
            if mode == "site_info": return await client.request("GET", "/")
            return await client.request(method, path, params=params or None, json=body or None)

        # Custom logic
        if name == "rest_call":
             return await client.request(args["method"], args["path"], params=args.get("params"), json=args.get("json_body"))
        if name == "wordpress_search_posts":
            return await client.request("GET", "/wp/v2/search", params={"search": args["query"], "subtype": "post"})
        if name == "wordpress_search_pages":
            return await client.request("GET", "/wp/v2/search", params={"search": args["query"], "subtype": "page"})
        if name == "wordpress_bulk_update_posts":
            results = [await client.request("POST", f"/wp/v2/posts/{pid}", json=args["data"]) for pid in args["post_ids"]]
            return {"success": True, "updated": len(results)}
        if name == "wordpress_create_article":
            ptype = args.pop("post_type", "post")
            endpoint = "/wp/v2/posts" if ptype == "post" else f"/wp/v2/{ptype}"
            return await client.request("POST", endpoint, json=args)
        if name == "wordpress_set_featured_image":
            return await client.request("POST", f"/wp/v2/posts/{args['post_id']}", json={"featured_media": args['media_id']})
        if name == "wordpress_delete_comment":
            return await client.request("DELETE", f"/wp/v2/comments/{args['id']}", params={"force": args.get("force", True)})
        if name == "wordpress_moderate_comment":
            return await client.request("POST", f"/wp/v2/comments/{args['id']}", json={"status": args["status"]})
        if name == "wordpress_create_category":
            return await client.request("POST", "/wp/v2/categories", json={"name": args["name"]})
        if name == "wordpress_create_tag":
            return await client.request("POST", "/wp/v2/tags", json={"name": args["name"]})
        if name == "wordpress_upload_image_from_url":
            async with httpx.AsyncClient() as hclient:
                r = await hclient.get(args["url"])
                r.raise_for_status()
                raw = r.content
                filename = args["url"].split('/')[-1] or "image.jpg"
                files = {"file": (filename, raw)}
                data = {"title": args.get("title", filename), "alt_text": args.get("alt_text", "")}
                headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
                return await client.request("POST", "/wp/v2/media", files=files, data=data, headers=headers)
        if name == "upload_media":
            import base64
            filename = args["filename"]
            raw = base64.b64decode(args["file_b64"])
            files = {"file": (filename, raw)}
            data = {k: args[k] for k in ["title", "alt_text"] if k in args}
            headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
            return await client.request("POST", "/wp/v2/media", files=files, data=data, headers=headers)
        if name == "reorder_menu_items":
            results = [await client.request("POST", f"/wp/v2/menu-items/{iid}", json={"menu_order": i+1, "menus": args["menu_id"]}) for i, iid in enumerate(args["ordered_item_ids"])]
            return {"success": True, "updated": len(results)}

        raise ValueError(f"Custom logic for tool '{name}' not implemented")

    # PORTED
    async def _read_theme_file(self, filename: str) -> str:
        base_path = "/var/www/wordpress/wp-content/themes/twentytwentyfive-child/"
        full_path = os.path.normpath(os.path.join(base_path, filename))
        if not full_path.startswith(base_path): return "Error: Access denied"
        if not os.path.exists(full_path): return f"Error: File not found: {filename}"
        with open(full_path, "r", encoding="utf-8") as f: return f.read()

    async def _write_theme_file(self, filename: str, content: str) -> str:
        base_path = "/var/www/wordpress/wp-content/themes/twentytwentyfive-child/"
        full_path = os.path.normpath(os.path.join(base_path, filename))
        if not full_path.startswith(base_path): return "Error: Access denied"
        with open(full_path, "w", encoding="utf-8") as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {filename}"

    async def _fix_theme_css(self, css_to_append: str) -> str:
        path = "/var/www/wordpress/wp-content/themes/twentytwentyfive-child/style.css"
        with open(path, "a", encoding="utf-8") as f: f.write("\n\n/* MCP AUTO-FIX */\n" + css_to_append)
        return "Successfully updated style.css"

    async def _execute_shell_command(self, command: str) -> str:
        import subprocess
        try: return subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT)
        except Exception as e: return str(e)

    async def _emergency_sql_command(self, query: str) -> str:
        import subprocess
        wp_path = "/var/www/wordpress/"
        cmd = ["/usr/local/bin/wp", "db", "query", query, "--allow-root", f"--path={wp_path}"]
        try: return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        except Exception as e: return str(e)

    async def _emergency_write_file(self, path: str, content: str) -> str:
        try:
            with open(path, 'w', encoding='utf-8') as f: f.write(content)
            return f"OK: {path}"
        except Exception as e: return str(e)

registry = ToolsRegistry()
