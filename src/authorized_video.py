import json
import os
import random
import re
import subprocess
import atexit
import shutil
from pathlib import Path

import requests


def _split_urls(raw):
    return [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()]


def _creator_url(value):
    value = value.strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if value.lower().startswith("youtube:"):
        return f"https://www.youtube.com/@{value.split(':', 1)[1].lstrip('@')}/videos"
    if value.lower().startswith("instagram:"):
        value = value.split(":", 1)[1]
    return f"https://www.instagram.com/{value.lstrip('@')}/reels/"


def _is_instagram(url):
    return "instagram.com/" in url.lower()


def _instagram_username(url):
    if not _is_instagram(url):
        return ""
    first = url.split("instagram.com/", 1)[-1].split("?", 1)[0].strip("/").split("/", 1)[0]
    return "" if first.lower() in {"reel", "p", "tv"} else first


def _is_direct_instagram_media(url):
    path = url.lower().split("instagram.com/", 1)[-1].split("?", 1)[0].strip("/")
    parts = path.split("/")
    return (
        len(parts) >= 2 and parts[0] in {"reel", "p", "tv"}
    ) or (
        len(parts) >= 3 and parts[1] in {"reel", "p", "tv"}
    )


def _media_files(group):
    extensions = {".mp4", ".mov", ".mkv", ".webm"}
    return [path for path in group.rglob("*") if path.is_file() and path.suffix.lower() in extensions]


def _probe_media(path):
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,bit_rate:format=duration",
            "-of", "json", str(path),
        ], check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        stream = payload.get("streams", [{}])[0]
        rate = str(stream.get("avg_frame_rate") or "0/1")
        numerator, denominator = rate.split("/", 1)
        fps = float(numerator) / max(float(denominator), 1.0)
        return {
            "width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0),
            "fps": round(fps, 3),
            "bit_rate": int(stream.get("bit_rate") or 0),
            "duration": float(payload.get("format", {}).get("duration") or 0),
        }
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, json.JSONDecodeError):
        return {"width": 0, "height": 0, "fps": 0.0, "bit_rate": 0, "duration": 0.0}


def _normalized_source_url(url):
    value = str(url or "").split("?", 1)[0].rstrip("./")
    return f"{value}/" if value else ""


def _configured_restyle_urls():
    return {
        _normalized_source_url(url)
        for url in _split_urls(os.getenv("AUTHORIZED_RESTYLE_VIDEO_URLS", ""))
    }


def _source_for_group(group, sources):
    source_index = Path(group).name.split("_", 1)[-1]
    if source_index.isdigit() and int(source_index) < len(sources):
        return sources[int(source_index)][0]
    return ""


def _shot_ranges(cut_times, duration, minimum_seconds=0.70):
    points = [0.0]
    points.extend(
        sorted({float(value) for value in cut_times if 0.0 < float(value) < float(duration)})
    )
    points.append(float(duration))
    return [
        (round(start, 3), round(end - start, 3))
        for start, end in zip(points, points[1:])
        if end - start >= minimum_seconds
    ]


def _detect_shots(path, duration):
    threshold = float(os.getenv("AUTHORIZED_SCENE_THRESHOLD", "0.28"))
    minimum = float(os.getenv("AUTHORIZED_MIN_SHOT_SECONDS", "0.70"))
    try:
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-i", str(path), "-an",
            "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-",
        ], check=False, capture_output=True, text=True, timeout=180)
        cut_times = [
            float(value)
            for value in re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", result.stderr)
        ]
        return _shot_ranges(cut_times, duration, minimum)
    except (OSError, subprocess.SubprocessError, ValueError):
        return [(0.0, round(float(duration), 3))] if duration >= minimum else []


def _expand_restyle_shots(items):
    expanded = []
    for item in items:
        if not item.get("creator_restyle"):
            expanded.append(item)
            continue
        duration = float(item.get("duration") or 0)
        if duration <= 0:
            duration = _probe_media(item["local_path"])["duration"]
        shots = _detect_shots(item["local_path"], duration) if duration > 0 else []
        if not shots:
            expanded.append(item)
            continue
        for index, (start, shot_duration) in enumerate(shots):
            shot = item.copy()
            shot["source_media_id"] = item["id"]
            shot["id"] = f'{item["id"]}_shot_{index:02d}'
            shot["segment_start"] = start
            shot["segment_duration"] = shot_duration
            shot["duration"] = shot_duration
            shot["search_query"] = "authorized creator scene library"
            expanded.append(shot)
    return expanded


def _cookie_args():
    cookie_file = os.getenv("AUTHORIZED_COOKIES_FILE", "").strip()
    if not cookie_file:
        return []
    path = Path(cookie_file)
    if not path.is_file() or path.stat().st_size == 0:
        print(f"Authorized cookies file is missing or empty: {path}")
        return []
    return ["--cookies", str(path)]


def _download_instagram_instaloader(url, group, limit):
    username = _instagram_username(url)
    if not username:
        return False
    try:
        import instaloader

        class NoWaitRateController(instaloader.RateController):
            def handle_429(self, query_type):
                raise instaloader.ConnectionException(
                    f"Instagram rate limit reached for {query_type}"
                )

        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
            max_connection_attempts=1,
            rate_controller=lambda context: NoWaitRateController(context),
        )
        profile = instaloader.Profile.from_username(loader.context, username)
        maximum = int(limit) if str(limit).isdigit() else 12
        downloaded = 0
        for post in profile.get_posts():
            if not post.is_video:
                continue
            target = group / f"instagram_{post.shortcode}.mp4"
            response = requests.get(post.video_url, stream=True, timeout=60)
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
            downloaded += 1
            if maximum > 0 and downloaded >= maximum:
                break
        return downloaded > 0
    except Exception as exc:
        print(f"Instaloader unavailable for @{username}: {exc}")
        return False


def _download_instagram_gallery(url, group, limit):
    before = set(_media_files(group))
    result = subprocess.run([
        "gallery-dl", "--no-mtime", "--range", f"1-{limit}",
        "--filter", "extension in ('mp4', 'mov', 'mkv', 'webm')",
        "-D", str(group), "-f", "instagram_{shortcode}_{num}.{extension}",
        *_cookie_args(), url,
    ], check=False)
    return result.returncode == 0 and bool(set(_media_files(group)) - before)


def _download_with_ytdlp(url, group, limit):
    output = str(group / "%(extractor)s_%(id)s.%(ext)s")
    duration_filter = [] if _is_direct_instagram_media(url) else [
        "--match-filter", "duration >= 8 & duration <= 1800",
    ]
    result = subprocess.run([
        "yt-dlp", "--no-warnings", "--ignore-errors",
        "--playlist-end", limit,
        *duration_filter,
        "--write-info-json", "--merge-output-format", "mp4",
        "-f", "bv*+ba/b",
        "-S", "res,fps,br",
        "-o", output, *_cookie_args(), url,
    ], check=False)
    return result.returncode == 0 and bool(_media_files(group))


def configured_sources():
    sources = []
    for url in _split_urls(os.getenv("AUTHORIZED_VIDEO_URLS", "")):
        sources.append((url, False))
    for url in _split_urls(os.getenv("AUTHORIZED_TEXT_VIDEO_URLS", "")):
        sources.append((url, True))
    for url in _split_urls(os.getenv("AUTHORIZED_RESTYLE_VIDEO_URLS", "")):
        sources.append((_normalized_source_url(url), False))
    for handle in _split_urls(os.getenv("AUTHORIZED_CREATOR_HANDLES", "")):
        sources.append((_creator_url(handle), False))
    for handle in _split_urls(os.getenv("AUTHORIZED_TEXT_CREATOR_HANDLES", "")):
        sources.append((_creator_url(handle), True))
    return list(dict.fromkeys(source for source in sources if source[0]))


def configured_urls():
    return [url for url, _ in configured_sources()]


def authorized_quality_penalty(item):
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    short_edge = min(width, height) if width and height else 0
    if short_edge >= 1000:
        penalty = 0
    elif short_edge >= 900:
        penalty = 4
    elif short_edge >= 700:
        penalty = 14
    elif short_edge >= 540:
        penalty = 24
    elif short_edge > 0:
        penalty = 36
    else:
        penalty = 18
    if width and height:
        if width > height:
            penalty += 20
        elif height / width < 1.5:
            penalty += 8
    bit_rate = int(item.get("bit_rate") or 0)
    if bit_rate and bit_rate < 1_500_000:
        penalty += 12
    elif bit_rate and bit_rate < 3_000_000:
        penalty += 5
    fps = float(item.get("fps") or 0)
    if fps and fps < 24.5:
        penalty += 5
    return penalty


def download_authorized_library(destination):
    sources = configured_sources()
    if not sources:
        return []
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    atexit.register(shutil.rmtree, destination, ignore_errors=True)
    for index, (url, cleanup_text) in enumerate(sources):
        group = destination / (f"text_{index}" if cleanup_text else f"clean_{index}")
        group.mkdir(exist_ok=True)
        limit = os.getenv("AUTHORIZED_PLAYLIST_LIMIT", "12")
        downloaded = False
        if _is_instagram(url) and not _is_direct_instagram_media(url):
            downloaded = _download_instagram_instaloader(url, group, limit)
            if not downloaded:
                downloaded = _download_instagram_gallery(url, group, limit)
        if not downloaded:
            downloaded = _download_with_ytdlp(url, group, limit)
        if not downloaded:
            print(f"Authorized source unavailable, skipping: {url}")
    owner = os.getenv("AUTHORIZED_SOURCE_OWNER", "authorized creator").strip()
    restyle_owner = os.getenv("AUTHORIZED_RESTYLE_SOURCE_OWNER", "@stevenishh").strip()
    restyle_urls = _configured_restyle_urls()
    items = []
    for info_path in destination.glob("**/*.info.json"):
        info = json.loads(info_path.read_text(encoding="utf-8"))
        video_id = str(info.get("id") or info_path.stem)
        matches = list(info_path.parent.glob(f"*_{video_id}.*"))
        video = next((p for p in matches if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}), None)
        if not video:
            continue
        configured_url = _source_for_group(info_path.parent, sources)
        page_url = info.get("webpage_url") or info.get("original_url") or configured_url
        is_restyle = _normalized_source_url(configured_url or page_url) in restyle_urls
        author = info.get("uploader") or _instagram_username(configured_url) or (restyle_owner if is_restyle else owner)
        media = _probe_media(video)
        items.append({
            "provider": "authorized_creator",
            "id": video_id,
            "local_path": str(video),
            "page_url": page_url,
            "author": author,
            "author_url": info.get("channel_url") or configured_url,
            "license_reference": f"Direct permission from {author}",
            "duration": float(info.get("duration") or 0),
            "width": media["width"] or int(info.get("width") or 0),
            "height": media["height"] or int(info.get("height") or 0),
            "fps": media["fps"] or float(info.get("fps") or 0),
            "bit_rate": media["bit_rate"] or int(float(info.get("tbr") or 0) * 1000),
            "tags": "authorized creator footage dark luxury wealth lifestyle",
            "search_query": "authorized creator library",
            "cleanup_text": info_path.parent.name.startswith("text_"),
            "creator_restyle": is_restyle,
        })
    indexed_paths = {Path(item["local_path"]).resolve() for item in items}
    for video in _media_files(destination):
        if video.resolve() in indexed_paths:
            continue
        cleanup_text = video.parent.name.startswith("text_")
        source_url = _source_for_group(video.parent, sources)
        is_restyle = _normalized_source_url(source_url) in restyle_urls
        author = _instagram_username(source_url) if _is_instagram(source_url) else ""
        author = author or (restyle_owner if is_restyle else owner)
        media = _probe_media(video)
        items.append({
            "provider": "authorized_creator",
            "id": video.stem,
            "local_path": str(video),
            "page_url": source_url,
            "author": author or owner,
            "author_url": source_url,
            "license_reference": f"Direct permission from {author or owner}",
            "duration": media["duration"],
            "width": media["width"],
            "height": media["height"],
            "fps": media["fps"],
            "bit_rate": media["bit_rate"],
            "tags": "authorized creator footage dark luxury wealth lifestyle",
            "search_query": "authorized creator library",
            "cleanup_text": cleanup_text,
            "creator_restyle": is_restyle,
        })
    return _expand_restyle_shots(items)


def choose_authorized_clip(items, usage_history, run_counts, position, excluded_ids=(), minimum_duration=0):
    available = [
        item for item in items
        if f'{item["provider"]}:{item["id"]}' not in excluded_ids
        and f'{item["provider"]}:{item.get("source_media_id", item["id"])}' not in excluded_ids
        and (
            not float(item.get("segment_duration") or item.get("duration") or 0)
            or float(item.get("segment_duration") or item.get("duration") or 0) >= float(minimum_duration) + 0.05
        )
    ]
    if not available:
        return None
    def rank(item):
        key = f'{item["provider"]}:{item["id"]}'
        author_key = f'author:{item.get("author", "authorized creator").lower()}'
        past = usage_history.get(key, {})
        total_uses = int(past.get("count", 0)) + run_counts.get(key, 0)
        positions = past.get("positions", [])
        position_penalty = 2 if position in positions[-6:] else 0
        author_penalty = run_counts.get(author_key, 0) * 4
        return (
            total_uses * 3 + author_penalty + position_penalty
            + authorized_quality_penalty(item) + random.random()
        )
    return min(available, key=rank).copy()
