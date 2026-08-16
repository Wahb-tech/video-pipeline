import argparse
import json
import os
import random
import shutil
from pathlib import Path
from .gemini import generate_plan
from .stock import find_clip, download
from .render import choose_cut_lengths, normalize_clip, concat_clips, make_text_overlay, add_overlay, add_music


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--style", default="mixed", choices=["dark_luxury", "summer_luxury", "dubai", "yacht_life", "mixed"])
    p.add_argument("--duration", type=float, default=15.0)
    p.add_argument("--clips", type=int, default=10)
    p.add_argument("--bpm", type=float, default=120.0)
    p.add_argument("--text-mode", default="minimal", choices=["minimal", "none"])
    p.add_argument("--text-position", default="center", choices=["center", "lower"])
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--music", default="")
    p.add_argument("--output", default="output/ZOOP_READY.mp4")
    return p.parse_args()


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    if not os.getenv("PEXELS_API_KEY") and not os.getenv("PIXABAY_API_KEY"):
        raise SystemExit("Set PEXELS_API_KEY and/or PIXABAY_API_KEY")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    plan = generate_plan(args.style, args.duration, args.clips, args.text_mode)
    (out.parent / "creative_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    (out.parent / "caption.txt").write_text(plan.get("caption", ""), encoding="utf-8")

    lengths = choose_cut_lengths(args.duration, args.clips, args.bpm)
    used = set()
    normalized = []
    sources = []

    for i, category in enumerate(plan["categories"]):
        item = find_clip(category, used, args.style)
        used.add(f'{item["provider"]}:{item["id"]}')
        raw = work / f"raw_{i:02d}.mp4"
        norm = work / f"clip_{i:02d}.mp4"
        download(item["url"], raw)
        normalize_clip(raw, norm, lengths[i], args.style)
        normalized.append(norm)
        item["category"] = category
        item["cut_seconds"] = lengths[i]
        sources.append(item)

    (out.parent / "sources.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False))
    concat = work / "concat.mp4"
    texted = work / "texted.mp4"
    overlay = work / "overlay.png"
    concat_clips(normalized, concat)
    overlay_path = make_text_overlay(plan.get("overlay_text", ""), overlay, args.text_position)
    add_overlay(concat, overlay_path, texted)
    music = Path(args.music) if args.music and Path(args.music).exists() else None
    add_music(texted, music, out, args.duration)
    print(f"Created {out}")


if __name__ == "__main__":
    main()
