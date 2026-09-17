"""Story 12.4c AC10 — the INDEPENDENT PC-side video oracle, and AC9's fixture.

WHY THIS EXISTS
---------------
Story 12.4b proved the bound engine's fire bits twice, and neither proof covers
the wired video path end to end:

* **AC3(A)** — the CPU evaluator over the 2666-PNG corpus against
  ``pc_reference_fires.json``: **0 / 357,244**. That corpus is PNGs read with
  ``cv2.imread``; **it never touches the YUV converter.**
* **AC3(B)** — the CPU arm against the GPU arm over the full 1061-keyframe
  capture: **0 / 142,174**. The reference there was the *other device arm* —
  which 12.4b then deleted, and in which it found a real defect (the last chroma
  texel read padding as Cr).

So on VIDEO there is no reference that is independent of the device. This script
is that reference. It decodes the capture's keyframes with FFmpeg (a different
H.264 decoder from MediaCodec — decoding is normative, so the planes must be
bit-identical), converts them with the **pinned numpy BT.709 limited-range +
nearest-chroma model** from ``bench/12-2/ac3_numpy_reference.py``, and evaluates
the rules with **Tool 9's own** ``zone_fires_on_frame`` (cv2 ``RGB2HSV_b`` +
``inRange``). Nothing in the chain is our Kotlin.

It then runs **Tool 12's** ``scoring.py`` / ``phases.py`` over those fires, so
the same artifact carries the expected classifier verdicts, the phase timeline
and the spans. That half is what AC9's jest fixture is generated from: the TS
port is checked against Tool 12's output, not against itself.

Three subcommands:

  oracle    VIDEO -> fires + Tool 12 timeline               (needs the capture)
  fixture   oracle JSON -> the committed jest fixture        (no video)
  compare   device analyzeSession JSON vs the oracle         (AC10's gate)

The COLOUR half is self-checking: the 2^24 LUT this builds is hashed and
compared against ``REFERENCE_YUV_SWEEP_SHA256`` — the same digest the device
re-derives in ``WardenEngineBench.colorConstantsCheck()``. If the oracle's
colour model ever drifts from the device's, the oracle refuses to run rather
than reporting disagreements that are its own fault.

Usage (from the tooling venv, which owns cv2/numpy and Tool 9/12):

    cd apps/tooling
    uv run python ../mobile/bench/12-4c/video_oracle.py oracle \
        --video "../../videos/V2/2026-04-27 22-05-34.mp4"
    uv run python ../mobile/bench/12-4c/video_oracle.py fixture
    uv run python ../mobile/bench/12-4c/video_oracle.py compare \
        --device ../mobile/bench/12-4c/device_analyze_session.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLING = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "tooling"))
if _TOOLING not in sys.path:
    sys.path.insert(0, _TOOLING)

from tools.keyframe_engine_bench import phases as phases_mod  # noqa: E402
from tools.keyframe_engine_bench.lut import (  # noqa: E402
    MODE_FULL_CIRCLE,
    MODE_NORMAL,
    MODE_WRAP,
    pack_rules,
)
from tools.keyframe_engine_bench.scoring import score_from_fires  # noqa: E402
from tools.roi_detection_tester import (  # noqa: E402
    load_map_config,
    zone_fires_on_frame,
)

REF_W, REF_H = 1920, 1080
CONFIG = os.path.join(_TOOLING, "output", "map_configs", "map_config.v2.json")
DEFAULT_ORACLE = os.path.join(_HERE, "video_oracle_fires.json")
DEFAULT_FIXTURE = os.path.abspath(
    os.path.join(
        _HERE,
        "..",
        "..",
        "src",
        "features",
        "video-processing",
        "__tests__",
        "fixtures",
        "tool12-parity.json",
    )
)

# The oracle's colour model is imported from 12.2's pinned reference rather than
# re-typed: a second transcription of the same four constants is a second thing
# that can drift, and this file's whole claim is independence FROM THE DEVICE,
# not independence from the pin the device is held to.
_AC3 = os.path.join(_HERE, "..", "12-2", "ac3_numpy_reference.py")
_spec = importlib.util.spec_from_file_location("ac3_numpy_reference", _AC3)
_ac3 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_ac3)


# ---------------------------------------------------------------------------
# Colour: one 2^24 LUT, hashed against the device's pin
# ---------------------------------------------------------------------------


def build_bgr_lut() -> np.ndarray:
    """(256,256,256,3) uint8 BGR LUT of the pinned conversion, digest-checked.

    Building the whole domain is not extravagance — it is the same sweep the pin
    covers, so hashing it re-proves that this script's colour half IS the
    device's colour half before a single fire bit is compared. It also makes the
    per-frame conversion a fancy-index instead of 2M float64 divisions.
    """
    y = np.arange(256, dtype=np.uint8).reshape(256, 1, 1)
    cb = np.arange(256, dtype=np.uint8).reshape(1, 256, 1)
    cr = np.arange(256, dtype=np.uint8).reshape(1, 1, 256)
    y, cb, cr = np.broadcast_arrays(y, cb, cr)
    lut = _ac3.shader_model(y, cb, cr)  # (256,256,256,3) uint8, B,G,R
    digest = hashlib.sha256(np.ascontiguousarray(lut).tobytes()).hexdigest()
    if digest != _ac3.REFERENCE_YUV_SWEEP_SHA256:
        raise SystemExit(
            "the oracle's colour LUT does not match REFERENCE_YUV_SWEEP_SHA256 "
            f"({digest} != {_ac3.REFERENCE_YUV_SWEEP_SHA256}). This script's "
            "colour model is supposed to BE the device's pinned model; a "
            "mismatch means any fire-bit disagreement it reports would be its "
            "own. Refusing to run."
        )
    return lut


def frame_to_bgr(lut: np.ndarray, y: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Y + 4:2:0 chroma -> BGR uint8, NEAREST chroma (``x/2, y/2``).

    ``repeat(2)`` on both axes is exactly ``bgrAt``'s ``cx = x / 2`` integer
    division — do NOT "improve" it to an interpolating upsample, which is what
    swscale does and what the converter deliberately does not.
    """
    u2 = u.repeat(2, axis=0).repeat(2, axis=1)[: y.shape[0], : y.shape[1]]
    v2 = v.repeat(2, axis=0).repeat(2, axis=1)[: y.shape[0], : y.shape[1]]
    return lut[y, u2, v2]


# ---------------------------------------------------------------------------
# Decode: FFmpeg keyframes -> planes, streamed one frame at a time
# ---------------------------------------------------------------------------

_SHOWINFO = re.compile(r"\bn:\s*(\d+).*?\bpts:\s*(-?\d+)\s+pts_time:\s*(-?[\d.]+)")


def probe_video(path: str) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries",
            "stream=width,height,pix_fmt,color_range,color_space,time_base,nb_frames",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    st = data["streams"][0]
    return {
        "width": int(st["width"]),
        "height": int(st["height"]),
        "pix_fmt": st.get("pix_fmt"),
        "color_range": st.get("color_range"),
        "color_space": st.get("color_space"),
        "time_base": st.get("time_base"),
        "duration_s": float(data.get("format", {}).get("duration", 0.0) or 0.0),
    }


def iter_keyframes(path: str, width: int, height: int, limit: int = 0):
    """Yield ``(idx, pts_time_s, y, u, v)`` for every keyframe, in order.

    ``-skip_frame nokey`` is the decoder-side keyframe filter (12.1's measured
    choice), and ``showinfo`` on stderr is how each yielded plane set keeps its
    timestamp. The raw stream carries no timestamps at all, so the two are
    matched BY ORDER — which is safe here because both come from the same
    single-pass filter graph, and is asserted by the frame count at the end.
    """
    y_size = width * height
    c_w, c_h = (width + 1) // 2, (height + 1) // 2
    c_size = c_w * c_h
    frame_size = y_size + 2 * c_size

    proc = subprocess.Popen(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info",
            "-skip_frame", "nokey", "-i", path,
            "-an", "-sn", "-dn",
            "-vf", "showinfo",
            "-fps_mode", "passthrough",
            "-f", "rawvideo", "-pix_fmt", "yuv420p", "pipe:1",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    stamps: list[float] = []
    stderr_tail: list[str] = []

    def drain_stderr() -> None:
        assert proc.stderr is not None
        for raw in proc.stderr:
            line = raw.decode("utf-8", "replace")
            m = _SHOWINFO.search(line)
            if m:
                stamps.append(float(m.group(3)))
            elif len(stderr_tail) < 40:
                stderr_tail.append(line.rstrip())

    t = threading.Thread(target=drain_stderr, daemon=True)
    t.start()

    idx = 0
    try:
        assert proc.stdout is not None
        while True:
            buf = proc.stdout.read(frame_size)
            if not buf or len(buf) < frame_size:
                break
            arr = np.frombuffer(buf, dtype=np.uint8)
            yp = arr[:y_size].reshape(height, width)
            up = arr[y_size:y_size + c_size].reshape(c_h, c_w)
            vp = arr[y_size + c_size:].reshape(c_h, c_w)
            # showinfo runs ahead of the pipe consumer, so the stamp for frame
            # `idx` is normally already in. Spin briefly if it is not: a raw
            # frame with a guessed timestamp is worse than a slow oracle.
            for _ in range(200):
                if len(stamps) > idx:
                    break
                time.sleep(0.01)
            if len(stamps) <= idx:
                raise SystemExit(
                    f"keyframe {idx} arrived on the pipe but showinfo reported "
                    f"only {len(stamps)} timestamps. Timestamps are matched to "
                    "frames by order; guessing one would silently misalign the "
                    "whole timeline.\n" + "\n".join(stderr_tail[-10:])
                )
            yield idx, stamps[idx], yp, up, vp
            idx += 1
            if limit and idx >= limit:
                break
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
        if limit and idx >= limit:
            proc.terminate()
        proc.wait()
        t.join(timeout=5)

    if not limit and proc.returncode not in (0, None):
        raise SystemExit(
            f"ffmpeg exited {proc.returncode}\n" + "\n".join(stderr_tail[-20:])
        )


def bits_to_hex(bits) -> str:
    """4 bits per hex char, LSB first — the packing WardenEngineBench uses."""
    out = []
    for i in range(0, len(bits), 4):
        nib = 0
        for j in range(4):
            if i + j < len(bits) and bits[i + j]:
                nib |= 1 << j
        out.append("0123456789abcdef"[nib])
    return "".join(out)


def hex_to_bits(s: str, n: int) -> list[bool]:
    bits: list[bool] = []
    for ch in s:
        nib = int(ch, 16)
        for j in range(4):
            bits.append(bool(nib & (1 << j)))
    return bits[:n]


# ---------------------------------------------------------------------------
# oracle
# ---------------------------------------------------------------------------


def _zone_list(config):
    """Every zone in canonical texel order — the SAME order pack_rules uses."""
    zones = list(config.hud_version_detection) + list(config.in_match_detection)
    for slug_zones in config.map_zones.values():
        zones.extend(slug_zones)
    return zones


def _refs_payload(packed, zones) -> list[dict]:
    from tools.keyframe_engine_bench.lut import resolve_band_bounds

    out = []
    for ref, zone in zip(packed.refs, zones):
        *_, mode = resolve_band_bounds(zone.band)
        out.append({
            "texel": ref.texel,
            "owning_class": ref.owning_class,
            "zone_id": ref.zone_id,
            "kind": ref.kind,
            "effective_weight": float(ref.effective_weight),
            "mode": int(mode),
            "h_tol": int(zone.band.h_tol),
            "s_center": int(zone.band.s_center),
            "min_ratio": float(zone.band.min_ratio),
        })
    return out


# 🔴 CONFIDENCES ARE WRITTEN AT FULL PRECISION, NEVER ROUNDED. They were rounded
# to 9 decimals at first, and the TS parity test then could not assert better than
# ~1e-9 — which is looser than the thing being checked. `fires / n_im` is the same
# IEEE-754 double in Python and in JavaScript, so exact round-trip is available
# and anything less would hide a real divergence behind the fixture's own rounding.
def run_oracle(video: str, out_path: str, limit: int, doubt_margin: float) -> int:
    meta = probe_video(video)
    if (meta["width"], meta["height"]) != (REF_W, REF_H):
        raise SystemExit(
            f"{video} is {meta['width']}x{meta['height']}; the shipped config's "
            f"reference_resolution is {REF_W}x{REF_H} and rule rects are "
            "calibrated there. Rescaling would compare resampled pixels."
        )
    if meta["pix_fmt"] != "yuv420p":
        raise SystemExit(
            f"{video} is {meta['pix_fmt']}; the oracle reads 8-bit 4:2:0 only "
            "(a 10-bit stream would be read as 8-bit garbage)."
        )

    config = load_map_config(CONFIG)
    packed = pack_rules(config, (REF_H, REF_W, 3))
    zones = _zone_list(config)
    with open(CONFIG, "r", encoding="utf-8") as fh:
        raw_cfg = fh.read()
    score_screen_ms = int(json.loads(raw_cfg)["score_screen_duration_ms"])

    print(f"config {os.path.basename(CONFIG)}: {packed.n_rules} rules, "
          f"score_screen_duration_ms={score_screen_ms}")
    print("building the 2^24 colour LUT and checking it against the device pin…")
    lut = build_bgr_lut()
    print("  colour LUT matches REFERENCE_YUV_SWEEP_SHA256 -- OK")

    resolver = phases_mod.PhaseResolver(score_screen_ms)
    frames_out: list[dict] = []
    calls: list[tuple[int, int, str]] = []
    internal: list[str] = []
    map_agg: list[dict] = []
    t0 = time.perf_counter()

    for idx, pts_s, yp, up, vp in iter_keyframes(video, REF_W, REF_H, limit):
        bgr = frame_to_bgr(lut, yp, up, vp)
        fires = [zone_fires_on_frame(z, bgr)[0] for z in zones]
        scores = score_from_fires(fires, packed, config)
        call = phases_mod.in_match_call(scores.in_match_conf, doubt_margin=doubt_margin)
        ts_ms = int(round(pts_s * 1000.0))
        emitted = resolver.push(ts_ms, call)
        calls.append((idx, ts_ms, call))
        internal.append(resolver.state)
        map_agg.append(scores.map_scores)
        frames_out.append({
            "frame_idx": idx,
            "pts_us": int(round(pts_s * 1_000_000.0)),
            "timestamp_ms": ts_ms,
            "fires": bits_to_hex(fires),
            "pred_hud": scores.pred_hud,
            "hud_conf": float(scores.hud_conf),
            "pred_in_match": scores.pred_in_match,
            "in_match_conf": float(scores.in_match_conf),
            "pred_map": scores.pred_map,
            "map_conf": float(scores.map_conf),
            "call": call,
            "emitted": emitted,
            "internal": resolver.state,
        })
        if idx % 50 == 0:
            print(f"  keyframe {idx} t={ts_ms/1000:8.2f}s {emitted:<13} "
                  f"map={scores.pred_map}", flush=True)

    if not frames_out:
        raise SystemExit(f"no keyframes decoded from {video}")

    spans = phases_mod.spans_from_states(calls, internal)
    matches = []
    for start, end in spans:
        agg: dict[str, float] = {}
        for row, (idx, _ts, _c) in zip(map_agg, calls):
            if start <= idx <= end:
                for slug, val in row.items():
                    agg[slug] = agg.get(slug, 0.0) + val
        best, conf = ("unknown", 0.0)
        if agg:
            best = max(agg, key=lambda s: agg[s])
            conf = agg[best]
            if conf <= 0.0:
                best = "unknown"
        by_idx = {i: f for i, f in enumerate(frames_out)}
        matches.append({
            "start_frame": start,
            "end_frame": end,
            "start_ms": by_idx[start]["timestamp_ms"],
            "end_ms": by_idx[end]["timestamp_ms"],
            "map_id": best,
            "confidence": float(conf),
        })

    wall = time.perf_counter() - t0
    payload = {
        "story": "12.4c",
        "kind": "pc-video-oracle",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "video": os.path.basename(video),
        "video_meta": meta,
        "config": os.path.basename(CONFIG),
        "colour_model": {
            "source": "bench/12-2/ac3_numpy_reference.shader_model",
            "sweep_sha256": _ac3.REFERENCE_YUV_SWEEP_SHA256,
            "chroma": "nearest (x/2, y/2)",
        },
        "evaluator": "tools.roi_detection_tester.zone_fires_on_frame (cv2 inRange)",
        "n_rules": packed.n_rules,
        "score_screen_duration_ms": score_screen_ms,
        "doubt_margin": doubt_margin,
        "n_hud_zones": len(config.hud_version_detection),
        "n_in_match_zones": len(config.in_match_detection),
        "map_zone_counts": {s: len(z) for s, z in config.map_zones.items()},
        "identification_threshold": float(config.identification_threshold),
        "hud_version": config.hud_version,
        "refs": _refs_payload(packed, zones),
        "n_keyframes": len(frames_out),
        "wall_s": round(wall, 3),
        "frames": frames_out,
        "spans": [{"start_frame": s, "end_frame": e} for s, e in spans],
        "matches": matches,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    print(f"\n{len(frames_out)} keyframes in {wall:.1f}s -> {out_path}")
    print(f"spans: {len(spans)}  matches: "
          f"{[(m['map_id'], m['start_ms'], m['end_ms']) for m in matches]}")
    return 0


# ---------------------------------------------------------------------------
# fixture — the committed jest fixture (AC9)
# ---------------------------------------------------------------------------


def _synthetic_config(
    n_hud: int,
    n_im: int,
    map_zones: dict[str, int],
    threshold: float,
    weights: dict[str, list[float]] | None = None,
):
    """A duck-typed Tool 12 (config, packed) pair for the synthetic cases.

    Tool 12's ``score_from_fires`` reads only ``config.hud_version``,
    ``hud_version_detection``, ``in_match_detection``, ``map_zones``,
    ``identification_threshold`` and ``packed.refs`` / ``packed.n_rules``, so a
    namespace is enough — and using the REAL function on synthetic inputs is the
    point: the expectations are Tool 12's, not hand-computed.
    """
    refs = []
    texel = 0
    for _ in range(n_hud):
        refs.append(SimpleNamespace(
            texel=texel, owning_class="v2", zone_id=f"hud_{texel}",
            kind="hud_version", effective_weight=1.0))
        texel += 1
    for _ in range(n_im):
        refs.append(SimpleNamespace(
            texel=texel, owning_class="in_match", zone_id=f"im_{texel}",
            kind="in_match", effective_weight=1.0))
        texel += 1
    for slug, count in map_zones.items():
        for k in range(count):
            w = 1.0 if weights is None else weights[slug][k]
            refs.append(SimpleNamespace(
                texel=texel, owning_class=slug, zone_id=f"{slug}_{k}",
                kind="map", effective_weight=w))
            texel += 1
    config = SimpleNamespace(
        hud_version="v2",
        hud_version_detection=[None] * n_hud,
        in_match_detection=[None] * n_im,
        map_zones={s: [None] * c for s, c in map_zones.items()},
        identification_threshold=threshold,
    )
    packed = SimpleNamespace(refs=refs, n_rules=texel)
    return config, packed


def _score_case(name, note, config, packed, fire_rows):
    """One synthetic case, scored by Tool 12 itself."""
    n_hud = len(config.hud_version_detection)
    n_im = len(config.in_match_detection)
    frames = []
    for row in fire_rows:
        fires = [bool(b) for b in row]
        if len(fires) != packed.n_rules:
            raise ValueError(f"{name}: {len(fires)} fires for {packed.n_rules} rules")
        s = score_from_fires(fires, packed, config)
        frames.append({
            "fires": bits_to_hex(fires),
            "pred_hud": s.pred_hud,
            "hud_conf": float(s.hud_conf),
            "pred_in_match": s.pred_in_match,
            "in_match_conf": float(s.in_match_conf),
            "pred_map": s.pred_map,
            "map_conf": float(s.map_conf),
            "map_scores": {k: float(v) for k, v in s.map_scores.items()},
        })
    return {
        "name": name,
        "note": note,
        "n_rules": packed.n_rules,
        "n_hud_zones": n_hud,
        "n_in_match_zones": n_im,
        "hud_version": config.hud_version,
        "identification_threshold": float(config.identification_threshold),
        "map_zone_counts": {s: len(z) for s, z in config.map_zones.items()},
        "refs": [
            {"texel": r.texel, "owning_class": r.owning_class, "zone_id": r.zone_id,
             "kind": r.kind, "effective_weight": float(r.effective_weight)}
            for r in packed.refs
        ],
        "frames": frames,
    }


def _phase_case(name, note, dur, doubt_margin, ratios_and_ts):
    """One phase-machine case, resolved by Tool 12's PhaseResolver itself."""
    resolver = phases_mod.PhaseResolver(dur)
    calls, emitted, internal = [], [], []
    for ts, ratio in ratios_and_ts:
        call = phases_mod.in_match_call(ratio, doubt_margin=doubt_margin)
        emitted.append(resolver.push(ts, call))
        internal.append(resolver.state)
        calls.append((len(calls), ts, call))
    spans = phases_mod.spans_from_states(calls, internal)
    return {
        "name": name,
        "note": note,
        "score_screen_duration_ms": dur,
        "doubt_margin": doubt_margin,
        "frames": [
            {"timestamp_ms": ts, "in_match_conf": ratio, "call": c[2],
             "emitted": e, "internal": i}
            for (ts, ratio), c, e, i in zip(ratios_and_ts, calls, emitted, internal)
        ],
        "spans": [{"start_frame": s, "end_frame": e} for s, e in spans],
    }


def build_fixture(oracle_path: str, out_path: str) -> int:
    with open(oracle_path, "r", encoding="utf-8") as fh:
        oracle = json.load(fh)

    # --- the three formulas, on a config whose three classifiers cannot be
    #     confused for each other: 2 HUD zones, 3 in_match zones, 3 maps.
    cfg3, pk3 = _synthetic_config(2, 3, {"atlantis": 2, "ceres": 2, "engine": 3}, 0.6)
    n = pk3.n_rules
    def row(hud, im, maps):
        bits = [False] * n
        for i in hud:
            bits[i] = True
        for i in im:
            bits[2 + i] = True
        for i in maps:
            bits[5 + i] = True
        return bits
    formulas = _score_case(
        "three_formulas",
        "HUD = fires/n_hud (normalized); in_match = fires/n_im (normalized, then "
        "HARD-BINARY, never unknown); map-ID = RAW sum(effective_weight x fired) "
        "vs identification_threshold. Implementing one formula everywhere breaks "
        "two of the three.",
        cfg3, pk3,
        [
            row([], [], []),               # nothing fires: hud unknown, not_in_match, map unknown
            row([0], [], []),              # hud 1/2 = 0.5 -> clears 0.5 exactly
            row([0, 1], [0, 1, 2], [0]),   # hud 1.0, in_match 1.0, one atlantis zone
            row([0, 1], [0], [0, 1]),      # in_match 1/3 -> not_in_match (binary, not unknown)
            row([0, 1], [0, 1], [0, 1, 2, 3]),  # 2 maps tie at 2.0 -> zone-count then label order
            row([0, 1], [0, 1, 2], [4, 5, 6]),  # engine 3.0 beats a tie by having more zones
        ],
    )

    # --- the weight = 1.0 degeneracy, and what breaks it. Same shape, real
    #     weights: a single 0.5-weighted zone does NOT clear 0.6, which is the
    #     whole reason the RAW sum matters.
    cfgw, pkw = _synthetic_config(
        1, 1, {"atlantis": 2, "ceres": 1}, 0.6,
        weights={"atlantis": [0.5, 0.5], "ceres": [1.0]},
    )
    nw = pkw.n_rules
    def roww(bits_on):
        bits = [False] * nw
        for i in bits_on:
            bits[i] = True
        return bits
    weights = _score_case(
        "weighted_aggregate",
        "The shipped config's 134 rules all carry weight 1.0, so map-ID reduces "
        "to argmax(fired_count) and the 0.6 threshold is near-inert. Reproduced "
        "AS-IS (9.16's call). These rows use non-unit weights to prove the sum is "
        "RAW and weight-aware: 1 x 0.5 < 0.6 -> unknown; 2 x 0.5 = 1.0 -> fires.",
        cfgw, pkw,
        [roww([2]), roww([2, 3]), roww([4]), roww([2, 4])],
    )

    # --- empty detection arrays are legal and must short-circuit, not crash.
    cfg_empty, pk_empty = _synthetic_config(0, 0, {"atlantis": 1}, 0.6)
    empty = _score_case(
        "empty_detection_arrays",
        "A partially-staged HUD version ships empty arrays (schema: 'Empty arrays "
        "are allowed'). HUD -> unknown with no scores at all; in_match -> the "
        "literal 'unknown' with conf 0 (the ONLY way in_match is ever unknown).",
        cfg_empty, pk_empty, [[False], [True]],
    )

    # --- the phase machine: doubt HOLDS.
    kf = 4167  # the capture's keyframe interval, ms
    phase_cases = [
        _phase_case(
            "doubt_holds_mid_match",
            "🔴 THE ONE MOST LIKELY TO BE GOT WRONG. A split vote mid-match is "
            "EMITTED as doubt but does NOT advance the machine, so the internal "
            "state stays in_match and the span is NOT shredded into two.",
            15000, 0.2,
            [(0, 0.0), (kf, 1.0), (2 * kf, 1.0), (3 * kf, 2 / 3), (4 * kf, 1.0),
             (5 * kf, 1 / 3), (6 * kf, 1.0), (7 * kf, 0.0), (8 * kf, 0.0),
             (9 * kf, 0.0), (10 * kf, 0.0), (11 * kf, 0.0)],
        ),
        _phase_case(
            "score_window_timing",
            "Falling edge arms the score window: elapsed is 0 BY DEFINITION on "
            "that frame, so a positive duration makes it the FIRST score_screen "
            "frame and the window closes once (ts - falling_ts) >= dur.",
            15000, 0.2,
            [(0, 1.0), (kf, 1.0), (2 * kf, 0.0), (3 * kf, 0.0), (4 * kf, 0.0),
             (5 * kf, 0.0), (6 * kf, 0.0)],
        ),
        _phase_case(
            "doubt_does_not_stop_the_clock",
            "A doubtful frame inside the score window keeps the timer running "
            "underneath: the window still closes on time.",
            15000, 0.2,
            [(0, 1.0), (kf, 0.0), (2 * kf, 0.5), (3 * kf, 2 / 3), (4 * kf, 0.0),
             (5 * kf, 0.0)],
        ),
        _phase_case(
            "rising_edge_aborts_score_window",
            "A confident in_match inside the score window aborts it and opens a "
            "NEW span — which is how back-to-back matches stay two segments.",
            15000, 0.2,
            [(0, 1.0), (kf, 0.0), (2 * kf, 1.0), (3 * kf, 1.0), (4 * kf, 0.0),
             (5 * kf, 0.0), (6 * kf, 0.0), (7 * kf, 0.0), (8 * kf, 0.0)],
        ),
        _phase_case(
            "zero_duration_skips_score_screen",
            "score_screen_duration_ms = 0 -> the falling edge lands straight in "
            "not_in_match; no frame is ever emitted as score_screen.",
            0, 0.2,
            [(0, 1.0), (kf, 1.0), (2 * kf, 0.0), (3 * kf, 0.0)],
        ),
        _phase_case(
            "doubt_margin_zero_is_9_13_parity",
            "doubt_margin = 0.0 disables doubt entirely and reproduces 9.13's "
            "hard-binary behaviour exactly — the same ratios, no doubt emitted.",
            15000, 0.0,
            [(0, 0.0), (kf, 2 / 3), (2 * kf, 1 / 3), (3 * kf, 0.5), (4 * kf, 1.0),
             (5 * kf, 0.0)],
        ),
        _phase_case(
            "eof_open_span",
            "A span still open at the last keyframe is closed at that keyframe, "
            "not dropped.",
            15000, 0.2,
            [(0, 0.0), (kf, 1.0), (2 * kf, 1.0), (3 * kf, 1.0)],
        ),
        _phase_case(
            "doubt_before_any_confident_frame",
            "Doubt while the machine has never left not_in_match holds there: a "
            "doubtful frame can never OPEN a span.",
            15000, 0.2,
            [(0, 0.5), (kf, 2 / 3), (2 * kf, 0.0), (3 * kf, 1.0), (4 * kf, 0.0),
             (5 * kf, 0.0), (6 * kf, 0.0), (7 * kf, 0.0), (8 * kf, 0.0)],
        ),
    ]

    # --- the real capture. Fires and expectations both come from the oracle, so
    #     this row set exercises the SHIPPED config's 134 rules, including its
    #     wrap-branch and full-circle rules, on real HUD-2.0 footage.
    modes = [r["mode"] for r in oracle["refs"]]
    mode_counts = {
        "normal": sum(1 for m in modes if m == MODE_NORMAL),
        "wrap": sum(1 for m in modes if m == MODE_WRAP),
        "full_circle": sum(1 for m in modes if m == MODE_FULL_CIRCLE),
    }
    fired_any = [False] * oracle["n_rules"]
    clear_any = [False] * oracle["n_rules"]
    for f in oracle["frames"]:
        bits = hex_to_bits(f["fires"], oracle["n_rules"])
        for i, b in enumerate(bits):
            if b:
                fired_any[i] = True
            else:
                clear_any[i] = True

    capture = {
        "note": (
            "Generated by video_oracle.py from the real capture: FFmpeg decode -> "
            "the pinned numpy BT.709 limited-range + nearest-chroma model -> Tool "
            "9's zone_fires_on_frame -> Tool 12's scoring.py/phases.py. No Kotlin "
            "and no TypeScript is involved in producing these expectations."
        ),
        "video": oracle["video"],
        "n_rules": oracle["n_rules"],
        "hud_version": oracle["hud_version"],
        "n_hud_zones": oracle["n_hud_zones"],
        "n_in_match_zones": oracle["n_in_match_zones"],
        "map_zone_counts": oracle["map_zone_counts"],
        "identification_threshold": oracle["identification_threshold"],
        "score_screen_duration_ms": oracle["score_screen_duration_ms"],
        "doubt_margin": oracle["doubt_margin"],
        "refs": oracle["refs"],
        "rule_mode_counts": mode_counts,
        "rules_that_fire_somewhere": sum(1 for b in fired_any if b),
        "wrap_rules_exercised_both_ways": sum(
            1 for i, m in enumerate(modes)
            if m == MODE_WRAP and fired_any[i] and clear_any[i]
        ),
        "full_circle_rules_exercised_both_ways": sum(
            1 for i, m in enumerate(modes)
            if m == MODE_FULL_CIRCLE and fired_any[i] and clear_any[i]
        ),
        "frames": [
            {
                "frame_idx": f["frame_idx"],
                "pts_us": f["pts_us"],
                "timestamp_ms": f["timestamp_ms"],
                "fires": f["fires"],
                "pred_hud": f["pred_hud"],
                "hud_conf": f["hud_conf"],
                "pred_in_match": f["pred_in_match"],
                "in_match_conf": f["in_match_conf"],
                "pred_map": f["pred_map"],
                "map_conf": f["map_conf"],
                "call": f["call"],
                "emitted": f["emitted"],
                "internal": f["internal"],
            }
            for f in oracle["frames"]
        ],
        "spans": oracle["spans"],
        "matches": oracle["matches"],
    }

    payload = {
        "story": "12.4c",
        "kind": "tool12-parity-fixture",
        "generated_by": "apps/mobile/bench/12-4c/video_oracle.py fixture",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "warning": (
            "COMMITTED, GENERATED. Every expectation here is Tool 12's own output "
            "(scoring.py / phases.py) — never hand-written. Regenerate with "
            "`video_oracle.py oracle` + `fixture`; do not edit by hand."
        ),
        "scoring_cases": [formulas, weights, empty],
        "phase_cases": phase_cases,
        "capture": capture,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    size = os.path.getsize(out_path)
    print(f"fixture -> {out_path} ({size/1024:.0f} kB)")
    print(f"  scoring cases: {len([formulas, weights, empty])}, "
          f"phase cases: {len(phase_cases)}, "
          f"capture keyframes: {len(capture['frames'])}")
    print(f"  rule modes: {mode_counts}, "
          f"wrap rules exercised both ways: "
          f"{capture['wrap_rules_exercised_both_ways']}, full-circle: "
          f"{capture['full_circle_rules_exercised_both_ways']}")
    return 0


# ---------------------------------------------------------------------------
# compare — AC10's gate
# ---------------------------------------------------------------------------


def compare(device_path: str, oracle_path: str, out_path: str, tol_us: int) -> int:
    with open(oracle_path, "r", encoding="utf-8") as fh:
        oracle = json.load(fh)
    with open(device_path, "r", encoding="utf-8") as fh:
        device = json.load(fh)

    n_rules = oracle["n_rules"]
    if int(device.get("n_rules", -1)) != n_rules:
        raise SystemExit(
            f"rule count differs: device {device.get('n_rules')} vs oracle "
            f"{n_rules}. Texel order would be misaligned; refusing to compare."
        )
    dev_refs = device.get("refs") or []
    if dev_refs:
        mismatch = [
            (i, d.get("zone_id"), o["zone_id"], d.get("owning_class"), o["owning_class"])
            for i, (d, o) in enumerate(zip(dev_refs, oracle["refs"]))
            if d.get("zone_id") != o["zone_id"] or d.get("owning_class") != o["owning_class"]
        ]
        if mismatch:
            raise SystemExit(
                "the device's rule ORDER differs from the oracle's at "
                f"{len(mismatch)} texels (first: {mismatch[0]}). This is the "
                "failure 12.2 lost a parity run to — every rule individually "
                "correct, the order wrong. Refusing to compare."
            )

    oracle_by_pts = {int(f["pts_us"]): f for f in oracle["frames"]}
    oracle_sorted = sorted(oracle_by_pts)

    matched = 0
    unmatched: list[int] = []
    disagreements = 0
    frames_with_disagreement = 0
    examples: list[str] = []
    per_rule = [0] * n_rules

    for df in device["frames"]:
        pts = int(df["pts_us"])
        of = oracle_by_pts.get(pts)
        if of is None:
            # Nearest within tolerance: MediaExtractor derives its sample time
            # from the container timescale with integer arithmetic, so an exact
            # match is not guaranteed even for the same sample.
            best, best_d = None, None
            for cand in oracle_sorted:
                d = abs(cand - pts)
                if best_d is None or d < best_d:
                    best, best_d = cand, d
            if best is not None and best_d is not None and best_d <= tol_us:
                of = oracle_by_pts[best]
            else:
                unmatched.append(pts)
                continue
        matched += 1
        dev_bits = hex_to_bits(df["fires"], n_rules)
        ora_bits = hex_to_bits(of["fires"], n_rules)
        bad = [i for i in range(n_rules) if dev_bits[i] != ora_bits[i]]
        if bad:
            frames_with_disagreement += 1
            disagreements += len(bad)
            for i in bad:
                per_rule[i] += 1
            if len(examples) < 10:
                r = oracle["refs"][bad[0]]
                examples.append(
                    f"pts={pts} rule {bad[0]} ({r['owning_class']}/{r['zone_id']}, "
                    f"mode={r['mode']}): device={dev_bits[bad[0]]} "
                    f"oracle={ora_bits[bad[0]]} (+{len(bad)-1} more on this frame)"
                )

    result = {
        "story": "12.4c",
        "kind": "ac10-video-parity",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "device_file": os.path.basename(device_path),
        "oracle_file": os.path.basename(oracle_path),
        "n_rules": n_rules,
        "device_keyframes": len(device["frames"]),
        "oracle_keyframes": len(oracle["frames"]),
        "frames_matched": matched,
        "frames_unmatched": len(unmatched),
        "unmatched_pts_us": unmatched[:20],
        "pts_tolerance_us": tol_us,
        "rule_frame_decisions": matched * n_rules,
        "frames_with_disagreement": frames_with_disagreement,
        "total_disagreements": disagreements,
        "exact_parity": disagreements == 0 and not unmatched,
        "worst_rules": sorted(
            [
                {
                    "texel": i,
                    "owning_class": oracle["refs"][i]["owning_class"],
                    "zone_id": oracle["refs"][i]["zone_id"],
                    "mode": oracle["refs"][i]["mode"],
                    "disagreements": c,
                }
                for i, c in enumerate(per_rule) if c
            ],
            key=lambda r: -r["disagreements"],
        )[:10],
        "examples": examples,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)

    print(json.dumps({k: v for k, v in result.items() if k != "worst_rules"}, indent=1))
    if result["exact_parity"]:
        print(f"\n✅ EXACT PARITY — 0 disagreements across "
              f"{result['rule_frame_decisions']} rule-frame decisions")
        return 0
    print(f"\n❌ {disagreements} disagreements across "
          f"{result['rule_frame_decisions']} rule-frame decisions")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("oracle", help="decode + evaluate the capture on the PC")
    o.add_argument("--video", required=True)
    o.add_argument("--out", default=DEFAULT_ORACLE)
    o.add_argument("--limit", type=int, default=0, help="stop after N keyframes")
    o.add_argument("--doubt-margin", type=float,
                   default=phases_mod.DEFAULT_DOUBT_MARGIN)

    f = sub.add_parser("fixture", help="oracle JSON -> the committed jest fixture")
    f.add_argument("--oracle", default=DEFAULT_ORACLE)
    f.add_argument("--out", default=DEFAULT_FIXTURE)

    c = sub.add_parser("compare", help="device analyzeSession JSON vs the oracle")
    c.add_argument("--device", required=True)
    c.add_argument("--oracle", default=DEFAULT_ORACLE)
    c.add_argument("--out", default=os.path.join(_HERE, "ac10_video_parity.json"))
    c.add_argument("--tol-us", type=int, default=1000)

    args = ap.parse_args()
    if args.cmd == "oracle":
        return run_oracle(args.video, args.out, args.limit, args.doubt_margin)
    if args.cmd == "fixture":
        return build_fixture(args.oracle, args.out)
    return compare(args.device, args.oracle, args.out, args.tol_us)


if __name__ == "__main__":
    raise SystemExit(main())
