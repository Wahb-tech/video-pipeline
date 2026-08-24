import csv
import os
import random
import requests
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from .config import CATEGORIES, DARK_QUERIES

UA = "ZoopLuxuryFactory/2.0"

STOCK_BLOCKED_CATEGORIES = {"watch", "cash"}

STRICT_TERMS = {
    "yacht": {"yacht", "superyacht", "marina"},
    "dubai": {"dubai", "burj", "emirates"},
    "supercar": {"supercar", "lamborghini", "ferrari", "mclaren", "porsche"},
    "private_jet": {"private-jet", "private jet", "business-jet", "aircraft", "jet"},
    "villa": {"mansion", "villa", "penthouse", "luxury-home", "luxury house"},
    "watch": {"watch", "rolex", "timepiece"},
    "cash": {"cash", "money", "dollar", "banknote"},
    "hotel": {"hotel", "suite", "lobby", "five-star", "five star"},
    "dark_feminine": {
        "woman", "women", "lady", "female", "black dress", "evening dress",
        "short dress", "bikini", "swimsuit"
    }
}

FORBIDDEN_TERMS = {
    "girl",
    "cosplay", "costume", "jester", "anime", "dj", "concert", "festival",
    "party", "dancing", "beach", "wedding", "abstract", "background",
    "texture", "close up", "close-up", "macro", "water", "fountain",
    "waterfall", "rain", "river", "stone", "rock", "nature", "forest",
    "flower", "smoke", "fire", "light leak", "bokeh", "3d", "cgi",
    "render", "animation", "animated", "game", "gaming", "metaverse",
    "digital art", "illustration", "cartoon", "ai generated", "generated ai",
    "futuristic", "concept car", "cyberpunk", "simulation", "virtual"
}

WEALTH_TERMS = {
    "luxury", "luxurious", "wealth", "rich", "exclusive", "premium",
    "supercar", "lamborghini", "ferrari", "mclaren", "porsche", "rolls royce",
    "private jet", "business jet", "superyacht", "yacht", "rolex", "diamond",
    "jewelry", "mansion", "penthouse", "five star", "hotel suite", "cash",
    "money", "banknote", "dubai", "burj"
}

FEMININE_LUXURY_TERMS = {
    "luxury", "supercar", "lamborghini", "ferrari", "private jet", "aircraft",
    "penthouse", "mansion", "villa", "five star", "hotel", "jewelry", "diamond",
    "black dress", "evening dress", "short dress", "rooftop", "yacht",
    "marina", "infinity pool", "pool night"
}


def pexels_search(query, per_page=12):
    key = os.getenv("PEXELS_API_KEY", "").strip()
    if not key:
        return []
    r = requests.get(
        "https://api.pexels.com/v1/videos/search",
        headers={"Authorization": key, "User-Agent": UA},
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for video in r.json().get("videos", []):
        files = sorted(video.get("video_files", []), key=lambda x: (x.get("height", 0), x.get("width", 0)), reverse=True)
        files = [f for f in files if f.get("link") and f.get("file_type") == "video/mp4"]
        if not files:
            continue
        portrait = [f for f in files if (f.get("height") or 0) >= (f.get("width") or 0)]
        f = (portrait or files)[0]
        user = video.get("user") or {}
        out.append({
            "provider": "pexels",
            "id": str(video.get("id")),
            "url": f["link"],
            "width": f.get("width", 0),
            "height": f.get("height", 0),
            "duration": float(video.get("duration") or 0),
            "page_url": video.get("url", ""),
            "author": user.get("name", ""),
            "author_url": user.get("url", ""),
            "license_reference": "https://www.pexels.com/license/"
        })
    return out


@lru_cache(maxsize=128)
def coverr_search(query, per_page=20):
    key = os.getenv("COVERR_API_KEY", "").strip()
    if not key:
        return []
    r = requests.get(
        "https://api.coverr.co/videos",
        headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
        params={
            "query": query,
            "page_size": per_page,
            "sort": "popular",
            "urls": "true",
        },
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for video in r.json().get("hits", []):
        urls = video.get("urls") or {}
        url = urls.get("mp4_download") or urls.get("mp4")
        if not url:
            continue
        tags = video.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        metadata = " ".join([
            str(video.get("title") or ""),
            str(video.get("description") or ""),
            " ".join(str(tag) for tag in tags),
        ]).strip()
        out.append({
            "provider": "coverr",
            "id": str(video.get("id")),
            "url": url,
            "width": int(video.get("max_width") or 0),
            "height": int(video.get("max_height") or 0),
            "duration": float(video.get("duration") or 0),
            "page_url": f'https://coverr.co/videos/{video.get("id")}',
            "author": "Coverr",
            "author_url": "https://coverr.co",
            "license_reference": "https://coverr.co/license",
            "tags": metadata,
        })
    return out


def pixabay_search(query, per_page=20):
    key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not key:
        return []
    r = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": key, "q": query, "per_page": per_page, "safesearch": "true", "order": "popular"},
        headers={"User-Agent": UA},
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for hit in r.json().get("hits", []):
        videos = hit.get("videos", {})
        candidates = [videos.get(k) for k in ("large", "medium", "small", "tiny") if videos.get(k)]
        candidates = [v for v in candidates if v.get("url")]
        if not candidates:
            continue
        f = max(candidates, key=lambda x: x.get("height", 0) * x.get("width", 0))
        out.append({
            "provider": "pixabay",
            "id": str(hit.get("id")),
            "url": f["url"],
            "width": f.get("width", 0),
            "height": f.get("height", 0),
            "duration": float(hit.get("duration") or 0),
            "page_url": hit.get("pageURL", ""),
            "author": hit.get("user", ""),
            "author_url": "",
            "license_reference": "https://pixabay.com/service/license-summary/",
            "tags": hit.get("tags", "")
        })
    return out


def score(item, usage=None, provider_usage=None):
    s = 0
    w, h = item.get("width", 0), item.get("height", 0)
    if h > w:
        s += 6
    if h >= 1080:
        s += 2
    if item.get("duration", 0) >= 5:
        s += 2
    usage = usage or {}
    reuse_penalty = min(6.0, float(usage.get("count", 0)) * 0.8)
    provider_usage = provider_usage or {}
    counts = list(provider_usage.values()) or [0]
    provider_penalty = min(
        3.0,
        max(0, provider_usage.get(item.get("provider", ""), 0) - min(counts)) * 0.08,
    )
    return s - reuse_penalty - provider_penalty + random.random() * 2


def is_strict_dark_luxury(item, category):
    text = " ".join([
        str(item.get("page_url", "")),
        str(item.get("tags", "")),
    ]).lower().replace("_", " ")
    if any(term in text for term in FORBIDDEN_TERMS):
        return False
    if category == "dark_feminine":
        has_woman = any(term in text for term in STRICT_TERMS["dark_feminine"])
        has_luxury = any(term in text for term in FEMININE_LUXURY_TERMS)
        return has_woman and has_luxury
    has_category = any(term in text for term in STRICT_TERMS.get(category, set()))
    has_wealth = any(term in text for term in WEALTH_TERMS)
    return has_category and has_wealth


def is_real_footage(item):
    text = " ".join([
        str(item.get("page_url", "")),
        str(item.get("tags", "")),
    ]).lower().replace("_", " ")
    synthetic = {
        "3d", "cgi", "render", "animation", "animated", "game", "gaming",
        "metaverse", "digital art", "illustration", "cartoon", "ai generated",
        "futuristic", "concept car", "cyberpunk", "simulation", "virtual"
    }
    return not any(term in text for term in synthetic)


def is_safe_dark_luxury(item):
    text = " ".join([
        str(item.get("page_url", "")),
        str(item.get("tags", "")),
    ]).lower().replace("_", " ")
    return not any(term in text for term in FORBIDDEN_TERMS)


def find_clip(category, usage_history, style="mixed", exclude_ids=None):
    if style == "dark_luxury" and category in STOCK_BLOCKED_CATEGORIES:
        raise RuntimeError(f"Stock category permanently blocked for dark luxury: {category}")
    query_map = DARK_QUERIES if style == "dark_luxury" else CATEGORIES
    queries = query_map[category][:]
    random.shuffle(queries)
    pool = []
    for query in queries:
        try:
            items = pexels_search(query)
            for item in items:
                item["search_query"] = query
            pool.extend(items)
        except Exception as e:
            print(f"Pexels search failed for {query}: {e}")
        try:
            items = pixabay_search(query)
            for item in items:
                item["search_query"] = query
            pool.extend(items)
        except Exception as e:
            print(f"Pixabay search failed for {query}: {e}")
        try:
            items = coverr_search(query)
            for item in items:
                item["search_query"] = query
            pool.extend(items)
        except Exception as e:
            print(f"Coverr search failed for {query}: {e}")
    unique = {}
    for item in pool:
        unique[f'{item["provider"]}:{item["id"]}'] = item
    pool = list(unique.values())
    exclude_ids = exclude_ids or set()
    banned_ids = {
        value.strip() for value in os.getenv("BANNED_STOCK_IDS", "").replace("\n", ",").split(",")
        if value.strip()
    }
    exclude_ids = set(exclude_ids) | banned_ids
    pool = [x for x in pool if f'{x["provider"]}:{x["id"]}' not in exclude_ids]
    if isinstance(usage_history, set):
        history = {key: {"count": 1, "starts": []} for key in usage_history}
    else:
        history = usage_history
    provider_usage = {}
    for key, entry in history.items():
        provider = key.split(":", 1)[0]
        provider_usage[provider] = provider_usage.get(provider, 0) + int(entry.get("count", 0))
    unused = [x for x in pool if f'{x["provider"]}:{x["id"]}' not in history]
    if style == "dark_luxury":
        candidates = [x for x in unused if is_real_footage(x) and is_strict_dark_luxury(x, category)]
    else:
        candidates = unused or pool
    if not candidates:
        raise RuntimeError(f"No stock video found for category: {category}")
    candidates.sort(
        key=lambda item: score(
            item,
            history.get(f'{item["provider"]}:{item["id"]}', {}),
            provider_usage,
        ),
        reverse=True,
    )
    chosen = random.choice(candidates[: min(6, len(candidates))])
    chosen["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    return chosen


def load_recent_used(path="data/used_stock.csv", limit=400):
    p = Path(path)
    if not p.exists():
        return set()
    with p.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[-limit:]
    return {f'{r["provider"]}:{r["stock_id"]}' for r in rows if r.get("provider") and r.get("stock_id")}


def load_usage_history(path="data/used_stock.csv", limit=1200):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    with p.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[-limit:]
    history = {}
    for row in rows:
        if not row.get("provider") or not row.get("stock_id"):
            continue
        key = f'{row["provider"]}:{row["stock_id"]}'
        entry = history.setdefault(key, {"count": 0, "starts": [], "positions": []})
        entry["count"] += 1
        try:
            entry["starts"].append(float(row["start_sec"]))
        except (KeyError, TypeError, ValueError):
            pass
        try:
            entry["positions"].append(int(row["sequence_index"]))
        except (KeyError, TypeError, ValueError):
            pass
    return history


def append_used(items, experiment_id, path="data/used_stock.csv"):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = ["experiment_id", "provider", "stock_id", "category", "search_query", "page_url", "start_sec", "cut_seconds", "sequence_index", "used_at"]
    existing = []
    if p.exists() and p.stat().st_size > 0:
        with p.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing = list(reader)
            old_fields = reader.fieldnames or []
        if old_fields != fields:
            with p.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for old in existing:
                    writer.writerow({key: old.get(key, "") for key in fields})
    exists = p.exists() and p.stat().st_size > 0
    with p.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        for item in items:
            writer.writerow({
                "experiment_id": experiment_id,
                "provider": item.get("provider", ""),
                "stock_id": item.get("id", ""),
                "category": item.get("category", ""),
                "search_query": item.get("search_query", ""),
                "page_url": item.get("page_url", ""),
                "start_sec": item.get("start_sec", ""),
                "cut_seconds": item.get("cut_seconds", ""),
                "sequence_index": item.get("sequence_index", ""),
                "used_at": datetime.now(timezone.utc).isoformat()
            })


def download(url, destination):
    destination = Path(destination)
    local = Path(str(url))
    if local.exists():
        destination.write_bytes(local.read_bytes())
        return
    with requests.get(url, stream=True, timeout=120, headers={"User-Agent": UA}) as r:
        r.raise_for_status()
        with destination.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
