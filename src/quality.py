def _number(item, name):
    try:
        return float(item.get(name) or 0)
    except (TypeError, ValueError):
        return 0.0


def source_quality_score(item):
    """Metadata quality score used before an expensive render/download."""
    width = _number(item, "width")
    height = _number(item, "height")
    fps = _number(item, "fps")
    bit_rate = _number(item, "bit_rate")
    if not width or not height:
        return 45.0
    short, long = min(width, height), max(width, height)
    score = 20.0
    score += min(38.0, 38.0 * short / 1080.0)
    score += min(18.0, 18.0 * long / 1920.0)
    score += 8.0 if height > width else 2.0
    score += 8.0 if not fps else min(8.0, 8.0 * fps / 30.0)
    score += 8.0 if not bit_rate else min(8.0, 8.0 * bit_rate / 4_000_000.0)
    return round(min(100.0, score), 2)


def passes_quality_gate(item):
    width = _number(item, "width")
    height = _number(item, "height")
    fps = _number(item, "fps")
    bit_rate = _number(item, "bit_rate")
    if width and height and (min(width, height) < 540 or max(width, height) < 960):
        return False
    if fps and fps < 20:
        return False
    if bit_rate and bit_rate < 600_000:
        return False
    return source_quality_score(item) >= 50.0
