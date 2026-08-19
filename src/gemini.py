import json
import os
import random
import re
import time
import requests
from .config import STYLE_PRESETS, THEME_PRESETS, COPY_VARIANTS

DARK_FEMININE_CATEGORY = "dark_feminine"
DARK_FEMININE_RATIO = 0.18


def balance_dark_feminine(categories, clip_count):
    target = max(1, round(clip_count * DARK_FEMININE_RATIO))
    base = [category for category in categories if category != DARK_FEMININE_CATEGORY]
    if not base:
        base = ["supercar", "watch", "nightlife"]
    while len(base) < clip_count - target:
        candidate = random.choice(base)
        if base and base[-1] == candidate and len(set(base)) > 1:
            continue
        base.append(candidate)
    base = base[:clip_count - target]
    positions = [round((i + 1) * clip_count / (target + 1)) for i in range(target)]
    for offset, position in enumerate(positions):
        base.insert(min(position + offset, len(base)), DARK_FEMININE_CATEGORY)
    return base[:clip_count]


def fallback_plan(style, duration, clip_count, text_mode, theme="mixed_dark", copy_variant="one_day"):
    categories = THEME_PRESETS.get(theme) or STYLE_PRESETS.get(style, STYLE_PRESETS["mixed"])
    chosen = []
    while len(chosen) < clip_count:
        candidate = random.choice(categories)
        if chosen and chosen[-1] == candidate and len(set(categories)) > 1:
            continue
        chosen.append(candidate)
    if style == "dark_luxury":
        chosen = balance_dark_feminine(chosen, clip_count)
    phrase = "" if text_mode == "none" else COPY_VARIANTS.get(copy_variant, "One day.")
    return {
        "concept": theme.replace("_", " ").title(),
        "overlay_text": phrase,
        "categories": chosen,
        "music_mood": style,
        "duration": duration
    }


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Gemini did not return JSON")
    return json.loads(text[start:end + 1])


def generate_plan(style, duration, clip_count, text_mode, theme="mixed_dark", copy_variant="one_day"):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return fallback_plan(style, duration, clip_count, text_mode, theme, copy_variant)

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    allowed = sorted(set(THEME_PRESETS.get(theme, STYLE_PRESETS.get(style, STYLE_PRESETS["mixed"]))))
    prompt = f"""
You are the creative director for a short vertical dark-luxury lifestyle edit for an adult audience.
Style: {style}
Theme: {theme}
Duration: {duration} seconds
Number of visual cuts: {clip_count}
Text mode: {text_mode}

The edit should feel dark, expensive, cinematic and restrained. Favor black supercars at night, cash, watches, suits, luxury restaurants, hotel interiors, Dubai at night, private jets and premium nightlife. People must clearly be adults. Keep it tasteful and non-explicit.

Return ONLY valid JSON:
{{
  "concept": "short concept name",
  "categories": ["exactly {clip_count} category names"],
  "music_mood": "short mood"
}}

Allowed categories for this theme only:
{', '.join(allowed)}

Rules:
- exactly {clip_count} category entries
- avoid the same category twice in a row
- visual variety while staying within the selected theme
- no narration
- no educational script
""".strip()
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}
    }
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            if response.status_code in (429, 500, 502, 503, 504):
                last_error = RuntimeError(f"Gemini temporary error {response.status_code}: {response.text[:300]}")
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            plan = extract_json(text)
            cats = plan.get("categories", [])
            if len(cats) != clip_count or any(c not in allowed for c in cats):
                raise ValueError("Gemini returned invalid categories")
            if style == "dark_luxury":
                cats = balance_dark_feminine(cats, clip_count)
                plan["categories"] = cats
            plan["duration"] = duration
            plan["overlay_text"] = "" if text_mode == "none" else COPY_VARIANTS.get(copy_variant, "One day.")
            return plan
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(2 ** attempt)
    print(f"Gemini unavailable, using fallback plan: {last_error}")
    return fallback_plan(style, duration, clip_count, text_mode, theme, copy_variant)
