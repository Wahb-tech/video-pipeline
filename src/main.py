import argparse
import csv
import json
import os
import random
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .config import BASELINE, CAPTION_TEMPLATES, THEME_PRESETS
from .gemini import generate_plan
from .stock import STOCK_BLOCKED_CATEGORIES, find_clip, download, load_usage_history, append_used
from .render import choose_cut_lengths, normalize_clip, concat_clips, make_text_overlay, add_overlay, add_music
from .strategy import choose_variant
from .audio import choose_audio
from .csvutil import append_row
from .authorized_video import download_authorized_library, choose_authorized_clip
from .text_cleanup import TextCleanupError, clean_creator_text

GENERATED_FIELDS = [
    "experiment_id", "created_at", "style", "theme", "copy_variant", "caption_variant",
    "duration", "clips", "bpm", "overlay_text", "caption", "audio_id", "audio_title",
    "audio_artist", "audio_version", "audio_start_sec", "audio_segment", "audio_available", "music_file",
    "sequence_signature"
]


def shuffled_categories(categories, recent_signatures=()):
    categories = list(categories)
    if len(categories) < 2:
        return categories
    best = categories[:]
    for _ in range(50):
        candidate = categories[:]
        random.shuffle(candidate)
        best = candidate
        signature = ">".join(candidate)
        if all(a != b for a, b in zip(candidate, candidate[1:])) and signature not in recent_signatures:
            return candidate
    return best


def load_recent_sequences(path="data/generated.csv", limit=12):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return set()
    with p.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[-limit:]
    return {row.get("sequence_signature", "") for row in rows if row.get("sequence_signature")}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--style", default=BASELINE["style"], choices=["dark_luxury", "summer_luxury", "dubai", "yacht_life", "mixed"])
    p.add_argument("--theme", default="auto", choices=["auto", "dark_cars", "money", "dark_life", "mixed_dark"])
    p.add_argument("--copy-variant", default="auto", choices=["auto", "one_day", "soon", "built_silence", "different_standard", "no_plan_b", "earned_not_given", "one_goal", "destiny", "end_goal", "none"])
    p.add_argument("--caption-variant", default="auto", choices=["auto", "choice", "aspiration", "minimal"])
    p.add_argument("--duration", type=float, default=BASELINE["duration"])
    p.add_argument("--clips", type=int, default=BASELINE["clips"])
    p.add_argument("--bpm", type=float, default=BASELINE["bpm"])
    p.add_argument("--text-mode", default="minimal", choices=["minimal", "none"])
    p.add_argument("--text-position", default=BASELINE["text_position"], choices=["center", "lower"])
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--audio", default="auto")
    p.add_argument("--music", default="")
    p.add_argument("--experiment-id", default="")
    p.add_argument("--output", default="output/ZOOP_READY.mp4")
    p.add_argument("--authorized-share", type=float, default=0.82)
    return p.parse_args()


def make_rights_manifest(sources, experiment_id):
    return {
        "experiment_id": experiment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "Keep this manifest with the exported video as a provenance record. It is not a legal opinion on any particular use.",
        "sources": [
            {
                "provider": x.get("provider", ""),
                "stock_id": x.get("id", ""),
                "category": x.get("category", ""),
                "search_query": x.get("search_query", ""),
                "page_url": x.get("page_url", ""),
                "author": x.get("author", ""),
                "author_url": x.get("author_url", ""),
                "license_reference": x.get("license_reference", ""),
                "retrieved_at": x.get("retrieved_at", "")
            }
            for x in sources
        ]
    }


def choose_cleanup_fallback(items, rejected_id, usage_history, run_counts, position):
    candidates = [
        item for item in items
        if not item.get("cleanup_text") and item.get("id") != rejected_id
    ]
    return choose_authorized_clip(candidates, usage_history, run_counts, position)


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    authorized_names = (
        "AUTHORIZED_VIDEO_URLS",
        "AUTHORIZED_TEXT_VIDEO_URLS",
        "AUTHORIZED_CREATOR_HANDLES",
        "AUTHORIZED_TEXT_CREATOR_HANDLES",
    )
    if not any(os.getenv(name) for name in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "COVERR_API_KEY", *authorized_names)):
        raise SystemExit("Configure an authorized creator source or a stock API key")

    selected = choose_variant()
    theme = selected["theme"] if args.theme == "auto" else args.theme
    copy_variant = selected["copy_variant"] if args.copy_variant == "auto" else args.copy_variant
    caption_variant = selected["caption_variant"] if args.caption_variant == "auto" else args.caption_variant
    experiment_id = args.experiment_id or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    authorized = download_authorized_library(work / "authorized")
    if any(os.getenv(name) for name in authorized_names) and not authorized:
        message = "No usable authorized footage was downloaded"
        if os.getenv("REQUIRE_AUTHORIZED_FOOTAGE", "").lower() in {"1", "true", "yes"}:
            raise RuntimeError(
                f"{message}. The configured sources may be unavailable, private, or rejected by the downloader; "
                "refusing a stock-only video"
            )
        print(f"{message}; continuing with licensed stock providers")

    text_mode = "none" if copy_variant == "none" else args.text_mode
    plan = generate_plan(args.style, args.duration, args.clips, text_mode, theme, copy_variant)
    plan["categories"] = shuffled_categories(plan["categories"], load_recent_sequences())
    caption = random.choice(CAPTION_TEMPLATES[caption_variant][theme])
    plan.update({
        "experiment_id": experiment_id,
        "theme": theme,
        "copy_variant": copy_variant,
        "caption_variant": caption_variant,
        "caption": caption
    })

    audio = None if args.music else choose_audio(theme, args.audio)
    direct_music = Path(args.music) if args.music and Path(args.music).exists() else None
    music = direct_music or (audio.get("file") if audio else None)
    start_sec = None if direct_music else (audio.get("selected_start_sec") if audio else None)
    audio_plan = {
        "audio_id": audio.get("audio_id") if audio else "",
        "title": audio.get("title") if audio else "",
        "artist": audio.get("artist") if audio else "",
        "version": audio.get("version") if audio else "",
        "preferred_start_sec": audio.get("preferred_start_sec") if audio else "",
        "selected_start_sec": start_sec if start_sec is not None else "",
        "popular_window": audio.get("popular_window") if audio else "",
        "alternate_start_sec": audio.get("alternate_start_sec") if audio else [],
        "available": bool(music),
        "resolved_file": str(music) if music else "",
        "note": "Known commercial audio is not downloaded by this project. The selected file is used only if it exists in assets/music or was passed with --music."
    }
    plan["audio"] = audio_plan

    (out.parent / "creative_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    (out.parent / "audio_plan.json").write_text(json.dumps(audio_plan, indent=2, ensure_ascii=False), encoding="utf-8")
    (out.parent / "caption.txt").write_text(caption, encoding="utf-8")
    (out.parent / "EXPERIMENT_ID.txt").write_text(experiment_id, encoding="utf-8")

    lengths = choose_cut_lengths(args.duration, args.clips, args.bpm)
    usage_history = load_usage_history()
    current_video_ids = set()
    current_starts = {}
    run_counts = {}
    normalized = []
    sources = []

    category_pool = list(dict.fromkeys(THEME_PRESETS.get(theme, plan["categories"])))
    authorized_count = min(args.clips, max(0, round(args.clips * args.authorized_share)))
    authorized_positions = set(random.sample(range(args.clips), authorized_count)) if authorized else set()
    for i, category in enumerate(plan["categories"]):
        attempts = [] if category in STOCK_BLOCKED_CATEGORIES else [category]
        alternatives = [
            value for value in category_pool
            if value != category and value not in STOCK_BLOCKED_CATEGORIES
        ]
        random.shuffle(alternatives)
        attempts.extend(alternatives)
        item = choose_authorized_clip(authorized, usage_history, run_counts, i) if i in authorized_positions else None
        errors = []
        for attempted_category in ([] if item else attempts):
            try:
                item = find_clip(attempted_category, usage_history, args.style, current_video_ids)
                category = attempted_category
                break
            except RuntimeError as exc:
                errors.append(str(exc))
        if item is None and authorized:
            item = choose_authorized_clip(authorized, usage_history, run_counts, i)
        if item is None:
            raise RuntimeError("; ".join(errors))
        item_key = f'{item["provider"]}:{item["id"]}'
        if item["provider"] != "authorized_creator":
            current_video_ids.add(item_key)
        raw = work / f"raw_{i:02d}.mp4"
        norm = work / f"clip_{i:02d}.mp4"
        download(item.get("local_path") or item["url"], raw)
        input_clip = raw
        if item.get("cleanup_text"):
            cleaned = work / f"cleaned_{i:02d}.mp4"
            try:
                item["removed_text_region"] = clean_creator_text(raw, cleaned)
                input_clip = cleaned
            except TextCleanupError as exc:
                rejected_id = item.get("id")
                item = choose_cleanup_fallback(
                    authorized, rejected_id, usage_history, run_counts, i
                )
                if item is None:
                    raise RuntimeError(
                        f"Text cleanup failed for {rejected_id} and no clean authorized fallback is available"
                    ) from exc
                print(f"Text cleanup failed for {rejected_id}; using clean authorized clip {item['id']}")
                item_key = f'{item["provider"]}:{item["id"]}'
                download(item.get("local_path") or item["url"], raw)
                input_clip = raw
        run_counts[item_key] = run_counts.get(item_key, 0) + 1
        if item["provider"] == "authorized_creator":
            author_key = f'author:{item.get("author", "authorized creator").lower()}'
            run_counts[author_key] = run_counts.get(author_key, 0) + 1
        previous_starts = usage_history.get(item_key, {}).get("starts", []) + current_starts.get(item_key, [])
        start_sec = normalize_clip(input_clip, norm, lengths[i], args.style, previous_starts)
        current_starts.setdefault(item_key, []).append(start_sec)
        normalized.append(norm)
        item["category"] = category
        item["start_sec"] = round(start_sec, 3)
        item["cut_seconds"] = lengths[i]
        item["sequence_index"] = i
        sources.append(item)

    (out.parent / "sources.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")
    rights = make_rights_manifest(sources, experiment_id)
    (out.parent / "rights_manifest.json").write_text(json.dumps(rights, indent=2, ensure_ascii=False), encoding="utf-8")
    if any(item.get("provider") == "coverr" for item in sources):
        caption = f"{caption}\n\nFootage via Coverr: https://coverr.co"
        plan["caption"] = caption
        (out.parent / "caption.txt").write_text(caption, encoding="utf-8")
        (out.parent / "creative_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    if any(item.get("provider") == "authorized_creator" for item in sources):
        fallback_owner = os.getenv("AUTHORIZED_SOURCE_OWNER", "authorized creator").strip()
        owners = sorted({
            str(item.get("author") or fallback_owner).strip()
            for item in sources
            if item.get("provider") == "authorized_creator"
        })
        caption = f"{caption}\n\nFootage used with permission from {', '.join(owners)}."
        plan["caption"] = caption
        (out.parent / "caption.txt").write_text(caption, encoding="utf-8")
        (out.parent / "creative_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    concat = work / "concat.mp4"
    texted = work / "texted.mp4"
    overlay = work / "overlay.png"
    concat_clips(normalized, concat)
    overlay_path = make_text_overlay(plan.get("overlay_text", ""), overlay, args.text_position)
    add_overlay(concat, overlay_path, texted)
    add_music(texted, music, out, args.duration, start_sec=start_sec)

    generated = {
        "experiment_id": experiment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "style": args.style,
        "theme": theme,
        "copy_variant": copy_variant,
        "caption_variant": caption_variant,
        "duration": args.duration,
        "clips": args.clips,
        "bpm": args.bpm,
        "overlay_text": plan.get("overlay_text", ""),
        "caption": caption,
        "audio_id": audio_plan["audio_id"],
        "audio_title": audio_plan["title"],
        "audio_artist": audio_plan["artist"],
        "audio_version": audio_plan["version"],
        "audio_start_sec": audio_plan["selected_start_sec"],
        "audio_segment": f"{audio_plan['audio_id']}@{audio_plan['selected_start_sec']}" if audio_plan["audio_id"] else "",
        "audio_available": int(bool(music)),
        "music_file": str(music) if music else "",
        "sequence_signature": ">".join(plan["categories"])
    }
    append_row("data/generated.csv", GENERATED_FIELDS, generated)
    append_used(sources, experiment_id)

    audio_line = "No music file available; video exported silent." if not audio_plan["available"] else f"{audio_plan['title']} — {audio_plan['version']} from {audio_plan['selected_start_sec']}s"
    post_card = [
        f"# ZOOP upload — {experiment_id}",
        "",
        f"**Theme:** {theme}",
        f"**Overlay:** {copy_variant}",
        f"**Caption type:** {caption_variant}",
        f"**Audio:** {audio_line}",
        "",
        "## Caption",
        "",
        caption,
        "",
        "## Files",
        "",
        "- `ZOOP_READY.mp4`",
        "- `audio_plan.json`",
        "- `rights_manifest.json`",
        "- `creative_plan.json`",
        "- `sources.json`",
        "",
        "If ZOOP asks for an AI Content / AI Edited Content label, apply the appropriate label before publishing.",
        "",
        "After publishing, record the post metrics using the Record ZOOP Metrics workflow with this experiment ID."
    ]
    (out.parent / "post_card.md").write_text("\n".join(post_card), encoding="utf-8")
    print(f"Created {out}")
    print(f"Experiment ID: {experiment_id}")
    print(f"Audio selection: {audio_plan['audio_id'] or 'none'} | available={audio_plan['available']}")


if __name__ == "__main__":
    main()
