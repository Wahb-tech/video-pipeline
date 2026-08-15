import json
import math
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


# --- "Dark luxury" grading -------------------------------------------------
# Desaturated, slightly cooled shadows, gentle vignette, subtle grain.
# Tune GRADE_* constants to taste rather than editing the filter string.
GRADE_CONTRAST = 1.15
GRADE_BRIGHTNESS = -0.06
GRADE_SATURATION = 0.75
GRADE_VIGNETTE = "PI/4"
GRADE_GRAIN = 6


def build_grade_filter():
    return (
        f"eq=contrast={GRADE_CONTRAST}:brightness={GRADE_BRIGHTNESS}:saturation={GRADE_SATURATION},"
        "curves=r='0/0 0.5/0.42 1/0.95':b='0/0.02 0.5/0.55 1/1',"
        f"vignette={GRADE_VIGNETTE},"
        f"noise=alls={GRADE_GRAIN}:allf=t"
    )


def normalize_clip(src, dst, seconds):
    total = probe_duration(src)
    max_start = max(0.0, total - seconds - 0.1)
    start = random.uniform(0, max_start) if max_start > 0 else 0
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,"
        + build_grade_filter()
    )
    run([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{seconds:.3f}",
        "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", str(dst)
    ])


def concat_clips(clips, output):
    list_path = Path(output).with_suffix(".txt")
    list_path.write_text("".join(f"file '{Path(c).resolve()}'\n" for c in clips))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output)])


# --- Text overlay ------------------------------------------------------
# Condensed display fonts read as "premium / intimidating" far better than
# generic DejaVu/Liberation. Install these in the build image (apt or
# vendor the .ttf into the repo, e.g. assets/fonts/).
FONT_PATHS = [
    "/usr/share/fonts/truetype/anton/Anton-Regular.ttf",
    "/usr/share/fonts/truetype/bebas-neue/BebasNeue-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]

TEXT_FILL = (230, 230, 225)          # off-white, not pure white
TEXT_STROKE_FILL = (0, 0, 0)
TEXT_STROKE_WIDTH = 2                # thin stroke reads premium, thick reads "meme"
TEXT_TRACKING = 6                    # letter-spacing in px, gives the "engraved" look


def draw_tracked_text(draw, pos, text, font, fill, stroke_width, stroke_fill, tracking=0):
    x, y = pos
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        bbox = draw.textbbox((0, 0), ch, font=font)
        x += (bbox[2] - bbox[0]) + tracking
    return x


def tracked_text_width(draw, text, font, tracking=0):
    width = 0
    for ch in text:
        bbox = draw.textbbox((0, 0), ch, font=font)
        width += (bbox[2] - bbox[0]) + tracking
    return width - tracking if text else 0


def make_text_overlay(text, output, position="center"):
    if not text:
        return None

    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    font_path = next((p for p in FONT_PATHS if os.path.exists(p)), None)
    font = ImageFont.truetype(font_path, 74) if font_path else ImageFont.load_default()

    words = text.upper().split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        test_w = tracked_text_width(draw, test, font, TEXT_TRACKING)
        if test_w > 900 and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))

    line_h = 95
    total_h = len(lines) * line_h
    y = 760 if position == "center" else 1350
    y -= total_h // 2

    for line in lines:
        w = tracked_text_width(draw, line, font, TEXT_TRACKING)
        x = (1080 - w) // 2
        draw_tracked_text(
            draw, (x, y), line, font,
            fill=TEXT_FILL,
            stroke_width=TEXT_STROKE_WIDTH,
            stroke_fill=TEXT_STROKE_FILL,
            tracking=TEXT_TRACKING,
        )
        y += line_h

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
