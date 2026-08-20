import csv
from pathlib import Path
from src.gemini import fallback_plan
from src.render import choose_cut_lengths
from src.strategy import COPIES, choose_variant, performance_score


def test_fallback_plan_count():
    plan = fallback_plan("dark_luxury", 25, 17, "minimal", "dark_cars", "one_day")
    assert len(plan["categories"]) == 17
    assert plan["overlay_text"] == "One day."


def test_dark_luxury_contains_no_generic_people_categories():
    plan = fallback_plan("dark_luxury", 25, 17, "minimal", "mixed_dark", "soon")
    assert not ({"dark_feminine", "business", "nightlife", "restaurant", "beach", "pool"} & set(plan["categories"]))


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
