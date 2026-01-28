import asyncio
import json
import logging
import os
import sqlite3
import time
from typing import List, Dict, Any, Optional
import httpx

# Logger
logger = logging.getLogger(__name__)

# ==================== CACHE ====================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wordstat_cache.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS wordstat_cache
                 (query TEXT PRIMARY KEY, region_id INT, data TEXT, timestamp REAL)''')
    conn.commit()
    conn.close()

init_db()

def get_cached(query: str, region_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Simple cache expiration: 30 days
        cutoff = time.time() - (30 * 24 * 3600)
        c.execute("SELECT data FROM wordstat_cache WHERE query=? AND region_id=? AND timestamp > ?", (query, region_id, cutoff))
        row = c.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception as e:
        logger.error(f"Cache read error: {e}")
    return None

def set_cached(query: str, region_id: int, data: Any):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO wordstat_cache VALUES (?, ?, ?, ?)", 
                  (query, region_id, json.dumps(data), time.time()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Cache write error: {e}")

# ==================== WORDSTAT API (MOCK/REAL) ====================
# Note: Real Wordstat API v4 requires complex REPORT building.
# For this implementation phase, we will implement the client structure.
# Since we don't have the keys yet (User has them), we expect env vars.

# ==================== WORDSTAT API (REAL via topRequests) ====================
# Uses endpoint: https://api.wordstat.yandex.net/v1/topRequests
import asyncio as _asyncio
import ssl as _ssl
import urllib.request as _ur
import urllib.error as _ue
import re as _re

_WORDSTAT_BASE = "https://api.wordstat.yandex.net/v1/"

def _ws_call_api(endpoint: str, payload: dict) -> dict:
    token = (os.environ.get("WORDSTAT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("WORDSTAT_TOKEN not found in env")

    url = f"{_WORDSTAT_BASE}{endpoint}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = _ur.Request(url, data=data, method="POST")
    req.add_header("Content-type", "application/json;charset=utf-8")
    req.add_header("Authorization", f"Bearer {token}")

    ctx = _ssl.create_default_context()
    with _ur.urlopen(req, timeout=25, context=ctx) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))

def _ws_call_top_requests(phrase: str, region_id: int = 225, devices=None) -> dict:
    payload = {"phrase": phrase, "regions": [int(region_id)], "devices": devices or ["all"]}
    return _ws_call_api("topRequests", payload)

def _ws_dedupe_sort(items):
    seen = set()
    out = []
    # сортируем по shows/count по убыванию
    items2 = sorted(items, key=lambda x: int(x.get("shows") or x.get("count") or 0), reverse=True)
    for it in items2:
        phr = it.get("phrase")
        if not phr:
            continue
        key = _ws_norm(phr)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"phrase": phr, "shows": int(it.get("shows") or it.get("count") or 0)})
    return out

async def wordstat_auth_status() -> str:
    """Check Wordstat API connection status"""
    token = (os.environ.get("WORDSTAT_TOKEN") or "").strip()
    if not token:
        return json.dumps({"success": False, "message": "WORDSTAT_TOKEN not found in env"}, ensure_ascii=False)

    try:
        data = await _asyncio.to_thread(_ws_call_top_requests, "тур по горному алтаю", 225, ["all"])
        top = data.get("topRequests") or []
        return json.dumps({
            "success": True,
            "message": "Wordstat OK",
            "totalCount": int(data.get("totalCount") or 0),
            "sample": top[:10],
            "source": "yandex_wordstat_topRequests"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": f"Wordstat error: {e}", "source": "yandex_wordstat_topRequests"}, ensure_ascii=False)

async def wordstat_suggest(seed_keywords: List[str], region_id: int = 225, limit: int = 50) -> str:
    """Get suggestions based on Wordstat topRequests + associations"""
    suggestions = []

    for seed in (seed_keywords or []):
        seed = (seed or "").strip()
        if not seed:
            continue

        cached = get_cached(seed, region_id)
        if cached:
            suggestions.extend(cached)
            continue

        try:
            data = await _asyncio.to_thread(_ws_call_top_requests, seed, region_id, ["all"])
            top = [{"phrase": x.get("phrase"), "shows": int(x.get("count") or 0)} for x in (data.get("topRequests") or [])]
            assoc = [{"phrase": x.get("phrase"), "shows": int(x.get("count") or 0)} for x in (data.get("associations") or [])]

            merged = _ws_dedupe_sort(top + assoc)
            set_cached(seed, region_id, merged)
            suggestions.extend(merged)
        except Exception as e:
            logger.error(f"Wordstat suggest error for '{seed}': {e}")

    suggestions = _ws_dedupe_sort(suggestions)[:int(limit)]
    return json.dumps({
        "success": True,
        "suggestions": suggestions,
        "region_id": int(region_id),
        "source": "yandex_wordstat_topRequests"
    }, ensure_ascii=False)

async def wordstat_related(query: str, region_id: int = 225, limit: int = 50) -> str:
    """Get related phrases (kept compatible: returns suggestions list)"""
    return await wordstat_suggest([query], region_id, limit)

async def wordstat_stats(queries: List[str], region_id: int = 225, period: str = "last_month") -> str:
    """Get stats for queries (period kept for compatibility, Wordstat topRequests returns current counts)"""
    out = {}
    for q in (queries or []):
        q = (q or "").strip()
        if not q:
            continue
        try:
            data = await _asyncio.to_thread(_ws_call_top_requests, q, region_id, ["all"])
            total = int(data.get("totalCount") or 0)
            exact = 0
            for x in (data.get("topRequests") or []):
                if _ws_norm(x.get("phrase")) == _ws_norm(q):
                    exact = int(x.get("count") or 0)
                    break
            out[q] = {"totalCount": total, "exactCount": exact}
        except Exception as e:
            out[q] = {"error": str(e)}

    return json.dumps({
        "success": True,
        "stats": out,
        "region_id": int(region_id),
        "period": period,
        "source": "yandex_wordstat_topRequests"
    }, ensure_ascii=False)

async def wordstat_get_top_requests(phrase: str, region_id: int = 225) -> str:
    """Get raw topRequests data from Wordstat"""
    try:
        data = await _asyncio.to_thread(_ws_call_top_requests, phrase, region_id, ["all"])
        return json.dumps({
            "success": True,
            "data": data,
            "phrase": phrase,
            "region_id": int(region_id),
            "source": "yandex_wordstat_topRequests"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

async def wordstat_get_dynamics(phrase: str, region_id: int = 225) -> str:
    """Get dynamics of requests for a phrase"""
    try:
        data = await _asyncio.to_thread(_ws_call_api, "getDynamics", {"phrase": phrase, "regions": [int(region_id)]})
        return json.dumps({"success": True, "data": data}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

async def wordstat_get_regions(phrase: str) -> str:
    """Get statistics by regions"""
    try:
        data = await _asyncio.to_thread(_ws_call_api, "getRegions", {"phrase": phrase})
        return json.dumps({"success": True, "data": data}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

async def wordstat_get_regions_tree() -> str:
    """Get Yandex.Wordstat regions tree"""
    try:
        data = await _asyncio.to_thread(_ws_call_api, "getRegionsTree", {})
        return json.dumps({"success": True, "data": data}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

async def wordstat_get_user_info() -> str:
    """Get Yandex.Wordstat account info"""
    try:
        data = await _asyncio.to_thread(_ws_call_api, "getUserInfo", {})
        return json.dumps({"success": True, "data": data}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

# ==================== SEMCORE & CONTENT ====================

async def semcore_build(topic_or_seeds: List[str], region_id: int = 225, negative_keywords: List[str] = None, min_freq: int = 0, max_freq: int = 1000000, limit: int = 100) -> str:
    """Build a semantic core from seeds"""
    # This would orchestrate wordstat calls
    raw = await wordstat_suggest(topic_or_seeds, region_id, limit * 2)
    data = json.loads(raw)
    items = data.get("suggestions", [])
    
    filtered = []
    for item in items:
        if item["shows"] < min_freq or item["shows"] > max_freq:
            continue
        if negative_keywords:
            if any(neg in item["phrase"] for neg in negative_keywords):
                continue
        filtered.append(item)
        
    return json.dumps({"success": True, "semcore": filtered[:limit]})

async def semcore_cluster(phrases_with_stats: List[Dict], method: str = "intent", max_cluster_size: int = 10) -> str:
    """Cluster phrases using basic heuristic"""
    # Simple word overlap clustering
    clusters = {}
    
    for p in phrases_with_stats:
        phrase = p["phrase"]
        words = phrase.split()
        # Find best cluster
        best_c = None
        best_overlap = 0
        
        for c_name, c_items in clusters.items():
            c_words = c_name.split()
            overlap = len(set(words) & set(c_words))
            if overlap > best_overlap:
                best_overlap = overlap
                best_c = c_name
        
        if best_c and best_overlap >= 1: # at least 1 word overlap
            clusters[best_c].append(p)
        else:
            clusters[phrase] = [p] # Start new cluster
            
    # Format
    result = []
    for name, items in clusters.items():
        result.append({"name": name, "items": items, "vol": sum(x["shows"] for x in items)})
        
    return json.dumps({"success": True, "clusters": result})


async def content_plan_generate(clusters: List[Dict], business_type: str, goals: str, tone: str) -> str:
    """Generate a structure for content plan (logic/template)"""
    plan = []
    for c in clusters:
        plan.append({
            "topic": c["name"],
            "keywords": [x["phrase"] for x in c["items"]],
            "intent": "informational", # mock
            "format": "blog_post"
        })
    return json.dumps({"success": True, "plan_structure": plan})

async def seo_article_generate(cluster: Dict, primary_keyword: str, secondary_keywords: List[str], audience: str, tone: str, length: str, structure_rules: str) -> str:
    """Generate article structure/prompt for ChatGPT"""
    # Return a prompt that the User (ChatGPT) can use effectively, or a template.
    structure = {
        "h1": f"{primary_keyword} - Complete Guide",
        "intro": f"Covering {', '.join(secondary_keywords[:3])}",
        "sections": [
            {"h2": f"What is {primary_keyword}?", "content_focus": "Definition"},
            {"h2": "Benefits", "content_focus": "Why it matters"}
        ]
    }
    return json.dumps({"success": True, "structure_proposal": structure})

async def social_posts_generate(topic: str, keywords: List[str], platforms: List[str], style: str, length: str, cta: str, hashtags: List[str] = None) -> str:
    """Generate draft social posts"""
    result = {}
    for p in platforms:
        result[p] = f"Draft {p} post about {topic}. Keywords: {keywords}. Style: {style}"
    return json.dumps({"success": True, "drafts": result})


# ==================== SOCIAL PUBLISHING ====================

async def tg_post(text: str, images: List[str] = None, buttons: List[Dict] = None, parse_mode: str = "HTML") -> str:
    """Publish to Telegram"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    target = os.environ.get("TELEGRAM_TARGET")
    if not token or not target:
        return json.dumps({"success": False, "message": "NO TELEGRAM CREDENTIALS"})
        
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": target,
                "text": text,
                "parse_mode": parse_mode
            }
            resp = await client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            return json.dumps({"success": True, "telegram_response": resp.json()})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

async def vk_post(text: str, attachments: List[str] = None, links: str = None, from_group: bool = True) -> str:
    """Publish to VK"""
    token = os.environ.get("VK_ACCESS_TOKEN")
    group_id = os.environ.get("VK_GROUP_ID") # e.g. -123456 (negative for group) or positive ID and explicit owner_id
    
    if not token or not group_id:
        return json.dumps({"success": False, "message": "NO VK CREDENTIALS"})
        
    try:
        # Normalize group_id (must be negative for community wall post if passed as owner_id)
        # Or usually owner_id=-GROUP_ID
        owner_id = int(group_id)
        if owner_id > 0 and from_group:
            owner_id = -owner_id
            
        async with httpx.AsyncClient() as client:
            url = "https://api.vk.com/method/wall.post"
            params = {
                "access_token": token,
                "v": "5.131",
                "owner_id": owner_id,
                "message": text,
                "from_group": 1 if from_group else 0
            }
            if attachments:
                params["attachments"] = ",".join(attachments)
                
            resp = await client.post(url, data=params, timeout=10.0)
            resp.raise_for_status()
            return json.dumps({"success": True, "vk_response": resp.json()})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

async def publish_bundle(content: Dict[str, Any], seo_meta: Dict = None, targets: List[str] = None, dry_run: bool = False) -> str:
    """Publish to multiple targets (WP, TG, VK)"""
    if targets is None:
        targets = ["wp", "tg", "vk"]
        
    results = {}
    
    if dry_run:
        return json.dumps({"success": True, "message": "Dry Run", "targets": targets})
        
    # WP
    if "wp" in targets:
        # This would call the create_post logic. 
        # Since we are inside the server, we could call create_post DIRECTLY?
        # But this function is inside `content_automation_tools`.
        # To reuse create_post, we need it passed or imported.
        # For now, we return a "WP Pending" status or rely on the caller to call `create_post`.
        # User prompt implies "pipeline... Publish Bundle".
        # Let's assume content includes: {"title":..., "html":...}
        results["wp"] = "Skipped (Call create_post separately or implement internal call)"  

    # TG
    if "tg" in targets and "tg_text" in content:
        results["tg"] = await tg_post(content["tg_text"])
        
    # VK
    if "vk" in targets and "vk_text" in content:
        results["vk"] = await vk_post(content["vk_text"])
        
    return json.dumps({"success": True, "results": results})
