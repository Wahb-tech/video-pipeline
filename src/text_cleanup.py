import csv
import shutil
import subprocess
from pathlib import Path

from .render import probe_duration


class TextCleanupError(RuntimeError):
    pass


def recurring_text_region(boxes_by_frame, width, height):
    if not boxes_by_frame or width <= 0 or height <= 0:
        return None
    bands = {}
    for frame_index, boxes in enumerate(boxes_by_frame):
        for x, y, w, h in boxes:
            band = min(11, int(((y + h / 2) / height) * 12))
            bands.setdefault(band, []).append((frame_index, x, y, w, h))
    minimum = max(2, (len(boxes_by_frame) + 1) // 2)
    recurring = []
    for entries in bands.values():
        if len({entry[0] for entry in entries}) >= minimum:
            recurring.extend(entries)
    if not recurring:
        return None
    x1 = max(0, min(entry[1] for entry in recurring) - 24)
    y1 = max(0, min(entry[2] for entry in recurring) - 18)
    x2 = min(width, max(entry[1] + entry[3] for entry in recurring) + 24)
    y2 = min(height, max(entry[2] + entry[4] for entry in recurring) + 18)
    return x1, y1, x2 - x1, y2 - y1


def _probe_size(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)
    ], check=True, capture_output=True, text=True)
    width, height = result.stdout.strip().split("x")
    return int(width), int(height)


def _ocr_boxes(frame):
    result = subprocess.run([
        "tesseract", str(frame), "stdout", "--psm", "11", "tsv"
    ], check=True, capture_output=True, text=True)
    boxes = []
    for row in csv.DictReader(result.stdout.splitlines(), delimiter="\t"):
        text = (row.get("text") or "").strip()
        try:
            confidence = float(row.get("conf") or -1)
        except ValueError:
            confidence = -1
        if confidence < 45 or len("".join(ch for ch in text if ch.isalnum())) < 2:
            continue
        boxes.append(tuple(int(row[key]) for key in ("left", "top", "width", "height")))
    return boxes


def detect_recurring_text(path, samples=6):
    path = Path(path)
    width, height = _probe_size(path)
    duration = probe_duration(path)
    frame_dir = path.parent / f"{path.stem}_ocr"
    frame_dir.mkdir(exist_ok=True)
    boxes = []
    for index in range(samples):
        timestamp = max(0.0, duration * (index + 1) / (samples + 1))
        frame = frame_dir / f"frame_{index:02d}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
            "-i", str(path), "-frames:v", "1", "-q:v", "2", str(frame)
        ], check=True)
        boxes.append(_ocr_boxes(frame))
    shutil.rmtree(frame_dir, ignore_errors=True)
    return recurring_text_region(boxes, width, height), width, height


def clean_creator_text(src, dst):
    src, dst = Path(src), Path(dst)
    region, width, height = detect_recurring_text(src)
    if not region:
        shutil.copy2(src, dst)
        return None
    x, y, w, h = region
    if w * h > width * height * 0.28:
        raise TextCleanupError("Embedded text covers too much of the image")
    if y + h < height * 0.20:
        crop_y = min(height - 2, y + h + 12)
        if crop_y > height * 0.20:
            raise TextCleanupError("Top text cannot be cropped without damaging the image")
        vf = f"crop=iw:ih-{crop_y}:0:{crop_y}"
    elif y > height * 0.80:
        crop_h = max(2, y - 12)
        if height - crop_h > height * 0.20:
            raise TextCleanupError("Bottom text cannot be cropped without damaging the image")
        vf = f"crop=iw:{crop_h}:0:0"
    else:
        raise TextCleanupError("Embedded text is not on a safely croppable edge")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-an", "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", str(dst)
    ], check=True)
    return region
