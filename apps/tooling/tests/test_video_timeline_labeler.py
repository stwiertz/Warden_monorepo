"""Unit tests for video_timeline_labeler pure helpers (no GUI)."""

import os

from tools.video_timeline_labeler import (
    _backfill_between,
    _format_hhmmss,
    _is_valid_hud_version,
    _next_seq,
    _output_path,
    _snap_to_keyframe,
    _undo,
)


# ---------------------------------------------------------------------------
# _snap_to_keyframe
# ---------------------------------------------------------------------------


PTS = [0.0, 2.0, 4.0, 6.0]


def test_snap_nearest_picks_closest():
    assert _snap_to_keyframe(2.7, PTS, "nearest") == 2.0


def test_snap_prior_picks_largest_at_or_before():
    assert _snap_to_keyframe(2.7, PTS, "prior") == 2.0


def test_snap_after_picks_smallest_at_or_after():
    assert _snap_to_keyframe(2.7, PTS, "after") == 4.0


def test_snap_nearest_tie_breaks_to_prior():
    # Equidistant from 4.0 and 6.0; tie -> prior (4.0).
    assert _snap_to_keyframe(5.0, PTS, "nearest") == 4.0


def test_snap_prior_out_of_range_returns_none():
    assert _snap_to_keyframe(-1.0, PTS, "prior") is None


def test_snap_after_out_of_range_returns_none():
    assert _snap_to_keyframe(99.0, PTS, "after") is None


def test_snap_empty_list_returns_none():
    assert _snap_to_keyframe(1.0, [], "nearest") is None


def test_snap_unknown_policy_returns_none():
    assert _snap_to_keyframe(1.0, PTS, "bogus") is None


# ---------------------------------------------------------------------------
# _output_path
# ---------------------------------------------------------------------------


def test_output_path_sub_one_hour_zero_pads_hours():
    p = _output_path("/out", "2.0", "lobby", 1, 12.0)
    assert p == os.path.join("/out", "v2.0", "lobby", "001_00h00m12s.png")


def test_output_path_over_one_hour_video():
    pts = 1 * 3600 + 5 * 60 + 23  # 01:05:23
    p = _output_path("/out", "1.0", "horizon", 42, pts)
    assert p == os.path.join("/out", "v1.0", "horizon", "042_01h05m23s.png")


def test_output_path_seq_pads_to_three_digits():
    p = _output_path("/o", "2.0", "score", 7, 0.0)
    assert "/007_" in p.replace(os.sep, "/")


def test_format_hhmmss_negative_clamps_to_zero():
    assert _format_hhmmss(-1.0) == "00h00m00s"


# ---------------------------------------------------------------------------
# _next_seq
# ---------------------------------------------------------------------------


def test_next_seq_empty_dir_returns_one(tmp_path):
    assert _next_seq(str(tmp_path)) == 1


def test_next_seq_returns_max_plus_one(tmp_path):
    (tmp_path / "001_00m12s.png").write_bytes(b"")
    (tmp_path / "002_00m34s.png").write_bytes(b"")
    assert _next_seq(str(tmp_path)) == 3


def test_next_seq_skips_non_conforming(tmp_path):
    (tmp_path / "001_00m12s.png").write_bytes(b"")
    (tmp_path / "random.png").write_bytes(b"")
    (tmp_path / "_no_seq_prefix.png").write_bytes(b"")
    assert _next_seq(str(tmp_path)) == 2


def test_next_seq_missing_dir_returns_one(tmp_path):
    assert _next_seq(str(tmp_path / "does_not_exist")) == 1


# ---------------------------------------------------------------------------
# _undo
# ---------------------------------------------------------------------------


def test_undo_removes_existing_file(tmp_path):
    f = tmp_path / "001_00m12s.png"
    f.write_bytes(b"x")
    assert _undo(str(f)) is True
    assert not f.exists()


def test_undo_none_path_returns_false():
    assert _undo(None) is False


def test_undo_missing_file_returns_false(tmp_path):
    assert _undo(str(tmp_path / "missing.png")) is False


def test_undo_then_next_seq_reuses_freed_number(tmp_path):
    (tmp_path / "001_00m12s.png").write_bytes(b"")
    f2 = tmp_path / "002_00m34s.png"
    f2.write_bytes(b"")
    assert _undo(str(f2)) is True
    # Freed seq number is 2; next allocation reuses it.
    assert _next_seq(str(tmp_path)) == 2


def test_undo_double_call_is_noop(tmp_path):
    f = tmp_path / "001_00m12s.png"
    f.write_bytes(b"x")
    assert _undo(str(f)) is True
    assert _undo(str(f)) is False  # second call: file gone, no-op


# ---------------------------------------------------------------------------
# _is_valid_hud_version
# ---------------------------------------------------------------------------


def test_hud_version_accepts_dotted_numeric():
    assert _is_valid_hud_version("1.0") is True
    assert _is_valid_hud_version("2.0") is True
    assert _is_valid_hud_version("1.5") is True


def test_hud_version_accepts_alphanumeric_with_separators():
    assert _is_valid_hud_version("2.0-beta") is True
    assert _is_valid_hud_version("hud_v3") is True
    assert _is_valid_hud_version("3.1.4-rc1") is True


def test_hud_version_rejects_path_separators():
    assert _is_valid_hud_version("1/0") is False
    assert _is_valid_hud_version("1\\0") is False
    assert _is_valid_hud_version("../etc") is False


def test_hud_version_rejects_dots_and_empty():
    assert _is_valid_hud_version("") is False
    assert _is_valid_hud_version(".") is False
    assert _is_valid_hud_version("..") is False


def test_hud_version_rejects_whitespace_and_specials():
    assert _is_valid_hud_version("1 0") is False
    assert _is_valid_hud_version("1:0") is False
    assert _is_valid_hud_version("1*0") is False


# ---------------------------------------------------------------------------
# _backfill_between
# ---------------------------------------------------------------------------


KFS = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0, 360.0, 420.0]


def test_backfill_consecutive_same_class_returns_keyframes_between():
    # last horizon at 60, current horizon at 240 → backfill 120, 180.
    assert _backfill_between("horizon", 60.0, "horizon", 240.0, KFS) == [120.0, 180.0]


def test_backfill_returns_empty_when_classes_differ():
    assert _backfill_between("lobby", 60.0, "horizon", 240.0, KFS) == []


def test_backfill_returns_empty_when_no_previous_label():
    assert _backfill_between(None, None, "horizon", 240.0, KFS) == []


def test_backfill_returns_empty_when_only_last_pts_is_none():
    # Asymmetric: class is set but pts is not — must still short-circuit.
    assert _backfill_between("horizon", None, "horizon", 240.0, KFS) == []


def test_backfill_returns_empty_when_only_last_class_is_none():
    # Asymmetric: pts is set but class is not — must still short-circuit.
    assert _backfill_between(None, 60.0, "horizon", 240.0, KFS) == []


def test_backfill_skips_transition_class():
    # Transitions are short; never assume they extend.
    assert _backfill_between("transition", 60.0, "transition", 240.0, KFS) == []


def test_backfill_returns_empty_when_current_not_strictly_after_previous():
    # Same PTS twice (no advance) → nothing to backfill.
    assert _backfill_between("horizon", 240.0, "horizon", 240.0, KFS) == []
    # Backwards (user manually scrubbed back) → also empty.
    assert _backfill_between("horizon", 240.0, "horizon", 60.0, KFS) == []


def test_backfill_is_exclusive_on_endpoints():
    # Endpoints themselves were already labeled; only strict middle is filled.
    assert _backfill_between("horizon", 60.0, "horizon", 120.0, KFS) == []  # adjacent kfs, no middle
    assert _backfill_between("horizon", 60.0, "horizon", 180.0, KFS) == [120.0]


def test_backfill_custom_skip_classes():
    # Score is added to skip classes — should not backfill.
    assert _backfill_between(
        "score", 60.0, "score", 240.0, KFS, skip_classes=("transition", "score")
    ) == []
