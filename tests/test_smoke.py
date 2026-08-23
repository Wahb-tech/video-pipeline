import csv
from pathlib import Path
from src.gemini import fallback_plan
from src.main import shuffled_categories
from src.render import choose_clip_start, choose_cut_lengths
from src.strategy import COPIES, choose_variant, performance_score
from src.stock import FORBIDDEN_TERMS, coverr_search, is_strict_dark_luxury, score


def test_fallback_plan_count():
    plan = fallback_plan("dark_luxury", 25, 17, "minimal", "dark_cars", "one_day")
    assert len(plan["categories"]) == 17
    assert plan["overlay_text"] == "One day."


def test_dark_luxury_limits_feminine_clips():
    plan = fallback_plan("dark_luxury", 25, 17, "minimal", "mixed_dark", "soon")
    assert plan["categories"].count("dark_feminine") <= 2
    assert not ({"business", "nightlife", "restaurant", "beach", "pool"} & set(plan["categories"]))


def test_swimwear_is_context_checked_not_globally_forbidden():
    assert "bikini" not in FORBIDDEN_TERMS
    assert "swimsuit" not in FORBIDDEN_TERMS


def test_abstract_water_clip_is_rejected():
    item = {"page_url": "https://example.com/luxury-villa-water-fountain-close-up", "tags": "water, stone, fountain"}
    assert not is_strict_dark_luxury(item, "villa")


def test_category_without_explicit_wealth_is_rejected():
    item = {"page_url": "https://example.com/ordinary-villa", "tags": "villa, house"}
    assert not is_strict_dark_luxury(item, "villa")


def test_explicit_dark_luxury_clip_is_accepted():
    item = {"page_url": "https://example.com/luxury-supercar-night", "tags": "luxury, lamborghini, night"}
    assert is_strict_dark_luxury(item, "supercar")


def test_cut_lengths_sum():
    cuts = choose_cut_lengths(25, 17, 100)
    assert abs(sum(cuts) - 25) < 1e-6


def test_performance_score_positive():
    score = performance_score({
        "views": "1000",
        "likes": "50",
        "comments": "10",
        "shares": "5",
        "follows": "3",
        "completion_rate": "60"
    })
    assert score > 0


def test_strategy_works_without_metrics(tmp_path):
    path = tmp_path / "missing.csv"
    variant = choose_variant(str(path))
    assert variant["theme"] in {"dark_cars", "money", "dark_life", "mixed_dark"}
    assert variant["copy_variant"] in set(COPIES)
    assert variant["caption_variant"] in {"choice", "aspiration", "minimal"}


def test_automatic_strategy_never_disables_overlay():
    assert "none" not in COPIES
    for _ in range(30):
        assert choose_variant()["copy_variant"] in set(COPIES)


def test_automatic_strategy_does_not_repeat_last_copy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    (data / "generated.csv").write_text("copy_variant\none_day\n", encoding="utf-8")
    for _ in range(30):
        assert choose_variant()["copy_variant"] != "one_day"


def test_shuffled_categories_preserves_content():
    original = ["supercar", "cash", "watch", "villa", "supercar"]
    shuffled = shuffled_categories(original)
    assert sorted(shuffled) == sorted(original)
    assert all(a != b for a, b in zip(shuffled, shuffled[1:]))


def test_reused_clip_moves_to_a_different_segment():
    for _ in range(30):
        start = choose_clip_start(30.0, 2.0, [3.0, 10.0, 17.0])
        assert min(abs(start - old) for old in [3.0, 10.0, 17.0]) > 2.0


def test_coverr_search_normalizes_video(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"hits": [{
                "id": "abc123",
                "title": "Luxury Lamborghini at Night",
                "description": "A dark premium supercar scene",
                "tags": ["luxury", "lamborghini", "night"],
                "duration": 8.5,
                "max_width": 2160,
                "max_height": 3840,
                "urls": {"mp4_download": "https://storage.coverr.co/video.mp4"},
            }]}

    monkeypatch.setenv("COVERR_API_KEY", "test-key")
    monkeypatch.setattr("src.stock.requests.get", lambda *args, **kwargs: Response())
    coverr_search.cache_clear()
    item = coverr_search("luxury car")[0]
    assert item["provider"] == "coverr"
    assert item["height"] == 3840
    assert item["url"].endswith("video.mp4")
    assert is_strict_dark_luxury(item, "supercar")
    coverr_search.cache_clear()


def test_provider_rotation_penalizes_overused_provider(monkeypatch):
    monkeypatch.setattr("src.stock.random.random", lambda: 0.0)
    pexels = {"provider": "pexels", "width": 1080, "height": 1920, "duration": 8}
    coverr = {"provider": "coverr", "width": 1080, "height": 1920, "duration": 8}
    usage = {"pexels": 50, "coverr": 0, "pixabay": 20}
    assert score(coverr, provider_usage=usage) > score(pexels, provider_usage=usage)
