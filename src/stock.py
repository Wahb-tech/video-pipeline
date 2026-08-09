import os
import random
import requests
from pathlib import Path
from .config import CATEGORIES

UA = "ZoopLuxuryFactory/1.0"


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
        out.append({
            "provider": "pexels",
            "id": str(video.get("id")),
            "url": f["link"],
            "width": f.get("width", 0),
            "height": f.get("height", 0),
            "duration": float(video.get("duration") or 0),
            "page_url": video.get("url", ""),
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


def find_clip(category, used_ids):
    queries = CATEGORIES[category][:]
    random.shuffle(queries)
    pool = []
    for query in queries[:2]:
        try:
            pool.extend(pexels_search(query))
        except Exception as e:
            print(f"Pexels search failed for {query}: {e}")
        try:
            pool.extend(pixabay_search(query))
        except Exception as e:
            print(f"Pixabay search failed for {query}: {e}")
    pool = [x for x in pool if f'{x["provider"]}:{x["id"]}' not in used_ids]
    if not pool:
        raise RuntimeError(f"No stock video found for category: {category}")
    pool.sort(key=score, reverse=True)
    return random.choice(pool[: min(5, len(pool))])


def download(url, destination):
    destination = Path(destination)
    with requests.get(url, stream=True, timeout=120, headers={"User-Agent": UA}) as r:
        r.raise_for_status()
        with destination.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return destination
