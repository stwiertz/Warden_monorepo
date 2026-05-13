"""Unit tests for overlay_stack_analyzer pure helpers + a tiny data smoke (no GUI)."""

import json
import math
import os

import cv2
import numpy as np
import pytest

from tools.overlay_stack_analyzer import (
    _HUE_CV_TO_RAD,
    _cell_output_paths,
    _circ_hue_finalize,
    _circ_hue_init,
    _circ_hue_update,
    _default_input_dir,
    _default_output_dir,
    _discover_cells,
    _modal_shape,
    _normalize_uint8,
    _read_bgr,
    _stability_score,
    _stats_npz_bytes,
    _target_shape,
    _welford_finalize,
    _welford_init,
    _welford_update,
    load_stats_npz,
    main,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_png_file(path, arr):
    """Write ``arr`` as a PNG to ``path`` (creating parents), Windows-path-safe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", arr)
    assert ok
    path.write_bytes(buf.tobytes())


# ---------------------------------------------------------------------------
# _welford_init / _welford_update / _welford_finalize
# ---------------------------------------------------------------------------


def test_welford_scalars_match_numpy():
    data = [1.0, 2.0, 3.0, 4.0]
    state = _welford_init(())
    for x in data:
        state = _welford_update(state, x)
    mean, stddev = _welford_finalize(state)
    assert float(mean) == pytest.approx(2.5)
    assert float(stddev) == pytest.approx(math.sqrt(1.25))
    assert float(mean) == pytest.approx(float(np.mean(data)))
    assert float(stddev) == pytest.approx(float(np.std(data)))  # ddof=0 → population


def test_welford_arrays_match_numpy():
    data = [1.0, 2.0, 3.0, 4.0]
    frames = [np.full((2, 2, 3), v, dtype=np.float64) for v in data]
    state = _welford_init((2, 2, 3))
    for frame in frames:
        state = _welford_update(state, frame)
    mean, stddev = _welford_finalize(state)
    assert np.allclose(mean, 2.5)
    assert np.allclose(stddev, math.sqrt(1.25))
    assert np.allclose(mean, np.mean(np.stack(frames), axis=0))
    assert np.allclose(stddev, np.std(np.stack(frames), axis=0))  # population


def test_welford_count_one_has_zero_stddev():
    state = _welford_update(_welford_init((2, 2, 3)), np.full((2, 2, 3), 7.0))
    mean, stddev = _welford_finalize(state)
    assert np.allclose(mean, 7.0)
    assert np.array_equal(stddev, np.zeros((2, 2, 3)))


def test_welford_count_zero_finalize_raises():
    with pytest.raises(ValueError):
        _welford_finalize(_welford_init(()))


# ---------------------------------------------------------------------------
# _modal_shape
# ---------------------------------------------------------------------------


def test_modal_shape_picks_most_common():
    shapes = [(1080, 1920, 3)] * 3 + [(1440, 2560, 3)]
    assert _modal_shape(shapes) == (1080, 1920, 3)


def test_modal_shape_tie_breaks_to_larger_area():
    # 2 vs 2 → larger h*w wins.
    shapes = [(8, 8, 3), (8, 8, 3), (16, 16, 3), (16, 16, 3)]
    assert _modal_shape(shapes) == (16, 16, 3)


def test_modal_shape_empty_raises():
    with pytest.raises(ValueError):
        _modal_shape([])


# ---------------------------------------------------------------------------
# _target_shape
# ---------------------------------------------------------------------------


def test_target_shape_none_returns_modal():
    assert _target_shape((1080, 1920, 3), None) == (1080, 1920, 3)


def test_target_shape_scales_to_ref_height_keeping_aspect():
    assert _target_shape((1080, 1920, 3), 720) == (720, 1280, 3)


# ---------------------------------------------------------------------------
# _discover_cells
# ---------------------------------------------------------------------------


def test_discover_cells_groups_versions_and_classes_and_ignores_strays(tmp_path):
    blank = np.zeros((4, 4, 3), dtype=np.uint8)
    _write_png_file(tmp_path / "v1.0" / "lobby" / "001_00h00m01s.png", blank)
    _write_png_file(tmp_path / "v2.0" / "lobby" / "001_00h00m02s.png", blank)
    _write_png_file(tmp_path / "v2.0" / "horizon" / "001_00h00m03s.png", blank)
    # Strays that must be ignored:
    (tmp_path / "notes.txt").write_text("not a cell")
    _write_png_file(tmp_path / "scratch" / "with.png", blank)  # non-`v` top-level dir
    _write_png_file(tmp_path / "v2.0" / "lobby" / "readme.md.png", blank)  # extra png ok

    cells = _discover_cells(str(tmp_path))
    keys = [(v, c) for v, c, _ in cells]
    assert keys == [("v1.0", "lobby"), ("v2.0", "horizon"), ("v2.0", "lobby")]
    # v2.0/lobby has 2 pngs, sorted:
    lobby_pngs = next(paths for v, c, paths in cells if (v, c) == ("v2.0", "lobby"))
    assert len(lobby_pngs) == 2
    assert lobby_pngs == sorted(lobby_pngs)
    # No empty class dir leaked through:
    assert all(paths for _, _, paths in cells)


def test_discover_cells_missing_root_returns_empty(tmp_path):
    assert _discover_cells(str(tmp_path / "does_not_exist")) == []


# ---------------------------------------------------------------------------
# _normalize_uint8
# ---------------------------------------------------------------------------


def test_normalize_uint8_min_max():
    out = _normalize_uint8(np.array([[0.0, 127.5, 255.0]]))
    assert out.dtype == np.uint8
    assert out[0, 0] == 0
    assert out[0, 2] == 255
    assert out[0, 1] in (127, 128)


def test_normalize_uint8_constant_is_all_zero():
    assert np.array_equal(_normalize_uint8(np.full((3, 3), 42.0)), np.zeros((3, 3), np.uint8))
    assert np.array_equal(_normalize_uint8(np.full((3, 3), 7, dtype=np.int32)), np.zeros((3, 3), np.uint8))


def test_normalize_uint8_accepts_int_and_float():
    np.testing.assert_array_equal(
        _normalize_uint8(np.array([[0, 5, 10]], dtype=np.int64)),
        _normalize_uint8(np.array([[0.0, 5.0, 10.0]])),
    )


# ---------------------------------------------------------------------------
# _stability_score
# ---------------------------------------------------------------------------


def test_stability_score_is_mean():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    assert _stability_score(arr) == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# _cell_output_paths
# ---------------------------------------------------------------------------


def test_cell_output_paths_without_heatmap():
    out = _cell_output_paths("/out", "v2.0", "lobby", heatmap=False)
    assert out == {
        "mean": os.path.join("/out", "v2.0", "lobby", "mean.png"),
        "stddev": os.path.join("/out", "v2.0", "lobby", "stddev.png"),
        "stats": os.path.join("/out", "v2.0", "lobby", "stats.npz"),
    }


def test_cell_output_paths_with_heatmap():
    out = _cell_output_paths("/out", "v1.0", "horizon", heatmap=True)
    assert out == {
        "mean": os.path.join("/out", "v1.0", "horizon", "mean.png"),
        "stddev": os.path.join("/out", "v1.0", "horizon", "stddev.png"),
        "stats": os.path.join("/out", "v1.0", "horizon", "stats.npz"),
        "heatmap": os.path.join("/out", "v1.0", "horizon", "variance_heatmap.png"),
    }


# ---------------------------------------------------------------------------
# Task 1 amendment — circular-Hue accumulator
# ---------------------------------------------------------------------------


def _direct_circular_hue(hues_cv):
    """Reference circular mean/std of OpenCV-space hues, computed directly."""
    angles = np.asarray(hues_cv, dtype=np.float64) * _HUE_CV_TO_RAD
    mean_sin = float(np.mean(np.sin(angles)))
    mean_cos = float(np.mean(np.cos(angles)))
    R = math.sqrt(mean_sin ** 2 + mean_cos ** 2)
    mean_deg = math.degrees(math.atan2(mean_sin, mean_cos)) % 360.0
    mean_cv = (mean_deg / 2.0) % 180.0
    inner = max(-2.0 * math.log(min(max(R, 1e-9), 1.0)), 0.0)
    std_cv = min(max(math.degrees(math.sqrt(inner)) / 2.0, 0.0), 90.0)
    return mean_cv, std_cv


def _run_circ_hue(hues_cv, shape=()):
    state = _circ_hue_init(shape)
    for h in hues_cv:
        state = _circ_hue_update(state, np.full(shape, h, dtype=np.uint8))
    return _circ_hue_finalize(state)


@pytest.mark.parametrize(
    "hues",
    [
        [10, 20, 30],
        [170, 175, 179, 0, 1, 5],   # wrap-around near 0/179
        [89, 90, 91],
        [0, 60, 120],               # spread thin → small but nonzero R
    ],
)
def test_circ_hue_matches_direct_computation(hues):
    mean_cv, std_cv = _run_circ_hue(hues)
    exp_mean, exp_std = _direct_circular_hue(hues)
    assert float(mean_cv) == pytest.approx(exp_mean, abs=1e-6)
    assert float(std_cv) == pytest.approx(exp_std, abs=1e-6)


def test_circ_hue_constant_and_single_sample_have_zero_std():
    _, std_const = _run_circ_hue([42, 42, 42, 42])
    assert float(std_const) == pytest.approx(0.0, abs=1e-4)
    mean_one, std_one = _run_circ_hue([100])
    assert float(mean_one) == pytest.approx(100.0, abs=1e-6)
    assert float(std_one) == pytest.approx(0.0, abs=1e-4)


def test_circ_hue_works_on_arrays_and_zero_count_raises():
    state = _circ_hue_init((2, 2))
    state = _circ_hue_update(state, np.array([[10, 10], [170, 170]], dtype=np.uint8))
    state = _circ_hue_update(state, np.array([[12, 12], [172, 172]], dtype=np.uint8))
    mean_cv, std_cv = _circ_hue_finalize(state)
    assert mean_cv.shape == (2, 2)
    assert float(mean_cv[0, 0]) == pytest.approx(11.0, abs=0.5)
    assert float(mean_cv[1, 0]) == pytest.approx(171.0, abs=0.5)
    assert (std_cv >= 0).all() and (std_cv <= 90).all()
    with pytest.raises(ValueError):
        _circ_hue_finalize(_circ_hue_init(()))


# ---------------------------------------------------------------------------
# Task 1 amendment — stats.npz build / round-trip
# ---------------------------------------------------------------------------


def test_stats_npz_round_trip_buffer_and_path(tmp_path):
    rng = np.random.default_rng(1)
    mean_bgr = rng.random((3, 4, 3)) * 255.0
    std_bgr = rng.random((3, 4, 3)) * 12.0
    mean_hsv = rng.random((3, 4, 3)) * 179.0
    std_hsv = rng.random((3, 4, 3)) * 6.0

    raw = _stats_npz_bytes(mean_bgr, std_bgr, mean_hsv, std_hsv, 9, (3, 4, 3))
    for loaded in (load_stats_npz(raw), None):
        if loaded is None:
            (tmp_path / "stats.npz").write_bytes(raw)
            loaded = load_stats_npz(tmp_path / "stats.npz")  # path form (Path/str both ok)
        assert loaded["frame_count"] == 9
        assert loaded["frame_shape"] == (3, 4, 3)
        for key, src in (
            ("mean_bgr", mean_bgr), ("std_bgr", std_bgr),
            ("mean_hsv", mean_hsv), ("std_hsv", std_hsv),
        ):
            assert loaded[key].dtype == np.float32
            assert loaded[key].shape == src.shape
            np.testing.assert_allclose(loaded[key], src.astype(np.float32), rtol=1e-5)


# ---------------------------------------------------------------------------
# _default_input_dir / _default_output_dir
# ---------------------------------------------------------------------------


def test_default_dirs_are_absolute_and_named():
    in_dir = _default_input_dir()
    out_dir = _default_output_dir()
    assert os.path.isabs(in_dir) and os.path.isabs(out_dir)
    assert in_dir.endswith(os.path.join("output", "labeled"))
    assert out_dir.endswith(os.path.join("output", "overlay_stacks"))
    # Same "output" parent — the two trees are siblings.
    assert os.path.dirname(in_dir) == os.path.dirname(out_dir)


def test_default_input_dir_matches_tool6_default_output():
    from tools.video_timeline_labeler import _default_output_dir as tool6_default_output

    assert _default_input_dir() == tool6_default_output()


# ---------------------------------------------------------------------------
# _read_bgr
# ---------------------------------------------------------------------------


def test_read_bgr_round_trip_and_failures(tmp_path):
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[:, :, 2] = 255  # solid red (BGR)
    png_path = tmp_path / "frame.png"
    _write_png_file(png_path, arr)
    decoded = _read_bgr(str(png_path))
    assert decoded is not None
    assert decoded.shape == (4, 4, 3)
    assert np.array_equal(decoded, arr)
    # Missing file → None (no exception):
    assert _read_bgr(str(tmp_path / "nope.png")) is None
    # Garbage bytes → None:
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"not a png")
    assert _read_bgr(str(junk)) is None


# ---------------------------------------------------------------------------
# Data smoke — _process_cell / main end-to-end with tiny imencode-written PNGs
# ---------------------------------------------------------------------------


def _build_smoke_tree(root):
    """cell A (v2.0/lobby) = 3× solid red 8×8; cell B (v2.0/horizon) = 3× 8×8
    gradient + 1× 16×16 frame (forces one resize)."""
    red = np.zeros((8, 8, 3), dtype=np.uint8)
    red[:, :, 2] = 255
    for i in range(1, 4):
        _write_png_file(root / "v2.0" / "lobby" / f"{i:03d}_00h00m0{i}s.png", red)

    for i, val in enumerate((0, 50, 100), start=1):
        _write_png_file(
            root / "v2.0" / "horizon" / f"{i:03d}_00h00m0{i}s.png",
            np.full((8, 8, 3), val, dtype=np.uint8),
        )
    _write_png_file(
        root / "v2.0" / "horizon" / "004_00h00m04s.png",
        np.full((16, 16, 3), 200, dtype=np.uint8),
    )


def test_main_data_smoke(tmp_path):
    in_dir = tmp_path / "labeled"
    out_dir = tmp_path / "stacks"
    _build_smoke_tree(in_dir)

    assert main(["--input", str(in_dir), "--output", str(out_dir)]) == 0

    # Cell A — solid red, zero variance.
    mean_a = _read_bgr(str(out_dir / "v2.0" / "lobby" / "mean.png"))
    std_a = _read_bgr(str(out_dir / "v2.0" / "lobby" / "stddev.png"))
    assert mean_a is not None and std_a is not None
    expected_red = np.zeros((8, 8, 3), dtype=np.uint8)
    expected_red[:, :, 2] = 255
    assert np.array_equal(mean_a, expected_red)
    assert np.array_equal(std_a, np.zeros((8, 8, 3), dtype=np.uint8))

    # Cell B — gradient, nonzero variance, one resized frame.
    std_b = _read_bgr(str(out_dir / "v2.0" / "horizon" / "stddev.png"))
    assert std_b is not None
    assert (std_b > 0).any()

    summary = json.loads((out_dir / "overlay_stacks_summary.json").read_text())
    assert summary["heatmap"] is False
    assert summary["ref_height"] is None
    assert summary["min_frames"] == 2
    ok_cells = [c for c in summary["cells"] if c["status"] == "ok"]
    assert len(ok_cells) == 2
    # Sorted ascending by stability_score → cell A (zero variance) first.
    assert summary["cells"][0]["class"] == "lobby"
    assert summary["cells"][0]["stability_score"] == pytest.approx(0.0)
    assert summary["cells"][1]["class"] == "horizon"
    assert summary["cells"][1]["stability_score"] > 0.0
    horizon_entry = next(c for c in summary["cells"] if c["class"] == "horizon")
    assert horizon_entry["frame_count"] == 4
    assert horizon_entry["resized_count"] == 1
    assert horizon_entry["frame_shape"] == [8, 8, 3]
    assert horizon_entry["outputs"]["mean"] == "v2.0/horizon/mean.png"

    # --- Task 1 amendment: always-on stats.npz side-car + new summary fields ---
    assert (out_dir / "v2.0" / "lobby" / "stats.npz").exists()
    assert (out_dir / "v2.0" / "horizon" / "stats.npz").exists()
    lobby_entry = next(c for c in summary["cells"] if c["class"] == "lobby")
    assert lobby_entry["outputs"]["stats"] == "v2.0/lobby/stats.npz"
    assert horizon_entry["outputs"]["stats"] == "v2.0/horizon/stats.npz"
    # Solid-red lobby cell → zero instability everywhere; most-stable HSV = red.
    assert lobby_entry["stability_percentiles"] == {"p10": 0.0, "p50": 0.0, "p90": 0.0}
    assert lobby_entry["most_stable_hsv"] == pytest.approx([0.0, 255.0, 255.0], abs=1.0)
    # Horizon cell varies → percentiles non-decreasing, fields present, npz loadable.
    sp = horizon_entry["stability_percentiles"]
    assert set(sp) == {"p10", "p50", "p90"} and sp["p10"] <= sp["p50"] <= sp["p90"]
    assert len(horizon_entry["most_stable_hsv"]) == 3
    stats_h = load_stats_npz(str(out_dir / "v2.0" / "horizon" / "stats.npz"))
    assert stats_h["frame_count"] == 4
    assert stats_h["frame_shape"] == (8, 8, 3)
    assert stats_h["mean_bgr"].shape == stats_h["std_hsv"].shape == (8, 8, 3)
    # Skipped cells (none here) would not carry the new fields, but ok cells always do.


def test_main_most_stable_hsv_picks_min_bgr_stddev_pixel(tmp_path):
    in_dir = tmp_path / "labeled"
    out_dir = tmp_path / "stacks"
    rng = np.random.default_rng(0)
    # 3 frames, 4×4 random — except pixel (row=1,col=2) is constant blue (BGR 255,0,0).
    for i in range(1, 4):
        frame = rng.integers(0, 256, size=(4, 4, 3), dtype=np.uint8)
        frame[1, 2] = (255, 0, 0)
        _write_png_file(in_dir / "v2.0" / "score" / f"{i:03d}_00h00m0{i}s.png", frame)

    assert main(["--input", str(in_dir), "--output", str(out_dir)]) == 0

    stats = load_stats_npz(str(out_dir / "v2.0" / "score" / "stats.npz"))
    # Constant-blue pixel → zero BGR stddev; HSV ≈ OpenCV blue (120, 255, 255).
    assert np.allclose(stats["std_bgr"][1, 2], 0.0)
    assert float(stats["mean_hsv"][1, 2, 0]) == pytest.approx(120.0, abs=1.0)
    assert float(stats["mean_hsv"][1, 2, 1]) == pytest.approx(255.0, abs=1.0)
    assert float(stats["mean_hsv"][1, 2, 2]) == pytest.approx(255.0, abs=1.0)
    assert float(stats["std_hsv"][1, 2, 0]) == pytest.approx(0.0, abs=1e-2)

    summary = json.loads((out_dir / "overlay_stacks_summary.json").read_text())
    cell = next(c for c in summary["cells"] if c["class"] == "score")
    assert cell["most_stable_hsv"] == pytest.approx([120.0, 255.0, 255.0], abs=1.0)


def test_main_heatmap_produces_three_channel_heatmap(tmp_path):
    in_dir = tmp_path / "labeled"
    out_dir = tmp_path / "stacks_heat"
    _build_smoke_tree(in_dir)

    assert main(["--input", str(in_dir), "--output", str(out_dir), "--heatmap"]) == 0

    heat = _read_bgr(str(out_dir / "v2.0" / "horizon" / "variance_heatmap.png"))
    assert heat is not None
    assert heat.ndim == 3 and heat.shape[2] == 3
    # The cell A heatmap (constant → all-zero scalar) still renders as a 3-channel image.
    heat_a = _read_bgr(str(out_dir / "v2.0" / "lobby" / "variance_heatmap.png"))
    assert heat_a is not None and heat_a.shape[2] == 3
    summary = json.loads((out_dir / "overlay_stacks_summary.json").read_text())
    assert summary["heatmap"] is True
    horizon_entry = next(c for c in summary["cells"] if c["class"] == "horizon")
    assert horizon_entry["outputs"]["heatmap"] == "v2.0/horizon/variance_heatmap.png"


def test_main_ref_height_resizes_every_cell(tmp_path):
    in_dir = tmp_path / "labeled"
    out_dir = tmp_path / "stacks_ref"
    _build_smoke_tree(in_dir)  # cell A: 3× red 8×8; cell B: 3× 8×8 + 1× 16×16

    assert main(["--input", str(in_dir), "--output", str(out_dir), "--ref-height", "4"]) == 0

    summary = json.loads((out_dir / "overlay_stacks_summary.json").read_text())
    assert summary["ref_height"] == 4
    lobby = next(c for c in summary["cells"] if c["class"] == "lobby")
    horizon = next(c for c in summary["cells"] if c["class"] == "horizon")
    # Every source frame (8×8 or 16×16) differs from the (4,4,3) target → all resized.
    assert lobby["frame_shape"] == [4, 4, 3]
    assert lobby["resized_count"] == lobby["frame_count"] == 3
    assert horizon["frame_shape"] == [4, 4, 3]
    assert horizon["resized_count"] == horizon["frame_count"] == 4
    # Solid-red cell stays solid red after the downscale; stddev stays zero.
    mean_a = _read_bgr(str(out_dir / "v2.0" / "lobby" / "mean.png"))
    std_a = _read_bgr(str(out_dir / "v2.0" / "lobby" / "stddev.png"))
    assert mean_a is not None and mean_a.shape == (4, 4, 3)
    expected_red = np.zeros((4, 4, 3), dtype=np.uint8)
    expected_red[:, :, 2] = 255
    assert np.array_equal(mean_a, expected_red)
    assert np.array_equal(std_a, np.zeros((4, 4, 3), dtype=np.uint8))


def test_main_no_cells_returns_one(tmp_path, capsys):
    empty = tmp_path / "empty_labeled"
    empty.mkdir()
    assert main(["--input", str(empty), "--output", str(tmp_path / "out")]) == 1


def test_main_min_frames_skips_thin_cell(tmp_path):
    in_dir = tmp_path / "labeled"
    out_dir = tmp_path / "stacks_thin"
    blank = np.zeros((8, 8, 3), dtype=np.uint8)
    _write_png_file(in_dir / "v2.0" / "lobby" / "001_00h00m01s.png", blank)  # only 1 frame
    for i in range(1, 4):
        _write_png_file(in_dir / "v2.0" / "horizon" / f"{i:03d}_00h00m0{i}s.png", blank)

    assert main(["--input", str(in_dir), "--output", str(out_dir)]) == 0
    summary = json.loads((out_dir / "overlay_stacks_summary.json").read_text())
    lobby = next(c for c in summary["cells"] if c["class"] == "lobby")
    assert lobby["status"] == "skipped"
    assert lobby["reason"] == "too_few_frames"
    assert lobby["frame_count"] == 1
    assert not (out_dir / "v2.0" / "lobby" / "mean.png").exists()
    horizon = next(c for c in summary["cells"] if c["class"] == "horizon")
    assert horizon["status"] == "ok"
