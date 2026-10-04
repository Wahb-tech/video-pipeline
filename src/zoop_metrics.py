import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin


PUBLICATION_FIELDS = [
    "experiment_id", "post_id", "post_url", "caption", "scheduled_at",
    "published_at", "status", "created_at", "last_seen_at", "source_url",
]

METRIC_FIELDS = [
    "experiment_id", "published_at", "theme", "copy_variant", "caption_variant",
    "audio_id", "audio_start_sec", "audio_segment", "views", "likes", "comments",
    "shares", "follows", "completion_rate", "avg_watch_seconds", "post_url", "notes",
    "recorded_at", "measurement_window", "source",
]

SNAPSHOT_FIELDS = METRIC_FIELDS

ID_KEYS = ("post_id", "postId", "publication_id", "publicationId", "id")
URL_KEYS = ("post_url", "postUrl", "permalink", "share_url", "shareUrl", "url")
CAPTION_KEYS = ("caption", "message", "description", "body", "text", "content")
DATE_KEYS = ("published_at", "publishedAt", "created_at", "createdAt", "scheduled_at", "scheduledAt", "publish_at", "publishAt")
METRIC_ALIASES = {
    "views": ("views", "view_count", "views_count", "viewCount", "viewsCount", "play_count", "playCount", "plays", "reach"),
    "likes": ("likes", "like_count", "likes_count", "likeCount", "likesCount", "reactionsCount", "reactions_count"),
    "comments": ("comments", "comment_count", "comments_count", "commentCount", "commentsCount"),
    "shares": ("shares", "share_count", "shares_count", "shareCount", "sharesCount", "reposts", "repost_count"),
    "completion_rate": ("completion_rate", "completionRate", "watch_completion_rate", "watchCompletionRate"),
    "avg_watch_seconds": ("avg_watch_seconds", "avgWatchSeconds", "average_watch_time", "averageWatchTime"),
}
SENSITIVE_KEYS = {
    "access_token", "authorization", "date_of_birth", "dob", "email", "password",
    "phone", "phone_number", "refresh_token", "street_address", "token",
}


def utc_now():
    return datetime.now(timezone.utc)


def iso_datetime(value):
    if not value:
        return ""
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value /= 1000
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    text = str(value).strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return text


def parse_datetime(value):
    normalized = iso_datetime(value)
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def read_rows(path):
    target = Path(path)
    if not target.exists() or target.stat().st_size == 0:
        return []
    with target.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path, fields, rows):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def upsert_row(path, fields, row, key_fields):
    rows = read_rows(path)
    key = tuple(str(row.get(field, "")) for field in key_fields)
    replaced = False
    for index, current in enumerate(rows):
        if tuple(str(current.get(field, "")) for field in key_fields) == key:
            rows[index] = {**current, **row}
            replaced = True
            break
    if not replaced:
        rows.append(row)
    write_rows(path, fields, rows)
    return not replaced


def walk_objects(value, path="$", source_url=""):
    if isinstance(value, dict):
        yield path, value, source_url
        for key, child in value.items():
            yield from walk_objects(child, f"{path}.{key}", source_url)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_objects(child, f"{path}[{index}]", source_url)


def first_value(item, keys):
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
    return ""


def deep_first_value(item, keys, depth=2):
    direct = first_value(item, keys)
    if direct != "" or depth <= 0:
        return direct
    for value in item.values():
        if isinstance(value, dict):
            found = deep_first_value(value, keys, depth - 1)
            if found != "":
                return found
    return ""


def number_value(item, keys):
    value = first_value(item, keys)
    if isinstance(value, dict):
        value = first_value(value, ("count", "total", "value"))
    if isinstance(value, str):
        compact = value.strip().lower().replace(",", "")
        multiplier = 1
        if compact.endswith("k"):
            compact, multiplier = compact[:-1], 1000
        elif compact.endswith("m"):
            compact, multiplier = compact[:-1], 1_000_000
        try:
            number = float(compact) * multiplier
            return int(number) if number.is_integer() else number
        except ValueError:
            return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return ""


def deep_number_value(item, keys, depth=3):
    direct = number_value(item, keys)
    if direct != "" or depth <= 0:
        return direct
    for value in item.values():
        if isinstance(value, dict):
            found = deep_number_value(value, keys, depth - 1)
            if found != "":
                return found
    return ""


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def redact_payload(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in SENSITIVE_KEYS else redact_payload(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_payload(child) for child in value]
    return value


def candidate_from_object(item, path="$", source_url=""):
    metrics = {
        name: deep_number_value(item, aliases)
        for name, aliases in METRIC_ALIASES.items()
    }
    post_id = first_value(item, ID_KEYS)
    post_url = deep_first_value(item, URL_KEYS)
    caption = deep_first_value(item, CAPTION_KEYS)
    published_at = deep_first_value(item, DATE_KEYS)
    if not any(value != "" for value in metrics.values()):
        return None
    return {
        "post_id": str(post_id) if post_id != "" else "",
        "post_url": str(post_url) if post_url != "" else "",
        "caption": str(caption) if caption != "" else "",
        "published_at": iso_datetime(published_at),
        "source_url": source_url,
        "json_path": path,
        **metrics,
    }


def candidates_from_payloads(payloads):
    candidates = []
    for entry in payloads:
        payload = entry.get("payload") if isinstance(entry, dict) and "payload" in entry else entry
        source_url = entry.get("url", "") if isinstance(entry, dict) else ""
        for path, item, _ in walk_objects(payload, source_url=source_url):
            candidate = candidate_from_object(item, path, source_url)
            if candidate:
                candidates.append(candidate)
    return candidates


def candidate_score(candidate, publication):
    score = 0
    post_id = str(publication.get("post_id", ""))
    post_url = str(publication.get("post_url", ""))
    caption = normalize_text(publication.get("caption", ""))
    if post_id and candidate.get("post_id") == post_id:
        score += 120
    if post_id and post_id in candidate.get("post_url", ""):
        score += 80
    if post_url and candidate.get("post_url") == post_url:
        score += 100
    candidate_caption = normalize_text(candidate.get("caption", ""))
    if caption and candidate_caption == caption:
        score += 90
    elif caption and candidate_caption and (caption in candidate_caption or candidate_caption in caption):
        score += 45
    if candidate.get("views") != "":
        score += 10
    return score


def best_candidate(candidates, publication):
    ranked = sorted(
        ((candidate_score(candidate, publication), candidate) for candidate in candidates),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < 40:
        return None
    if not publication.get("post_id") and not publication.get("post_url") and len(ranked) > 1:
        top_score = ranked[0][0]
        tied_ids = {
            candidate.get("post_id") or candidate.get("post_url")
            for score, candidate in ranked
            if score == top_score
        }
        if len(tied_ids - {""}) > 1:
            return None
    return ranked[0][1]


def post_record_from_responses(responses, experiment_id, caption, scheduled_at, now=None):
    now = now or utc_now()
    objects = []
    for response in responses:
        payload = response.get("payload")
        if payload is None:
            continue
        objects.extend(walk_objects(payload, source_url=response.get("url", "")))
    best = None
    best_score = -1
    for path, item, source_url in objects:
        post_id = first_value(item, ID_KEYS)
        post_url = deep_first_value(item, URL_KEYS)
        item_caption = deep_first_value(item, CAPTION_KEYS)
        score = 0
        if post_id != "":
            score += 15
        if post_url and "/post/" in str(post_url):
            score += 40
        if normalize_text(item_caption) == normalize_text(caption):
            score += 80
        if any(token in path.lower() for token in ("post", "publication", "schedule")):
            score += 20
        if score > best_score:
            best_score = score
            best = (post_id, post_url, source_url)
    post_id, post_url, source_url = best or ("", "", "")
    if post_url and str(post_url).startswith("/"):
        post_url = urljoin("https://app.zoop.club", str(post_url))
    if not post_url and post_id:
        post_url = f"https://app.zoop.club/profile/post/{post_id}"
    created_at = now.isoformat()
    return {
        "experiment_id": experiment_id,
        "post_id": str(post_id or ""),
        "post_url": str(post_url or ""),
        "caption": caption,
        "scheduled_at": iso_datetime(scheduled_at),
        "published_at": iso_datetime(scheduled_at),
        "status": "scheduled",
        "created_at": created_at,
        "last_seen_at": "",
        "source_url": source_url,
    }


def due_window(publication, existing_snapshots, now=None):
    now = now or utc_now()
    published = publication.get("published_at") or publication.get("scheduled_at")
    try:
        moment = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return ""
    age_hours = (now - moment.astimezone(timezone.utc)).total_seconds() / 3600
    completed = {
        row.get("measurement_window", "")
        for row in existing_snapshots
        if row.get("experiment_id") == publication.get("experiment_id")
    }
    if "7d" in completed:
        completed.update(("72h", "24h"))
    elif "72h" in completed:
        completed.add("24h")
    for label, threshold in (("7d", 168), ("72h", 72), ("24h", 24)):
        if age_hours >= threshold and label not in completed:
            return label
    return ""


def generated_index(path):
    return {row.get("experiment_id", ""): row for row in read_rows(path)}


def discover_publications(candidates, generated_rows, publications, now=None):
    now = now or utc_now()
    known = {row.get("experiment_id", "") for row in publications}
    known_posts = {
        row.get("post_id") or row.get("post_url")
        for row in publications
        if row.get("post_id") or row.get("post_url")
    }
    identities = {}
    for candidate in candidates:
        identity = candidate.get("post_id") or candidate.get("post_url")
        if identity:
            identities[identity] = candidate
    available = {
        row.get("experiment_id", ""): row
        for row in generated_rows
        if row.get("experiment_id") and row.get("experiment_id") not in known
    }
    discovered = []
    ordered_candidates = sorted(
        identities.values(),
        key=lambda candidate: candidate.get("published_at", ""),
    )
    for candidate in ordered_candidates:
        identity = candidate.get("post_id") or candidate.get("post_url")
        if not identity or identity in known_posts:
            continue
        caption = normalize_text(candidate.get("caption"))
        matches = [
            row for row in available.values()
            if caption and normalize_text(row.get("caption") or row.get("overlay_text")) == caption
        ]
        if not matches:
            continue
        published = parse_datetime(candidate.get("published_at"))
        if published:
            dated = [
                (abs((published - created).total_seconds()), row)
                for row in matches
                if (created := parse_datetime(row.get("created_at"))) is not None
            ]
            dated.sort(key=lambda pair: pair[0])
            if not dated or dated[0][0] > 12 * 3600:
                continue
            if len(dated) > 1 and dated[0][0] == dated[1][0]:
                continue
            generated = dated[0][1]
        elif len(matches) == 1:
            generated = matches[0]
        else:
            continue
        experiment_id = generated.get("experiment_id", "")
        post_id = candidate.get("post_id", "")
        post_url = candidate.get("post_url", "")
        if post_url.startswith("/"):
            post_url = urljoin("https://app.zoop.club", post_url)
        if not post_url and post_id:
            post_url = f"https://app.zoop.club/profile/post/{post_id}"
        published_at = candidate.get("published_at") or generated.get("created_at", "")
        discovered.append({
            "experiment_id": experiment_id,
            "post_id": post_id,
            "post_url": post_url,
            "caption": generated.get("caption") or generated.get("overlay_text", ""),
            "scheduled_at": "",
            "published_at": iso_datetime(published_at),
            "status": "published",
            "created_at": now.isoformat(),
            "last_seen_at": now.isoformat(),
            "source_url": candidate.get("source_url", ""),
        })
        known.add(experiment_id)
        known_posts.add(identity)
        available.pop(experiment_id, None)
    return discovered


def build_metric_row(publication, candidate, generated, window, now=None):
    now = now or utc_now()
    experiment_id = publication.get("experiment_id", "")
    meta = generated.get(experiment_id, {})
    post_url = publication.get("post_url") or candidate.get("post_url", "")
    return {
        "experiment_id": experiment_id,
        "published_at": publication.get("published_at", ""),
        "theme": meta.get("theme", ""),
        "copy_variant": meta.get("copy_variant", ""),
        "caption_variant": meta.get("caption_variant", ""),
        "audio_id": meta.get("audio_id", ""),
        "audio_start_sec": meta.get("audio_start_sec", ""),
        "audio_segment": meta.get("audio_segment", ""),
        "views": candidate.get("views", ""),
        "likes": candidate.get("likes", 0),
        "comments": candidate.get("comments", 0),
        "shares": candidate.get("shares", 0),
        "follows": 0,
        "completion_rate": candidate.get("completion_rate", ""),
        "avg_watch_seconds": candidate.get("avg_watch_seconds", ""),
        "post_url": post_url,
        "notes": f"Automatic Zoop {window} snapshot",
        "recorded_at": now.isoformat(),
        "measurement_window": window,
        "source": candidate.get("source_url", "Zoop"),
    }


def register_publication(record, path="data/published_posts.csv"):
    if not record.get("experiment_id"):
        raise ValueError("Missing experiment_id for Zoop publication")
    upsert_row(path, PUBLICATION_FIELDS, record, ("experiment_id",))


def capture_profile_payloads(state, profile_url, raw_path):
    from playwright.sync_api import sync_playwright

    captured = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=state,
            viewport={"width": 1440, "height": 1000},
            timezone_id="Europe/Zurich",
        )

        def bridge(route):
            request = route.request
            try:
                if request.method == "OPTIONS":
                    route.fulfill(
                        status=204,
                        headers={
                            "Access-Control-Allow-Origin": "https://app.zoop.club",
                            "Access-Control-Allow-Credentials": "true",
                            "Access-Control-Allow-Headers": request.headers.get("access-control-request-headers", "authorization,content-type"),
                            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                        },
                        body="",
                    )
                    return
                response = route.fetch(timeout=60000)
                headers = dict(response.headers)
                headers["access-control-allow-origin"] = "https://app.zoop.club"
                headers["access-control-allow-credentials"] = "true"
                route.fulfill(response=response, headers=headers)
            except Exception as exc:
                print("ZOOP_METRICS_CORS_ERROR", request.method, request.url, repr(exc))
                route.abort()

        context.route("https://api-v2.influencerindex.com/**", bridge)
        page = context.new_page()

        def capture(response):
            if "influencerindex.com" not in response.url or response.request.method != "GET":
                return
            try:
                payload = response.json()
            except Exception:
                return
            captured.append({
                "url": response.url,
                "status": response.status,
                "payload": redact_payload(payload),
            })

        page.on("response", capture)
        page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        if "login" in page.url.lower() or "sign" in page.url.lower():
            raise RuntimeError("ZOOP session expired")
        for _ in range(5):
            page.mouse.wheel(0, 1400)
            page.wait_for_timeout(800)
        links = page.locator('a[href*="/profile/post/"]')
        urls = []
        for index in range(links.count()):
            href = links.nth(index).get_attribute("href")
            if href:
                urls.append(urljoin("https://app.zoop.club", href))
        for entry in captured:
            payload = entry.get("payload", {})
            posts = payload.get("posts", []) if isinstance(payload, dict) else []
            if not isinstance(posts, list):
                continue
            for post in posts:
                if isinstance(post, dict) and post.get("id") not in (None, ""):
                    urls.append(
                        f"https://app.zoop.club/profile/post/{post['id']}"
                    )
        print(f"ZOOP_METRICS_DETAIL_PAGES {len(set(urls))}")
        for url in list(dict.fromkeys(urls))[:80]:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
        browser.close()
    raw = {"captured_at": utc_now().isoformat(), "profile_url": profile_url, "responses": captured}
    target = Path(raw_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return captured


def collect(args):
    now = utc_now()
    publications = read_rows(args.publications)
    snapshots = read_rows(args.snapshots)
    generated_rows = read_rows(args.generated)
    generated = {row.get("experiment_id", ""): row for row in generated_rows}
    due = [row for row in publications if due_window(row, snapshots, now)]
    known = {row.get("experiment_id", "") for row in publications}
    unlinked = [row for row in generated_rows[-80:] if row.get("experiment_id") not in known]
    if not due and not unlinked:
        print("No Zoop metric snapshots are due")
        return 0
    payloads = capture_profile_payloads(args.state, args.profile_url, args.raw)
    candidates = candidates_from_payloads(payloads)
    discovered = discover_publications(candidates, unlinked, publications, now)
    if discovered:
        publications.extend(discovered)
        print(f"Discovered {len(discovered)} existing Zoop publication(s)")
    due = [row for row in publications if due_window(row, snapshots, now)]
    recorded = 0
    for publication in due:
        window = due_window(publication, snapshots, now)
        candidate = best_candidate(candidates, publication)
        if not candidate:
            print(f"No matching Zoop statistics for {publication.get('experiment_id')}")
            continue
        if not publication.get("post_id") and candidate.get("post_id"):
            publication["post_id"] = candidate["post_id"]
        if not publication.get("post_url") and candidate.get("post_url"):
            publication["post_url"] = candidate["post_url"]
        publication["last_seen_at"] = now.isoformat()
        publication["status"] = "published"
        metric = build_metric_row(publication, candidate, generated, window, now)
        upsert_row(args.snapshots, SNAPSHOT_FIELDS, metric, ("experiment_id", "measurement_window"))
        if candidate.get("views", "") not in ("", 0):
            upsert_row(args.metrics, METRIC_FIELDS, metric, ("experiment_id",))
        else:
            print(
                f"Zoop did not expose views for {publication.get('experiment_id')}; "
                "saved available metrics without updating the learning model"
            )
        snapshots.append(metric)
        recorded += 1
    write_rows(args.publications, PUBLICATION_FIELDS, publications)
    print(f"Recorded {recorded} Zoop metric snapshot(s)")
    return recorded


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=os.environ.get("ZOOP_STATE", "zoop_state.json"))
    parser.add_argument("--profile-url", default=os.environ.get("ZOOP_PROFILE_URL", "https://app.zoop.club/profile"))
    parser.add_argument("--publications", default="data/published_posts.csv")
    parser.add_argument("--generated", default="data/generated.csv")
    parser.add_argument("--metrics", default="data/metrics.csv")
    parser.add_argument("--snapshots", default="data/metric_snapshots.csv")
    parser.add_argument("--raw", default="output/zoop_metrics_raw.json")
    return parser.parse_args()


if __name__ == "__main__":
    collect(parse_args())
