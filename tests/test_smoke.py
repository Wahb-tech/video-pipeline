import csv
from pathlib import Path
from src.gemini import fallback_plan, balance_dark_feminine
from src.render import choose_cut_lengths
from src.strategy import choose_variant, performance_score


def test_fallback_plan_count():
    plan = fallback_plan("dark_luxury", 25, 17, "minimal", "dark_cars", "one_day")
    assert len(plan["categories"]) == 17
    assert plan["overlay_text"] == "One day."


def test_dark_feminine_balance():
    categories = balance_dark_feminine(["supercar"] * 17, 17)
    assert len(categories) == 17
    assert categories.count("dark_feminine") == 3


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
    assert variant["copy_variant"] in {"one_day", "soon", "none"}
    assert variant["caption_variant"] in {"choice", "aspiration", "minimal"}
