import csv
import json
import random
from pathlib import Path
from .strategy import performance_score

CATALOG_PATH = Path("data/audio_catalog.json")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".flac")


def load_catalog(path=CATALOG_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["tracks"]


def resolve_audio_file(track, folder="assets/music"):
    base = Path(folder)
    stem = track["expected_file_stem"]
    for ext in AUDIO_EXTENSIONS:
        candidate = base / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def _load_metrics(path="data/metrics.csv"):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def audio_stats(catalog=None, metrics_path="data/metrics.csv"):
    catalog = catalog or load_catalog()
    rows = _load_metrics(metrics_path)
    all_scores = [performance_score(r) for r in rows]
    prior = sum(all_scores) / len(all_scores) if all_scores else 8.0
    prior_weight = 3.0
    stats = {}
    for audio_id in catalog:
        scores = [performance_score(r) for r in rows if r.get("audio_id") == audio_id]
        smoothed = (sum(scores) + prior * prior_weight) / (len(scores) + prior_weight)
        stats[audio_id] = {
            "count": len(scores),
            "raw_mean": sum(scores) / len(scores) if scores else 0.0,
            "score": smoothed
        }
    return stats


def _choose_segment(audio_id, track, metrics_path="data/metrics.csv", exploration=0.25):
    starts = [float(track["preferred_start_sec"])] + [float(x) for x in track.get("alternate_start_sec", [])]
    starts = list(dict.fromkeys(starts))
    rows = [r for r in _load_metrics(metrics_path) if r.get("audio_id") == audio_id]
    scores_by_start = {x: [] for x in starts}
    all_scores = [performance_score(r) for r in rows]
    prior = sum(all_scores) / len(all_scores) if all_scores else 8.0
    for row in rows:
        try:
            value = float(row.get("audio_start_sec", ""))
        except (TypeError, ValueError):
            continue
        nearest = min(starts, key=lambda x: abs(x - value))
        if abs(nearest - value) <= 0.25:
            scores_by_start[nearest].append(performance_score(row))
    under = [x for x in starts if len(scores_by_start[x]) < 2]
    if under:
        least = min(len(scores_by_start[x]) for x in under)
        return random.choice([x for x in under if len(scores_by_start[x]) == least])
    if random.random() < exploration:
        return random.choice(starts)
    def smoothed(x):
        vals = scores_by_start[x]
        return (sum(vals) + prior * 3.0) / (len(vals) + 3.0)
    best = max(smoothed(x) for x in starts)
    return random.choice([x for x in starts if abs(smoothed(x) - best) < 1e-9])


def choose_audio(theme, requested="auto", metrics_path="data/metrics.csv", exploration=0.30):
    catalog = load_catalog()
    if requested == "none":
        return None
    if requested != "auto":
        if requested not in catalog:
            raise ValueError(f"Unknown audio id: {requested}")
        chosen_id = requested
    else:
        stats = audio_stats(catalog, metrics_path)
        ids = list(catalog)
        under_sampled = [x for x in ids if stats[x]["count"] < 2]
        if under_sampled and random.random() < 0.65:
            chosen_id = random.choice(under_sampled)
        elif random.random() < exploration:
            weights = [catalog[x]["theme_weights"].get(theme, 1.0) for x in ids]
            chosen_id = random.choices(ids, weights=weights, k=1)[0]
        else:
            def value(x):
                return catalog[x]["theme_weights"].get(theme, 1.0) * stats[x]["score"]
            best = max(value(x) for x in ids)
            winners = [x for x in ids if abs(value(x) - best) < 1e-9]
            chosen_id = random.choice(winners)
    track = dict(catalog[chosen_id])
    track["audio_id"] = chosen_id
    track["selected_start_sec"] = _choose_segment(chosen_id, track, metrics_path)
    track["file"] = resolve_audio_file(track)
    return track


def catalog_status(folder="assets/music"):
    catalog = load_catalog()
    result = []
    for audio_id, track in catalog.items():
        path = resolve_audio_file(track, folder)
        result.append({
            "audio_id": audio_id,
            "title": track["title"],
            "version": track["version"],
            "available": bool(path),
            "path": str(path) if path else ""
        })
    return result
