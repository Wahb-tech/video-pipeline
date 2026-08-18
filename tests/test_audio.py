from src.audio import load_catalog, choose_audio, resolve_audio_file


def test_catalog_has_validated_tracks():
    catalog = load_catalog()
    assert "te_conoci_super_slowed" in catalog
    assert "gozalo_super_slowed" in catalog
    assert catalog["te_conoci_super_slowed"]["preferred_start_sec"] == 8.0


def test_choose_specific_audio():
    audio = choose_audio("dark_cars", "te_conoci_super_slowed")
    assert audio["title"] == "TE CONOCÍ"
    assert audio["audio_id"] == "te_conoci_super_slowed"


def test_missing_audio_file_is_safe():
    track = load_catalog()["gozalo_super_slowed"]
    assert resolve_audio_file(track, "this-folder-does-not-exist") is None


def test_audio_selects_known_segment(tmp_path):
    audio = choose_audio("dark_life", "gozalo_super_slowed", metrics_path=str(tmp_path / "missing.csv"))
    assert audio["selected_start_sec"] in {0.0, 25.0, 35.0, 55.0}
