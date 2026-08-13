import json
import os
import random
import re
import requests
from .config import STYLE_PRESETS, FALLBACK_TEXTS


def fallback_plan(style, duration, clip_count, text_mode):
    categories = STYLE_PRESETS.get(style, STYLE_PRESETS["mixed"])
    chosen = [random.choice(categories) for _ in range(clip_count)]
    phrase = "" if text_mode == "none" else random.choice(FALLBACK_TEXTS)
    return {
        "concept": style.replace("_", " ").title(),
        "overlay_text": phrase,
        "caption": phrase or "Luxury lifestyle edit.",
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


def generate_plan(style, duration, clip_count, text_mode):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return fallback_plan(style, duration, clip_count, text_mode)

    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    prompt = f"""
You are the creative director for a short vertical luxury-lifestyle edit intended for an adult audience.
Style: {style}
Duration: {duration} seconds
Number of visual cuts: {clip_count}
Text mode: {text_mode}

The visual universe is aspirational luxury: yachts, Dubai rooftops, supercars, five-star hotels, private jets, villas, beaches, pools, nightlife, watches and stylish adult models. Any people referenced must clearly be adults. Keep it tasteful and non-explicit.

Return ONLY valid JSON with this schema:
{{
  "concept": "short concept name",
  "overlay_text": "0-7 words, or empty string",
  "caption": "one short social caption",
  "categories": ["exactly {clip_count} category names"],
  "music_mood": "short mood"
}}

Allowed category names only:
yacht, pool, dubai, supercar, private_jet, villa, beach, nightlife, watch, hotel, monaco, restaurant

Rules:
- categories must contain exactly {clip_count} entries
- avoid using the same category twice in a row
- create visual variety
- if text_mode is none, overlay_text must be empty
- if text_mode is minimal, overlay_text must be extremely short
- no narration and no educational script
""".strip()
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"}
    }
    response = requests.post(
        endpoint,
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=60
    )
    
    if not response.ok:
        raise RuntimeError(
            f"Gemini API error {response.status_code}: {response.text}"
        )
    
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    plan = extract_json(text)
    cats = plan.get("categories", [])
    if len(cats) != clip_count:
        return fallback_plan(style, duration, clip_count, text_mode)
    plan["duration"] = duration
    return plan
