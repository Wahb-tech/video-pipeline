import csv
from pathlib import Path
from src.gemini import fallback_plan
from src.main import shuffled_categories
from src.render import choose_clip_start, choose_cut_lengths
from src.strategy import COPIES, choose_variant, performance_score
from src.stock import FORBIDDEN_TERMS, is_strict_dark_luxury


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
