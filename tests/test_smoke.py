from src.gemini import fallback_plan
from src.render import choose_cut_lengths


def test_fallback_plan_count():
    plan = fallback_plan("mixed", 15, 10, "minimal")
    assert len(plan["categories"]) == 10


def test_cut_lengths_sum():
    cuts = choose_cut_lengths(15, 10, 120)
    assert abs(sum(cuts) - 15) < 1e-6
