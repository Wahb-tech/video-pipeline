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


def normalize_clip(src, dst, seconds):
    total = probe_duration(src)
    max_start = max(0.0, total - seconds - 0.1)
    start = random.uniform(0, max_start) if max_start > 0 else 0
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
    run([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{seconds:.3f}",
        "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", str(dst)
    ])


def concat_clips(clips, output):
    list_path = Path(output).with_suffix(".txt")
    list_path.write_text("".join(f"file '{Path(c).resolve()}'\n" for c in clips))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output)])


def make_text_overlay(text, output, position="bottom"):
    """
    Crée un overlay de texte style '69perception' avec fond noir effet pill.
    position: "bottom" (par défaut) ou "center"
    """
    if not text or not text.strip():
        return None
    
    # Nettoyer et formater le texte
    text = text.strip().upper()
    
    # Si le texte est trop long, on le tronque à 5 mots max
    words = text.split()
    if len(words) > 5:
        text = " ".join(words[:5]) + "."
    
    # Dimensions du canvas (1080x1920)
    W, H = 1080, 1920
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    
    # Essayer d'utiliser une police moderne et impactante
    font_paths = [
        "/usr/share/fonts/truetype/msttcorefonts/Helvetica_Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
    ]
    font_path = next((p for p in font_paths if os.path.exists(p)), None)
    
    # Taille de police : 100px (énorme, style impact)
    font = ImageFont.truetype(font_path, 100) if font_path else ImageFont.load_default()
    
    # Calculer la boîte de texte
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    # Padding autour du texte (effet "pill")
    padding_x, padding_y = 60, 30
    box_w = tw + padding_x * 2
    box_h = th + padding_y * 2
    
    # Position en bas (à 78% de la hauteur) ou au centre
    if position == "bottom":
        x = (W - box_w) // 2
        y = int(H * 0.78)  # 78% du bas, laisse respirer en dessous
    else:  # center
        x = (W - box_w) // 2
        y = (H - box_h) // 2
    
    # 1. DESSINER LE FOND NOIR ARRONDI (effet pill)
    radius = 30
    bg = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    bg_draw.rounded_rectangle(
        [(0, 0), (box_w, box_h)],
        radius=radius,
        fill=(0, 0, 0, 180)  # Noir semi-transparent
    )
    canvas.paste(bg, (x, y), bg)
    
    # 2. DESSINER LE TEXTE (sur le fond)
    tx = x + padding_x
    ty = y + padding_y
    
    # Ombre portée (drop shadow) pour plus d'impact
    shadow_offset = 4
    draw.text(
        (tx + shadow_offset, ty + shadow_offset),
        text,
        font=font,
        fill=(0, 0, 0, 100)  # Ombre noire transparente
    )
    
    # Texte principal : blanc pur
    draw.text(
        (tx, ty),
        text,
        font=font,
        fill=(255, 255, 255, 255)  # Blanc pur
    )
    
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
