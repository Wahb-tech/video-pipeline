import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from .zoop_metrics import upsert_row

METRICS_FIELDS = [
    "experiment_id", "published_at", "theme", "copy_variant", "caption_variant",
    "audio_id", "audio_start_sec", "audio_segment", "views", "likes", "comments", "shares", "follows",
    "completion_rate", "avg_watch_seconds", "post_url", "notes", "recorded_at",
    "measurement_window", "source"
]


def load_generated(path="data/generated.csv"):
    p = Path(path)
    if not p.exists():
        return {}
    with p.open(newline="", encoding="utf-8") as f:
        return {row["experiment_id"]: row for row in csv.DictReader(f)}


def record(args):
    generated = load_generated(args.generated)
    meta = generated.get(args.experiment_id)
    if not meta:
        raise SystemExit(f"Unknown experiment_id: {args.experiment_id}")
    row = {
        "experiment_id": args.experiment_id,
        "published_at": args.published_at,
        "theme": meta.get("theme", ""),
        "copy_variant": meta.get("copy_variant", ""),
        "caption_variant": meta.get("caption_variant", ""),
        "audio_id": meta.get("audio_id", ""),
        "audio_start_sec": meta.get("audio_start_sec", ""),
        "audio_segment": meta.get("audio_segment", ""),
        "views": args.views,
        "likes": args.likes,
        "comments": args.comments,
        "shares": args.shares,
        "follows": args.follows,
        "completion_rate": args.completion_rate,
        "avg_watch_seconds": args.avg_watch_seconds,
        "post_url": args.post_url,
        "notes": args.notes,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "measurement_window": "manual",
        "source": "manual",
    }
    upsert_row(args.metrics, METRICS_FIELDS, row, ("experiment_id",))
    print(f"Recorded metrics for {args.experiment_id}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--experiment-id", required=True)
    p.add_argument("--published-at", default="")
    p.add_argument("--views", type=int, required=True)
    p.add_argument("--likes", type=int, default=0)
    p.add_argument("--comments", type=int, default=0)
    p.add_argument("--shares", type=int, default=0)
    p.add_argument("--follows", type=int, default=0)
    p.add_argument("--completion-rate", type=float, default=0.0)
    p.add_argument("--avg-watch-seconds", type=float, default=0.0)
    p.add_argument("--post-url", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--generated", default="data/generated.csv")
    p.add_argument("--metrics", default="data/metrics.csv")
    return p.parse_args()


if __name__ == "__main__":
    record(parse_args())
