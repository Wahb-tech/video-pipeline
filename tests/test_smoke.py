import csv
from pathlib import Path
from src.gemini import fallback_plan
from src.main import shuffled_categories
from src.render import choose_clip_start, choose_cut_lengths
from src.strategy import COPIES, choose_variant, performance_score
from src.stock import FORBIDDEN_TERMS, STOCK_BLOCKED_CATEGORIES, coverr_search, is_real_footage, is_strict_dark_luxury, score
from src.authorized_video import _cookie_args, choose_authorized_clip, configured_sources, configured_urls, download_authorized_library
from src.text_cleanup import recurring_text_region


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


def test_cgi_and_game_footage_are_rejected():
    assert not is_real_footage({"tags": "3D CGI luxury watch animation"})
    assert not is_real_footage({"tags": "dark supercar video game render"})
    assert is_real_footage({"tags": "real cinematic Rolls Royce at night"})


def test_weak_stock_categories_are_blocked():
    assert STOCK_BLOCKED_CATEGORIES == {"watch", "cash"}
    assert not is_real_footage({"tags": "futuristic concept car luxury simulation"})


def test_authorized_urls_accept_multiline_secret(monkeypatch):
    monkeypatch.setenv("AUTHORIZED_VIDEO_URLS", "https://youtu.be/a\nhttps://youtu.be/b")
    assert configured_urls() == ["https://youtu.be/a", "https://youtu.be/b"]


def test_authorized_handles_become_instagram_reel_feeds(monkeypatch):
    monkeypatch.delenv("AUTHORIZED_VIDEO_URLS", raising=False)
    monkeypatch.delenv("AUTHORIZED_TEXT_VIDEO_URLS", raising=False)
    monkeypatch.delenv("AUTHORIZED_CREATOR_HANDLES", raising=False)
    monkeypatch.setenv("AUTHORIZED_TEXT_CREATOR_HANDLES", "@theluxevora\n369godsplan, crestvalue")
    assert configured_sources() == [
        ("https://www.instagram.com/theluxevora/reels/", True),
        ("https://www.instagram.com/369godsplan/reels/", True),
        ("https://www.instagram.com/crestvalue/reels/", True),
    ]


def test_authorized_cookie_file_is_passed_to_downloaders(monkeypatch, tmp_path):
    cookie_file = tmp_path / "instagram-cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setenv("AUTHORIZED_COOKIES_FILE", str(cookie_file))
    assert _cookie_args() == ["--cookies", str(cookie_file)]


def test_missing_authorized_cookie_file_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTHORIZED_COOKIES_FILE", str(tmp_path / "missing.txt"))
    assert _cookie_args() == []


def test_explicit_platform_handles(monkeypatch):
    monkeypatch.delenv("AUTHORIZED_VIDEO_URLS", raising=False)
    monkeypatch.delenv("AUTHORIZED_TEXT_VIDEO_URLS", raising=False)
    monkeypatch.delenv("AUTHORIZED_TEXT_CREATOR_HANDLES", raising=False)
    monkeypatch.setenv("AUTHORIZED_CREATOR_HANDLES", "youtube:noirwealthlifestyle\ninstagram:5relux")
    assert configured_sources() == [
        ("https://www.youtube.com/@noirwealthlifestyle/videos", False),
        ("https://www.instagram.com/5relux/reels/", False),
    ]


def test_unavailable_authorized_source_does_not_abort(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTHORIZED_VIDEO_URLS", "https://youtube.com/@missing/videos")
    monkeypatch.delenv("AUTHORIZED_TEXT_VIDEO_URLS", raising=False)
    monkeypatch.delenv("AUTHORIZED_CREATOR_HANDLES", raising=False)
    monkeypatch.delenv("AUTHORIZED_TEXT_CREATOR_HANDLES", raising=False)

    class Result:
        returncode = 1

    monkeypatch.setattr("src.authorized_video.subprocess.run", lambda *args, **kwargs: Result())
    assert download_authorized_library(tmp_path) == []


def test_text_sources_are_marked_for_cleanup(monkeypatch):
    monkeypatch.setenv("AUTHORIZED_VIDEO_URLS", "https://youtu.be/clean")
    monkeypatch.setenv("AUTHORIZED_TEXT_VIDEO_URLS", "https://youtu.be/text")
    assert configured_sources() == [
        ("https://youtu.be/clean", False),
        ("https://youtu.be/text", True),
    ]


def test_recurring_text_region_ignores_one_frame_text():
    frames = [[(100, 100, 200, 50)], [], [], []]
    assert recurring_text_region(frames, 1080, 1920) is None


def test_recurring_text_region_finds_static_overlay():
    frames = [
        [(300, 850, 400, 80)],
        [(310, 855, 390, 78)],
        [(305, 852, 395, 82)],
        [],
    ]
    region = recurring_text_region(frames, 1080, 1920)
    assert region is not None
    assert region[0] < 300
    assert region[2] > 400


def test_authorized_rotation_prefers_less_used_video(monkeypatch):
    monkeypatch.setattr("src.authorized_video.random.random", lambda: 0.0)
    items = [
        {"provider": "authorized_creator", "id": "a"},
        {"provider": "authorized_creator", "id": "b"},
    ]
    chosen = choose_authorized_clip(items, {}, {"authorized_creator:a": 2}, 0)
    assert chosen["id"] == "b"
