import csv
import os
import random
import requests
from datetime import datetime, timezone
from pathlib import Path
from .config import CATEGORIES, DARK_QUERIES

UA = "ZoopLuxuryFactory/2.0"

STRICT_TERMS = {
    "yacht": {"yacht", "superyacht", "marina"},
    "dubai": {"dubai", "burj", "emirates"},
    "supercar": {"supercar", "lamborghini", "ferrari", "mclaren", "porsche"},
    "private_jet": {"private-jet", "private jet", "business-jet", "aircraft", "jet"},
    "villa": {"mansion", "villa", "penthouse", "luxury-home", "luxury house"},
    "watch": {"watch", "rolex", "timepiece"},
    "cash": {"cash", "money", "dollar", "banknote"},
    "hotel": {"hotel", "suite", "lobby", "five-star", "five star"}
}

FORBIDDEN_TERMS = {
    "bikini", "swimsuit", "girl", "woman", "women", "model", "fashion",
    "cosplay", "costume", "jester", "anime", "dj", "concert", "festival",
    "party", "dancing", "beach", "wedding", "portrait"
}


def pexels_search(query, per_page=12):
    key = os.getenv("PEXELS_API_KEY", "").strip()
    if not key:
        return []
    r = requests.get(
        "https://api.pexels.com/videos/search",
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


def score(item):
    s = 0
    w, h = item.get("width", 0), item.get("height", 0)
    if h > w:
        s += 6
    if h >= 1080:
        s += 2
    if item.get("duration", 0) >= 5:
        s += 2
    return s + random.random() * 2


def is_strict_dark_luxury(item, category):
    text = " ".join([
        str(item.get("page_url", "")),
        str(item.get("tags", "")),
    ]).lower().replace("_", " ")
    if any(term in text for term in FORBIDDEN_TERMS):
        return False
    return any(term in text for term in STRICT_TERMS.get(category, set()))


def is_safe_dark_luxury(item):
    text = " ".join([
        str(item.get("page_url", "")),
        str(item.get("tags", "")),
    ]).lower().replace("_", " ")
    return not any(term in text for term in FORBIDDEN_TERMS)


def find_clip(category, used_ids, style="mixed"):
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
    unique = {}
    for item in pool:
        unique[f'{item["provider"]}:{item["id"]}'] = item
    pool = list(unique.values())
    unused = [x for x in pool if f'{x["provider"]}:{x["id"]}' not in used_ids]
    if style == "dark_luxury":
        candidates = [x for x in unused if is_strict_dark_luxury(x, category)]
        fallback_reason = ""
        if not candidates:
            candidates = [x for x in pool if is_strict_dark_luxury(x, category)]
            fallback_reason = "reusing strict stock"
        if not candidates:
            candidates = [x for x in unused if is_safe_dark_luxury(x)]
            fallback_reason = "using safe query-matched stock"
        if not candidates:
            candidates = [x for x in pool if is_safe_dark_luxury(x)]
            fallback_reason = "reusing safe query-matched stock"
        if fallback_reason:
            print(f"Stock fallback for {category}: {fallback_reason}")
    else:
        candidates = unused or pool
    if not candidates:
        raise RuntimeError(f"No stock video found for category: {category}")
    candidates.sort(key=score, reverse=True)
    chosen = random.choice(candidates[: min(8, len(candidates))])
    chosen["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    return chosen


def load_recent_used(path="data/used_stock.csv", limit=400):
    p = Path(path)
    if not p.exists():
        return set()
    with p.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[-limit:]
    return {f'{r["provider"]}:{r["stock_id"]}' for r in rows if r.get("provider") and r.get("stock_id")}


def append_used(items, experiment_id, path="data/used_stock.csv"):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    exists = p.exists() and p.stat().st_size > 0
    fields = ["experiment_id", "provider", "stock_id", "category", "search_query", "page_url", "used_at"]
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
                "used_at": datetime.now(timezone.utc).isoformat()
            })


def download(url, destination):
    destination = Path(destination)
    with requests.get(url, stream=True, timeout=120, headers={"User-Agent": UA}) as r:
        r.raise_for_status()
        with destination.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
