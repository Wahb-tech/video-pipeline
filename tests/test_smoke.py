import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import pytest
from src.gemini import fallback_plan
from src.config import COPY_VARIANTS
from src.main import choose_cleanup_fallback, shuffled_categories
from src.render import HIGH_QUALITY_VIDEO_ARGS, INTERMEDIATE_VIDEO_ARGS, _behavior_novelty, _overlay_lines, _should_ai_upscale, _snap_cut_times, choose_clip_start, choose_cut_lengths
from src.strategy import COPIES, choose_variant, performance_score
from src.stock import FORBIDDEN_TERMS, STOCK_BLOCKED_CATEGORIES, coverr_search, is_real_footage, is_strict_dark_luxury, score
from src.authorized_video import _cookie_args, _download_with_ytdlp, _instagram_username, _is_direct_instagram_media, authorized_quality_penalty, choose_authorized_clip, configured_sources, configured_urls, download_authorized_library
from src.text_cleanup import TextCleanupError, clean_creator_text, recurring_text_region
from src.zoop_metrics import (
    METRIC_FIELDS,
    PUBLICATION_FIELDS,
    best_candidate,
    build_metric_row,
    candidates_from_payloads,
    collect,
    discover_publications,
    due_window,
    post_record_from_responses,
    read_rows,
    redact_payload,
    upsert_row,
    write_rows,
)


def test_fallback_plan_count():
    plan = fallback_plan("dark_luxury", 25, 17, "minimal", "dark_cars", "pov_relationship")
    assert len(plan["categories"]) == 17
    assert plan["overlay_text"] in COPY_VARIANTS["pov_relationship"]


def test_dark_luxury_limits_feminine_clips():
    plan = fallback_plan("dark_luxury", 25, 17, "minimal", "mixed_dark", "future_self")
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


def test_music_cuts_snap_to_nearby_energy_peaks():
    novelty = [0.0] * 101
    for frame, strength in [(18, 2.0), (42, 3.0), (61, 4.0), (82, 2.5)]:
        novelty[frame] = strength
    cuts = _snap_cut_times(novelty, 0.1, 10.0, 5, search_radius=0.7)
    assert cuts == pytest.approx([1.8, 4.2, 6.1, 8.2])


def test_music_behavior_prefers_section_change_over_isolated_spike():
    energy = [0.2] * 50 + [0.8] * 50
    bass = [0.2] * 50 + [0.7] * 50
    texture = [0.3] * 50 + [0.6] * 50
    energy[20] = 1.0
    novelty = _behavior_novelty(energy, bass, texture, window=10)
    assert novelty[50] > novelty[20]


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
    (data / "generated.csv").write_text("copy_variant\npov_relationship\n", encoding="utf-8")
    for _ in range(30):
        assert choose_variant()["copy_variant"] != "pov_relationship"


def test_copy_bank_contains_many_non_generic_hooks():
    hooks = [text for key, values in COPY_VARIANTS.items() if key != "none" for text in values]
    assert len(hooks) >= 75
    assert sum(text.startswith("POV:") for text in hooks) >= 25
    assert {"identity_shift", "legacy"} <= set(COPY_VARIANTS)


def test_long_overlay_is_split_into_two_balanced_lines():
    lines = _overlay_lines("POV: SHE WANTS DOUBLE TEXTS. YOU WANT DOUBLE THE INCOME.")
    assert len(lines) == 2
    assert abs(len(lines[0]) - len(lines[1])) <= 12


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


def test_stock_quality_bonus_requires_true_1080_width(monkeypatch):
    monkeypatch.setattr("src.stock.random.random", lambda: 0.0)
    vertical_720 = {"provider": "pexels", "width": 720, "height": 1280, "duration": 8}
    vertical_1080 = {"provider": "pexels", "width": 1080, "height": 1920, "duration": 8}
    assert score(vertical_1080) == score(vertical_720) + 2


def test_authorized_vertical_video_is_preferred_over_landscape():
    vertical = {"width": 1080, "height": 1920}
    landscape = {"width": 1920, "height": 1080}
    assert authorized_quality_penalty(vertical) < authorized_quality_penalty(landscape)


def test_authorized_true_hd_is_strongly_preferred_over_720p():
    hd = {"width": 1080, "height": 1920, "fps": 30, "bit_rate": 5_000_000}
    compressed = {"width": 720, "height": 1280, "fps": 30, "bit_rate": 1_200_000}
    assert authorized_quality_penalty(compressed) - authorized_quality_penalty(hd) >= 20


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


def test_instagram_username_is_extracted_from_reels_url():
    assert _instagram_username("https://www.instagram.com/noirwealthlifestyle/reels/") == "noirwealthlifestyle"


def test_direct_instagram_media_is_detected_without_matching_profile_feed():
    assert _is_direct_instagram_media("https://www.instagram.com/crestvalue/reel/Db-_Jq9zX9T/")
    assert _is_direct_instagram_media("https://www.instagram.com/creator/p/abc123/")
    assert not _is_direct_instagram_media("https://www.instagram.com/crestvalue/reels/")


def test_authorized_cookie_file_is_passed_to_downloaders(monkeypatch, tmp_path):
    cookie_file = tmp_path / "instagram-cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setenv("AUTHORIZED_COOKIES_FILE", str(cookie_file))
    assert _cookie_args() == ["--cookies", str(cookie_file)]


def test_missing_authorized_cookie_file_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTHORIZED_COOKIES_FILE", str(tmp_path / "missing.txt"))
    assert _cookie_args() == []


def test_ytdlp_does_not_filter_direct_instagram_reels_by_duration(monkeypatch, tmp_path):
    commands = []

    class Result:
        returncode = 1

    def fake_run(command, check=False):
        commands.append(command)
        return Result()

    monkeypatch.setattr("src.authorized_video.subprocess.run", fake_run)
    assert not _download_with_ytdlp("https://www.instagram.com/creator/reel/short/", tmp_path, "12")
    assert "--match-filter" not in commands[0]


def test_ytdlp_keeps_duration_filter_for_other_sources(monkeypatch, tmp_path):
    commands = []

    class Result:
        returncode = 1

    def fake_run(command, check=False):
        commands.append(command)
        return Result()

    monkeypatch.setattr("src.authorized_video.subprocess.run", fake_run)
    assert not _download_with_ytdlp("https://youtube.com/@creator/videos", tmp_path, "12")
    match_filter = commands[0][commands[0].index("--match-filter") + 1]
    assert match_filter == "duration >= 8 & duration <= 1800"


def test_ytdlp_requests_best_available_source_quality(monkeypatch, tmp_path):
    commands = []

    class Result:
        returncode = 1

    def fake_run(command, check=False):
        commands.append(command)
        return Result()

    monkeypatch.setattr("src.authorized_video.subprocess.run", fake_run)
    assert not _download_with_ytdlp("https://www.instagram.com/creator/reel/example/", tmp_path, "12")
    command = commands[0]
    assert command[command.index("-f") + 1] == "bv*+ba/b"
    assert command[command.index("-S") + 1] == "res,fps,br"


def test_render_uses_high_quality_encoding():
    assert HIGH_QUALITY_VIDEO_ARGS == [
        "-c:v", "libx264", "-preset", "slow", "-crf", "12",
        "-profile:v", "high", "-level:v", "4.1",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart"
    ]
    assert INTERMEDIATE_VIDEO_ARGS[INTERMEDIATE_VIDEO_ARGS.index("-crf") + 1] == "10"


def test_ai_upscale_only_targets_sub_1080_portrait(monkeypatch, tmp_path):
    script = tmp_path / "inference_realesrgan.py"
    script.write_text("")
    monkeypatch.setenv("ENABLE_AI_UPSCALE", "true")
    monkeypatch.setenv("REALESRGAN_SCRIPT", str(script))
    assert _should_ai_upscale(720, 1280)
    assert not _should_ai_upscale(1080, 1920)
    assert not _should_ai_upscale(1920, 1080)
    assert not _should_ai_upscale(480, 854)


def test_text_cleanup_failure_falls_back_to_clean_authorized_clip(monkeypatch):
    monkeypatch.setattr("src.authorized_video.random.random", lambda: 0.0)
    items = [
        {"provider": "authorized_creator", "id": "text", "cleanup_text": True},
        {"provider": "authorized_creator", "id": "clean", "cleanup_text": False},
    ]
    chosen = choose_cleanup_fallback(items, "text", {}, {}, 4)
    assert chosen["id"] == "clean"


def test_cleanup_fallback_never_reuses_a_clip_in_same_reel(monkeypatch):
    monkeypatch.setattr("src.authorized_video.random.random", lambda: 0.0)
    items = [
        {"provider": "authorized_creator", "id": "text", "cleanup_text": True},
        {"provider": "authorized_creator", "id": "used", "cleanup_text": False},
        {"provider": "authorized_creator", "id": "fresh", "cleanup_text": False},
    ]
    chosen = choose_cleanup_fallback(
        items, "text", {}, {}, 4, {"authorized_creator:used"}
    )
    assert chosen["id"] == "fresh"


def test_cleanup_fallback_can_reuse_when_clean_pool_is_exhausted(monkeypatch):
    monkeypatch.setattr("src.authorized_video.random.random", lambda: 0.0)
    items = [
        {"provider": "authorized_creator", "id": "text", "cleanup_text": True},
        {"provider": "authorized_creator", "id": "used", "cleanup_text": False},
    ]
    excluded = {"authorized_creator:used"}
    assert choose_cleanup_fallback(items, "text", {}, {}, 14, excluded) is None
    chosen = choose_cleanup_fallback(items, "text", {}, {}, 14)
    assert chosen["id"] == "used"


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


def test_noir_wealth_source_is_never_marked_for_cleanup(monkeypatch):
    url = "https://www.instagram.com/noirwealthlifestyle/reel/example/"
    monkeypatch.setenv("AUTHORIZED_VIDEO_URLS", url)
    monkeypatch.delenv("AUTHORIZED_TEXT_VIDEO_URLS", raising=False)
    monkeypatch.delenv("AUTHORIZED_CREATOR_HANDLES", raising=False)
    monkeypatch.delenv("AUTHORIZED_TEXT_CREATOR_HANDLES", raising=False)
    assert configured_sources() == [(url, False)]


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


def test_center_text_is_rejected_instead_of_blurred(monkeypatch, tmp_path):
    src = tmp_path / "source.mp4"
    dst = tmp_path / "clean.mp4"
    src.write_bytes(b"video")
    monkeypatch.setattr(
        "src.text_cleanup.detect_recurring_text",
        lambda path: ((300, 800, 400, 100), 1080, 1920),
    )
    with pytest.raises(TextCleanupError, match="safely croppable"):
        clean_creator_text(src, dst)
    assert not dst.exists()


def test_authorized_rotation_prefers_less_used_video(monkeypatch):
    monkeypatch.setattr("src.authorized_video.random.random", lambda: 0.0)
    items = [
        {"provider": "authorized_creator", "id": "a"},
        {"provider": "authorized_creator", "id": "b"},
    ]
    chosen = choose_authorized_clip(items, {}, {"authorized_creator:a": 2}, 0)
    assert chosen["id"] == "b"


def test_authorized_clip_is_unique_inside_one_reel(monkeypatch):
    monkeypatch.setattr("src.authorized_video.random.random", lambda: 0.0)
    items = [
        {"provider": "authorized_creator", "id": "a"},
        {"provider": "authorized_creator", "id": "b"},
    ]
    first = choose_authorized_clip(items, {}, {}, 0)
    excluded = {f'{first["provider"]}:{first["id"]}'}
    second = choose_authorized_clip(items, {}, {}, 1, excluded)
    assert second["id"] != first["id"]
    assert choose_authorized_clip(
        items, {}, {}, 2, {"authorized_creator:a", "authorized_creator:b"}
    ) is None


def test_authorized_rotation_prefers_true_1080_source(monkeypatch):
    monkeypatch.setattr("src.authorized_video.random.random", lambda: 0.0)
    items = [
        {"provider": "authorized_creator", "id": "low", "width": 480, "height": 864},
        {"provider": "authorized_creator", "id": "hd", "width": 1080, "height": 1920},
    ]
    assert choose_authorized_clip(items, {}, {}, 0)["id"] == "hd"


def test_authorized_rotation_keeps_low_resolution_as_fallback(monkeypatch):
    monkeypatch.setattr("src.authorized_video.random.random", lambda: 0.0)
    items = [
        {"provider": "authorized_creator", "id": "low", "width": 480, "height": 864},
        {"provider": "authorized_creator", "id": "hd", "width": 1080, "height": 1920},
    ]
    excluded = {"authorized_creator:hd"}
    assert choose_authorized_clip(items, {}, {}, 1, excluded)["id"] == "low"


def test_zoop_publish_response_is_linked_to_experiment():
    responses = [{
        "url": "https://api-v2.influencerindex.com/posts",
        "payload": {
            "data": {
                "post": {
                    "id": 128854,
                    "caption": "Discipline. Income. Freedom.",
                }
            }
        },
    }]
    record = post_record_from_responses(
        responses,
        "experiment-1",
        "Discipline. Income. Freedom.",
        "2026-09-03T10:00:00+00:00",
        datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc),
    )
    assert record["post_id"] == "128854"
    assert record["post_url"] == "https://app.zoop.club/profile/post/128854"
    assert record["experiment_id"] == "experiment-1"


def test_zoop_nested_insights_are_normalized_and_matched():
    payloads = [{
        "url": "https://api-v2.influencerindex.com/posts/128854",
        "payload": {
            "post": {
                "id": 128854,
                "caption": "Build in silence.",
                "insights": {
                    "viewCount": "1.2k",
                    "likesCount": 81,
                    "commentCount": 7,
                    "shareCount": 4,
                },
            }
        },
    }]
    candidates = candidates_from_payloads(payloads)
    selected = best_candidate(candidates, {
        "post_id": "128854",
        "caption": "Build in silence.",
    })
    assert selected["views"] == 1200
    assert selected["likes"] == 81
    assert selected["comments"] == 7
    assert selected["shares"] == 4


def test_zoop_metric_windows_are_collected_once():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    publication = {
        "experiment_id": "experiment-1",
        "published_at": (now - timedelta(hours=80)).isoformat(),
    }
    assert due_window(publication, [], now) == "72h"
    existing = [{"experiment_id": "experiment-1", "measurement_window": "72h"}]
    assert due_window(publication, existing, now) == ""


def test_zoop_latest_metric_upsert_does_not_duplicate_experiment(tmp_path):
    path = tmp_path / "metrics.csv"
    first = {field: "" for field in METRIC_FIELDS}
    first.update({"experiment_id": "experiment-1", "views": 100, "measurement_window": "24h"})
    second = {**first, "views": 500, "measurement_window": "72h"}
    upsert_row(path, METRIC_FIELDS, first, ("experiment_id",))
    upsert_row(path, METRIC_FIELDS, second, ("experiment_id",))
    rows = read_rows(path)
    assert len(rows) == 1
    assert rows[0]["views"] == "500"
    assert rows[0]["measurement_window"] == "72h"


def test_zoop_metric_row_inherits_generated_experiment_factors():
    publication = {
        "experiment_id": "experiment-1",
        "published_at": "2026-09-03T10:00:00+00:00",
        "post_url": "https://app.zoop.club/profile/post/128854",
    }
    generated = {"experiment-1": {
        "theme": "dark_life",
        "copy_variant": "discipline",
        "caption_variant": "minimal",
        "audio_id": "montagem_coma_slowed",
        "audio_start_sec": "12.0",
        "audio_segment": "montagem_coma_slowed@12.0",
    }}
    candidate = {
        "views": 900,
        "likes": 50,
        "comments": 3,
        "shares": 2,
        "source_url": "https://api-v2.influencerindex.com/posts/128854",
    }
    row = build_metric_row(
        publication,
        candidate,
        generated,
        "24h",
        datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert row["theme"] == "dark_life"
    assert row["audio_id"] == "montagem_coma_slowed"
    assert row["measurement_window"] == "24h"


def test_zoop_existing_post_is_backfilled_from_unique_caption():
    candidates = [{
        "post_id": "128854",
        "post_url": "/profile/post/128854",
        "caption": "You fall to the routine.",
        "published_at": "2026-09-01T08:00:00Z",
        "source_url": "https://api-v2.influencerindex.com/feed",
    }]
    generated = [{
        "experiment_id": "experiment-old",
        "caption": "You fall to the routine.",
        "created_at": "2026-09-01T07:30:00Z",
    }]
    rows = discover_publications(
        candidates,
        generated,
        [],
        datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0]["experiment_id"] == "experiment-old"
    assert rows[0]["post_url"] == "https://app.zoop.club/profile/post/128854"


def test_zoop_raw_diagnostics_redact_private_fields():
    payload = {
        "post": {"id": 1, "views": 20},
        "user": {"email": "private@example.com", "access_token": "secret"},
    }
    redacted = redact_payload(payload)
    assert redacted["post"]["views"] == 20
    assert redacted["user"]["email"] == "[redacted]"
    assert redacted["user"]["access_token"] == "[redacted]"


def test_zoop_collector_updates_snapshot_and_latest_metric(monkeypatch, tmp_path):
    fixed_now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    publications = tmp_path / "published.csv"
    generated = tmp_path / "generated.csv"
    metrics = tmp_path / "metrics.csv"
    snapshots = tmp_path / "snapshots.csv"
    write_rows(publications, PUBLICATION_FIELDS, [{
        "experiment_id": "experiment-1",
        "post_id": "128854",
        "post_url": "https://app.zoop.club/profile/post/128854",
        "caption": "Build in silence.",
        "published_at": "2026-09-01T10:00:00+00:00",
    }])
    generated.write_text(
        "experiment_id,theme,copy_variant,caption_variant,audio_id,audio_start_sec,audio_segment,caption\n"
        "experiment-1,dark_life,discipline,minimal,coma,12.0,coma@12.0,Build in silence.\n",
        encoding="utf-8",
    )
    payloads = [{
        "url": "https://api-v2.influencerindex.com/posts/128854",
        "payload": {"post": {
            "id": 128854,
            "caption": "Build in silence.",
            "views": 1500,
            "likes": 100,
            "comments": 8,
            "shares": 5,
        }},
    }]
    monkeypatch.setattr("src.zoop_metrics.utc_now", lambda: fixed_now)
    monkeypatch.setattr(
        "src.zoop_metrics.capture_profile_payloads",
        lambda state, profile_url, raw: payloads,
    )
    args = SimpleNamespace(
        state="state.json",
        profile_url="https://app.zoop.club/profile",
        publications=str(publications),
        generated=str(generated),
        metrics=str(metrics),
        snapshots=str(snapshots),
        raw=str(tmp_path / "raw.json"),
    )
    assert collect(args) == 1
    assert read_rows(metrics)[0]["views"] == "1500"
    assert read_rows(metrics)[0]["measurement_window"] == "72h"
    assert len(read_rows(snapshots)) == 1
    collect,
