import os
import random
import hashlib
import subprocess
import sys
import tempfile
from array import array
from math import sqrt
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


HIGH_QUALITY_VIDEO_ARGS = [
    "-c:v", "libx264", "-preset", "slow", "-crf", "12",
    "-profile:v", "high", "-level:v", "4.1",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart"
]

INTERMEDIATE_VIDEO_ARGS = [
    "-c:v", "libx264", "-preset", "slow", "-crf", "10",
    "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p"
]


def run(cmd):
    print(" ".join(str(x) for x in cmd))
    subprocess.run(cmd, check=True)


def probe_duration(path):
    p = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], check=True, capture_output=True, text=True)
    return float(p.stdout.strip())


def probe_dimensions(path):
    p = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)
    ], check=True, capture_output=True, text=True)
    width, height = p.stdout.strip().split("x")
    return int(width), int(height)


def choose_music_start(music, target_duration, preferred=None):
    """Resolve one audio start that is shared by analysis and final mixing."""
    if not music:
        return 0.0
    total = probe_duration(music)
    max_start = max(0.0, total - float(target_duration) - 0.1)
    if preferred is None or preferred == "":
        return random.uniform(0, max_start) if max_start > 0 else 0.0
    return max(0.0, min(float(preferred), max_start))


def _should_ai_upscale(width, height):
    enabled = os.getenv("ENABLE_AI_UPSCALE", "").lower() in {"1", "true", "yes"}
    script = Path(os.getenv("REALESRGAN_SCRIPT", ""))
    return enabled and script.is_file() and 600 <= width < 1000 and height > width * 1.4


CREATOR_STYLE_PROFILES = {
    "graphite": "colorbalance=bs=0.025:gs=-0.008:rh=0.015",
    "midnight_blue": "colorbalance=bs=0.055:bm=0.018:rs=-0.018",
    "noir_gold": "colorbalance=bs=0.025:rh=0.045:gh=0.018",
    "deep_burgundy": "colorbalance=rs=0.028:bs=-0.015:rh=0.025",
}


def creator_style_profile(seed):
    names = tuple(CREATOR_STYLE_PROFILES)
    digest = hashlib.sha256(str(seed).encode("utf-8")).digest()
    return names[digest[0] % len(names)]


def _creator_restyle_enabled():
    return os.getenv("ENABLE_CREATOR_RESTYLE", "").lower() in {"1", "true", "yes"}


def _ai_retouch_segment(src, start, seconds, destination, seed):
    if os.getenv("ENABLE_AI_CAR_RECOLOR", "").lower() not in {"1", "true", "yes"}:
        return False
    timeout = int(os.getenv("AI_RETOUCH_TIMEOUT_SECONDS", "900"))
    try:
        subprocess.run([
            sys.executable, "-m", "src.ai_retouch", "--input", str(src),
            "--output", str(destination), "--start", f"{start:.3f}",
            "--seconds", f"{seconds:.3f}", "--seed", str(seed),
        ], check=True, timeout=timeout)
        return Path(destination).is_file() and Path(destination).stat().st_size > 0
    except (OSError, subprocess.SubprocessError):
        print("AI car mask unavailable; keeping the creator restyle without local recoloring")
        return False


def _ai_upscale_segment(src, start, seconds, destination):
    script = Path(os.getenv("REALESRGAN_SCRIPT", ""))
    timeout = int(os.getenv("AI_UPSCALE_TIMEOUT_SECONDS", "900"))
    with tempfile.TemporaryDirectory(prefix="zoop_ai_", dir=Path(destination).parent) as temp:
        temp = Path(temp)
        frames = temp / "frames"
        enhanced = temp / "enhanced"
        frames.mkdir()
        enhanced.mkdir()
        try:
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src),
                "-t", f"{seconds:.3f}", "-an", "-vf", "fps=30",
                str(frames / "frame_%08d.png"),
            ], check=True, timeout=120)
            subprocess.run([
                sys.executable, str(script), "-n", "realesr-general-x4v3",
                "-i", str(frames), "-o", str(enhanced), "-s", "1.5",
                "-dn", "0.35", "--suffix", "out", "--fp32", "--tile", "128", "--ext", "png",
            ], check=True, timeout=timeout)
            output_frames = sorted(enhanced.glob("frame_*_out.png"))
            if not output_frames:
                raise RuntimeError("Real-ESRGAN produced no frames")
            run([
                "ffmpeg", "-y", "-framerate", "30", "-i", str(enhanced / "frame_%08d_out.png"),
                "-an", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "yuv420p", str(destination),
            ])
            print(f"Real-ESRGAN enhanced {len(output_frames)} frames")
            return True
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            print(f"Real-ESRGAN unavailable for this clip; using Lanczos fallback: {exc}")
            return False


def choose_cut_lengths(duration, count, bpm):
    if bpm <= 0:
        return [duration / count] * count
    beat = 60.0 / bpm
    possible = [2 * beat, 3 * beat, 4 * beat]
    lengths = [random.choice(possible) for _ in range(count)]
    scale = duration / sum(lengths)
    return [x * scale for x in lengths]


def _snap_cut_times(novelty, step_seconds, duration, count, search_radius=1.0):
    if count <= 1:
        return []
    cuts = []
    minimum_gap = min(1.15, duration / count * 0.65)
    for index in range(1, count):
        target = duration * index / count
        low = max(minimum_gap, target - search_radius)
        high = min(duration - minimum_gap, target + search_radius)
        candidates = [
            frame for frame in range(max(1, int(low / step_seconds)), min(len(novelty), int(high / step_seconds) + 1))
            if not cuts or frame * step_seconds - cuts[-1] >= minimum_gap
        ]
        if candidates:
            best = max(candidates, key=lambda frame: novelty[frame])
            cut = best * step_seconds
        else:
            cut = target
        remaining = count - index
        latest = duration - remaining * minimum_gap
        cut = min(max(cut, cuts[-1] + minimum_gap if cuts else minimum_gap), latest)
        cuts.append(cut)
    return cuts


def _normalized(values):
    peak = max(values, default=0.0)
    if peak <= 0:
        return [0.0] * len(values)
    return [value / peak for value in values]


def _behavior_novelty(energy, bass, texture, window=12):
    features = [_normalized(values) for values in (energy, bass, texture)]
    size = min(len(values) for values in features)
    novelty = [0.0] * size
    for index in range(1, size):
        before_start = max(0, index - window)
        after_end = min(size, index + window)
        before_size = index - before_start
        after_size = after_end - index
        if before_size < 2 or after_size < 2:
            continue
        structural_change = 0.0
        for values in features:
            before = sum(values[before_start:index]) / before_size
            after = sum(values[index:after_end]) / after_size
            structural_change += abs(after - before)
        accent = max(0.0, features[0][index] - features[0][index - 1])
        novelty[index] = structural_change + 0.18 * accent
    return novelty


def music_cut_lengths(music, start_sec, duration, count, bpm, with_method=False):
    if not music or count <= 1:
        lengths = choose_cut_lengths(duration, count, bpm)
        return (lengths, "bpm_fallback") if with_method else lengths
    sample_rate = 8000
    block_seconds = 0.05
    try:
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-ss", f"{float(start_sec or 0):.3f}",
            "-i", str(music), "-t", f"{duration:.3f}", "-ac", "1", "-ar", str(sample_rate),
            "-f", "f32le", "pipe:1"
        ], check=True, capture_output=True)
        samples = array("f")
        samples.frombytes(result.stdout)
        block_size = int(sample_rate * block_seconds)
        blocks = [
            samples[offset:offset + block_size]
            for offset in range(0, len(samples) - block_size + 1, block_size)
        ]
        energy = [sqrt(sum(value * value for value in block) / len(block)) for block in blocks]
        if len(energy) < count * 2 or max(energy, default=0) <= 0:
            raise ValueError("Audio analysis returned too little signal")
        bass = []
        texture = []
        for block in blocks:
            grouped = [sum(block[index:index + 8]) / len(block[index:index + 8]) for index in range(0, len(block), 8)]
            bass.append(sqrt(sum(value * value for value in grouped) / len(grouped)))
            texture.append(sum(abs(block[index] - block[index - 1]) for index in range(1, len(block))) / (len(block) - 1))
        novelty = _behavior_novelty(energy, bass, texture)
        cuts = _snap_cut_times(novelty, block_seconds, duration, count, search_radius=1.35)
        boundaries = [0.0, *cuts, duration]
        lengths = [boundaries[index + 1] - boundaries[index] for index in range(count)]
        return (lengths, "music_structure") if with_method else lengths
    except (OSError, subprocess.SubprocessError, ValueError):
        lengths = choose_cut_lengths(duration, count, bpm)
        return (lengths, "bpm_fallback") if with_method else lengths


def choose_clip_start(total, seconds, prior_starts=()):
    max_start = max(0.0, total - seconds - 0.1)
    if max_start <= 0:
        return 0.0
    prior = [float(value) for value in prior_starts if value not in (None, "")]
    if not prior:
        return random.uniform(0, max_start)
    candidates = [max_start * i / 23 for i in range(24)]
    random.shuffle(candidates)
    candidates.sort(key=lambda value: min(abs(value - old) for old in prior), reverse=True)
    return random.choice(candidates[: min(4, len(candidates))])


def normalize_clip(
    src, dst, seconds, style="mixed", prior_starts=(), segment_start=0.0,
    segment_duration=None, creator_restyle=False, restyle_seed="zoop", metadata=None,
):
    source_total = probe_duration(src)
    segment_start = max(0.0, min(float(segment_start or 0), source_total))
    total = min(float(segment_duration), source_total - segment_start) if segment_duration else source_total
    width, height = probe_dimensions(src)
    local_prior = [
        float(value) - segment_start for value in prior_starts
        if segment_start <= float(value) <= segment_start + total
    ]
    start = segment_start + choose_clip_start(total, seconds, local_prior)
    ai_source = Path(dst).with_suffix(".ai.mkv")
    restyled_source = Path(dst).with_suffix(".restyled.mkv")
    source = src
    source_start = start
    ai_applied = False
    car_recolor_applied = False
    restyle_active = bool(creator_restyle and _creator_restyle_enabled())
    if restyle_active:
        car_recolor_applied = _ai_retouch_segment(
            src, start, seconds, restyled_source, restyle_seed
        )
        if car_recolor_applied:
            source = restyled_source
            source_start = 0.0
            width, height = probe_dimensions(source)
    if _should_ai_upscale(width, height):
        ai_applied = _ai_upscale_segment(source, source_start, seconds, ai_source)
        if ai_applied:
            source = ai_source
            source_start = 0.0
            width, height = probe_dimensions(source)
    profile = creator_style_profile(restyle_seed) if restyle_active else ""
    if restyle_active:
        digest = hashlib.sha256(f"crop:{restyle_seed}".encode("utf-8")).digest()
        zoom = (1.025, 1.04, 1.055)[digest[0] % 3]
        scaled_width = int(1080 * zoom) // 2 * 2
        scaled_height = int(1920 * zoom) // 2 * 2
        x_ratio = (0.28, 0.5, 0.72)[digest[1] % 3]
        y_ratio = (0.35, 0.5, 0.65)[digest[2] % 3]
        filters = [
            f"scale={scaled_width}:{scaled_height}:force_original_aspect_ratio=increase:flags=lanczos",
            f"crop=1080:1920:x=(in_w-out_w)*{x_ratio}:y=(in_h-out_h)*{y_ratio}",
            "fps=30", "setsar=1",
        ]
    else:
        filters = [
            "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos",
            "crop=1080:1920", "fps=30", "setsar=1",
        ]
    if not ai_applied and (width < 1080 or height < 1920):
        filters.append("unsharp=5:5:0.28:3:3:0.0")
    if style == "dark_luxury":
        filters.extend([
            "eq=brightness=-0.10:contrast=1.18:saturation=0.78:gamma=0.93",
            "vignette=PI/6"
        ])
    if restyle_active:
        filters.extend([
            CREATOR_STYLE_PROFILES[profile],
            "curves=all='0/0 0.20/0.15 0.72/0.79 1/1'",
        ])
    vf = ",".join(filters)
    if metadata is not None:
        metadata["restyle_profile"] = profile
        metadata["ai_car_recolor_applied"] = car_recolor_applied
        metadata["ai_upscale_applied"] = ai_applied
    try:
        run([
            "ffmpeg", "-y", "-ss", f"{source_start:.3f}", "-i", str(source), "-t", f"{seconds:.3f}",
            "-an", "-vf", vf, *INTERMEDIATE_VIDEO_ARGS, str(dst)
        ])
    finally:
        if ai_source.exists():
            ai_source.unlink()
        if restyled_source.exists():
            restyled_source.unlink()
    return start


def concat_clips(clips, output):
    list_path = Path(output).with_suffix(".txt")
    list_path.write_text("".join(f"file '{Path(c).resolve()}'\n" for c in clips))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output)])


def _font_path():
    candidates = [
        "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    return next((p for p in candidates if os.path.exists(p)), None)


def _tracked_width(draw, text, font, spacing):
    widths = []
    for ch in text:
        box = draw.textbbox((0, 0), ch, font=font)
        widths.append(box[2] - box[0])
    return sum(widths) + max(0, len(text) - 1) * spacing


def _draw_tracked(draw, text, font, x, y, spacing, fill):
    cursor = x
    for ch in text:
        box = draw.textbbox((0, 0), ch, font=font)
        w = box[2] - box[0]
        draw.text((cursor, y), ch, font=font, fill=fill)
        cursor += w + spacing


def _overlay_lines(text):
    words = text.split()
    if len(text) <= 34 or len(words) < 4:
        return [text]
    target = len(text) / 2
    best = min(
        range(1, len(words)),
        key=lambda index: abs(len(" ".join(words[:index])) - target)
    )
    return [" ".join(words[:best]), " ".join(words[best:])]


def make_text_overlay(text, output, position="center"):
    if not text:
        return None
    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font_path = _font_path()
    clean = " ".join(text.upper().split())
    lines = _overlay_lines(clean)
    font_size = 29 if len(lines) == 1 else 25
    spacing = 10 if len(lines) == 1 else 6
    while True:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        widths = [_tracked_width(draw, line, font, spacing) for line in lines]
        if max(widths) <= 820 or font_size <= 18:
            break
        font_size -= 1
        spacing = max(3, spacing - 1)
    center_y = 906 if position == "center" else 1435
    line_height = font_size + 18
    first_y = center_y - (len(lines) - 1) * line_height / 2
    for index, (line, width) in enumerate(zip(lines, widths)):
        x = (1080 - width) / 2
        y = first_y + index * line_height
        _draw_tracked(draw, line, font, x, y, spacing, (238, 238, 238, 230))
    canvas.save(output)
    return output


def add_overlay(video, overlay, output):
    if not overlay:
        Path(output).write_bytes(Path(video).read_bytes())
        return
    run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(overlay),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]", "-an", *HIGH_QUALITY_VIDEO_ARGS, str(output)
    ])


def add_music(video, music, output, target_duration, music_volume=0.75, start_sec=None):
    if not music:
        raise RuntimeError("No music file available; refusing to export a silent video")
    start = choose_music_start(music, target_duration, start_sec)
    fade_out = max(0, target_duration - 1.0)
    af = f"volume={music_volume},afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out:.2f}:d=1.0"
    run([
        "ffmpeg", "-y", "-i", str(video), "-ss", f"{start:.3f}", "-stream_loop", "-1", "-i", str(music),
        "-t", f"{target_duration:.3f}", "-map", "0:v:0", "-map", "1:a:0", "-af", af,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)
    ])
