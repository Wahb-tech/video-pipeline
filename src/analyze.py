import json
from pathlib import Path
from .strategy import build_state, factor_stats, load_metrics
from .audio import load_catalog


def table(title, stats):
    lines = [f"## {title}", "", "| Variant | Samples | Smoothed score | Raw mean |", "|---|---:|---:|---:|"]
    ordered = sorted(stats.items(), key=lambda kv: kv[1]["score"], reverse=True)
    for name, s in ordered:
        lines.append(f"| {name} | {s['count']} | {s['score']:.2f} | {s['raw_mean']:.2f} |")
    lines.append("")
    return lines


def generate(metrics="data/metrics.csv", report="reports/latest.md", state_path="data/strategy_state.json"):
    state = build_state(metrics)
    rows = load_metrics(metrics)
    audio_ids = list(load_catalog())
    audio_stats = factor_stats(rows, "audio_id", audio_ids)
    state["audio"] = audio_stats
    segment_values = sorted({r.get("audio_segment", "") for r in rows if r.get("audio_segment")})
    segment_stats = factor_stats(rows, "audio_segment", segment_values) if segment_values else {}
    state["audio_segment"] = segment_stats
    lines = [
        "# ZOOP Experiment Report",
        "",
        f"Recorded posts: **{state['samples']}**",
        "",
        "The score below is an internal experiment score, not ZOOP's ranking formula. It weights likes, comments, shares, follows and optional completion rate so the pipeline can compare its own variants consistently.",
        ""
    ]
    lines += table("Themes", state["theme"])
    lines += table("Overlay copy", state["copy_variant"])
    lines += table("Caption type", state["caption_variant"])
    lines += table("Known audio", audio_stats)
    if segment_stats:
        lines += table("Audio segments", segment_stats)
    nxt = state["next_variant"]
    lines += [
        "## Suggested next visual test",
        "",
        f"- Theme: `{nxt['theme']}`",
        f"- Overlay: `{nxt['copy_variant']}`",
        f"- Caption: `{nxt['caption_variant']}`",
        "",
        "Audio and segment selection are handled separately by `src.audio`: the system explores under-tested tracks/segments, then increasingly exploits combinations with the strongest observed performance.",
        ""
    ]
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    Path(report).write_text("\n".join(lines), encoding="utf-8")
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)
    Path(state_path).write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {report} and {state_path}")


if __name__ == "__main__":
    generate()
