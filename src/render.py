import os
import random
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def run(cmd):
    print(" ".join(str(x) for x in cmd))
    subprocess.run(cmd, check=True)


def probe_duration(path):
    p = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], check=True, capture_output=True, text=True)
    return float(p.stdout.strip())


def choose_cut_lengths(duration, count, bpm):
    if bpm <= 0:
        return [duration / count] * count
    beat = 60.0 / bpm
    possible = [2 * beat, 3 * beat, 4 * beat]
    lengths = [random.choice(possible) for _ in range(count)]
    scale = duration / sum(lengths)
    return [x * scale for x in lengths]


def normalize_clip(src, dst, seconds, style="mixed"):
    total = probe_duration(src)
    max_start = max(0.0, total - seconds - 0.1)
    start = random.uniform(0, max_start) if max_start > 0 else 0
    filters = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        "fps=30",
        "setsar=1"
    ]
    if style == "dark_luxury":
        filters.extend([
            "eq=brightness=-0.10:contrast=1.18:saturation=0.78:gamma=0.93",
            "vignette=PI/6"
        ])
    vf = ",".join(filters)
    run([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{seconds:.3f}",
        "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", str(dst)
    ])


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


def make_text_overlay(text, output, position="center"):
    if not text:
        return None
    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font_path = _font_path()
    font = ImageFont.truetype(font_path, 27) if font_path else ImageFont.load_default()
    clean = " ".join(text.upper().split())
    spacing = 11
    width = _tracked_width(draw, clean, font, spacing)
    while width > 760 and spacing > 4:
        spacing -= 1
        width = _tracked_width(draw, clean, font, spacing)
    x = (1080 - width) / 2
    y = 906 if position == "center" else 1435
    _draw_tracked(draw, clean, font, x, y, spacing, (238, 238, 238, 230))
    canvas.save(output)
    return output


def add_overlay(video, overlay, output):
    if not overlay:
        Path(output).write_bytes(Path(video).read_bytes())
        return
    run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(overlay),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", str(output)
    ])


def add_music(video, music, output, target_duration, music_volume=0.75):
    if not music:
        run(["ffmpeg", "-y", "-i", str(video), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(output)])
        return
    m_total = probe_duration(music)
    max_start = max(0.0, m_total - target_duration - 0.1)
    start = random.uniform(0, max_start) if max_start > 0 else 0
    fade_out = max(0, target_duration - 1.0)
    af = f"volume={music_volume},afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out:.2f}:d=1.0"
    run([
        "ffmpeg", "-y", "-i", str(video), "-ss", f"{start:.3f}", "-stream_loop", "-1", "-i", str(music),
        "-t", f"{target_duration:.3f}", "-map", "0:v:0", "-map", "1:a:0", "-af", af,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)
    ])
