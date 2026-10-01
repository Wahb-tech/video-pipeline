import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from .config import THEME_PRESETS, COPY_VARIANTS, CAPTION_TEMPLATES, CONTENT_FORMATS

THEMES = list(THEME_PRESETS.keys())
COPIES = [value for value in COPY_VARIANTS if value != "none"]
# Choice captions produced no comments in the first dataset. Keep them
# available for manual experiments, but do not spend automatic traffic on them.
CAPTIONS = ["aspiration", "minimal"]
FORMATS = list(CONTENT_FORMATS.keys())


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def performance_score(row):
    views = _to_float(row.get("views"))
    likes = _to_float(row.get("likes"))
    comments = _to_float(row.get("comments"))
    shares = _to_float(row.get("shares"))
    follows = _to_float(row.get("follows"))
    completion = _to_float(row.get("completion_rate"))
    if views > 0:
        engagement = 100.0 * (
            likes / views
            + 3.0 * comments / views
            + 4.0 * shares / views
            + 6.0 * follows / views
        )
        return engagement + 0.10 * max(0.0, min(100.0, completion))
    # Zoop currently exposes reactions/comments but no views. Keep learning from
    # the signals it does expose instead of silently discarding every result.
    return likes + 3.0 * comments + 4.0 * shares + 6.0 * follows


def load_metrics(path="data/metrics.csv"):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def factor_stats(rows, factor, values):
    raw = defaultdict(list)
    all_scores = [performance_score(r) for r in rows]
    prior_mean = sum(all_scores) / len(all_scores) if all_scores else 8.0
    prior_weight = 3.0
    for row in rows:
        value = row.get(factor, "")
        if value in values:
            raw[value].append(performance_score(row))
    result = {}
    for value in values:
        scores = raw[value]
        smoothed = (sum(scores) + prior_mean * prior_weight) / (len(scores) + prior_weight)
        result[value] = {
            "count": len(scores),
            "raw_mean": sum(scores) / len(scores) if scores else 0.0,
            "score": smoothed
        }
    return result


def _pick(stats, values, exploration=0.30, min_samples=3):
    under_sampled = [v for v in values if stats[v]["count"] < min_samples]
    if under_sampled:
        least = min(stats[v]["count"] for v in under_sampled)
        return random.choice([v for v in under_sampled if stats[v]["count"] == least])
    if random.random() < exploration:
        return random.choice(values)
    best = max(stats[v]["score"] for v in values)
    winners = [v for v in values if abs(stats[v]["score"] - best) < 1e-9]
    return random.choice(winners)


def _pick_70_20_10(stats, values, min_samples=3):
    rollout_targets = {
        value: int(CONTENT_FORMATS[value].get("rollout_target", min_samples))
        for value in values
    }
    under_sampled = [value for value in values if stats[value]["count"] < rollout_targets[value]]
    if under_sampled:
        progress = {
            value: stats[value]["count"] / rollout_targets[value]
            for value in under_sampled
        }
        least = min(progress.values())
        return random.choice([value for value in under_sampled if abs(progress[value] - least) < 1e-9])
    ranked = sorted(values, key=lambda value: stats[value]["score"], reverse=True)
    roll = random.random()
    if roll < 0.70:
        return ranked[0]
    if roll < 0.90:
        return random.choice(ranked[1:3] or ranked)
    return random.choice(values)


def choose_variant(metrics_path="data/metrics.csv", exploration=0.30):
    rows = load_metrics(metrics_path)
    format_stats = factor_stats(rows, "content_format", FORMATS)
    content_format = _pick_70_20_10(format_stats, FORMATS)
    preset = CONTENT_FORMATS[content_format]
    theme_values = preset["themes"]
    copy_values = preset["copies"]
    theme_stats = factor_stats(rows, "theme", theme_values)
    copy_stats = factor_stats(rows, "copy_variant", copy_values)
    caption_stats = factor_stats(rows, "caption_variant", CAPTIONS)
    generated_path = Path("data/generated.csv")
    if generated_path.exists() and generated_path.stat().st_size:
        with generated_path.open(newline="", encoding="utf-8") as f:
            generated = list(csv.DictReader(f))
        if generated:
            last_copy = generated[-1].get("copy_variant")
            copy_values = [value for value in copy_values if value != last_copy] or preset["copies"]
    return {
        "content_format": content_format,
        "theme": _pick(theme_stats, theme_values, exploration),
        "copy_variant": _pick(copy_stats, copy_values, exploration),
        "caption_variant": _pick(caption_stats, CAPTIONS, exploration),
        "sample_count": len(rows)
    }


def build_state(metrics_path="data/metrics.csv"):
    rows = load_metrics(metrics_path)
    return {
        "samples": len(rows),
        "content_format": factor_stats(rows, "content_format", FORMATS),
        "theme": factor_stats(rows, "theme", THEMES),
        "copy_variant": factor_stats(rows, "copy_variant", COPIES),
        "caption_variant": factor_stats(rows, "caption_variant", CAPTIONS),
        "next_variant": choose_variant(metrics_path)
    }


def main():
    print(json.dumps(choose_variant(), ensure_ascii=False))


if __name__ == "__main__":
    main()
