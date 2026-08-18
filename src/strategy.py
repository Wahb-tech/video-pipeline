import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from .config import THEME_PRESETS, COPY_VARIANTS, CAPTION_TEMPLATES

THEMES = list(THEME_PRESETS.keys())
COPIES = list(COPY_VARIANTS.keys())
CAPTIONS = list(CAPTION_TEMPLATES.keys())


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def performance_score(row):
    views = max(_to_float(row.get("views")), 1.0)
    likes = _to_float(row.get("likes"))
    comments = _to_float(row.get("comments"))
    shares = _to_float(row.get("shares"))
    follows = _to_float(row.get("follows"))
    completion = _to_float(row.get("completion_rate"))
    engagement = 100.0 * (
        likes / views
        + 3.0 * comments / views
        + 4.0 * shares / views
        + 6.0 * follows / views
    )
    return engagement + 0.10 * max(0.0, min(100.0, completion))


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


def choose_variant(metrics_path="data/metrics.csv", exploration=0.30):
    rows = load_metrics(metrics_path)
    theme_stats = factor_stats(rows, "theme", THEMES)
    copy_stats = factor_stats(rows, "copy_variant", COPIES)
    caption_stats = factor_stats(rows, "caption_variant", CAPTIONS)
    return {
        "theme": _pick(theme_stats, THEMES, exploration),
        "copy_variant": _pick(copy_stats, COPIES, exploration),
        "caption_variant": _pick(caption_stats, CAPTIONS, exploration),
        "sample_count": len(rows)
    }


def build_state(metrics_path="data/metrics.csv"):
    rows = load_metrics(metrics_path)
    return {
        "samples": len(rows),
        "theme": factor_stats(rows, "theme", THEMES),
        "copy_variant": factor_stats(rows, "copy_variant", COPIES),
        "caption_variant": factor_stats(rows, "caption_variant", CAPTIONS),
        "next_variant": choose_variant(metrics_path)
    }


def main():
    print(json.dumps(choose_variant(), ensure_ascii=False))


if __name__ == "__main__":
    main()
