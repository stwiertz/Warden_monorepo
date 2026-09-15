"""Tool 12 CLI — ``python -m tools.keyframe_engine_bench`` (AC1, E7).

argparse, not Typer/click (``architecture.md:281``). ``run()`` carries the core
logic and returns results; ``main()`` is the argparse entry (``:1002``).

Two deliverables, one engine (AC8b):

* ``<video>``     -> ms/keyframe + phase timeline + retroactive thumbnails
* ``--accuracy``  -> parity vs the Tool 9 CPU baseline on the labeled corpus
* ``--gate-glsl`` -> compile the shader under both dialects (AC6)
"""

import argparse
import csv
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_PKG_ROOT = os.path.dirname(_TOOLS)
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from tools.roi_detection_tester import load_map_config  # noqa: E402

from . import frames as frames_mod  # noqa: E402
from . import phases as phases_mod  # noqa: E402
from .lut import MAX_RULES, pack_rules  # noqa: E402
from .lut import decode_results  # noqa: E402
from .scoring import IN_MATCH_THRESHOLD, score_from_fires  # noqa: E402

# The decode-timing key utils/video.py._extract_iframes accumulates into the
# caller's profile_stats dict (video.py:272,295). Named here rather than
# inlined because the decode-bound thesis is the story's headline: if this key
# ever moves, _run_video must fail loudly rather than report decode as 0.000.
_DECODE_STAT_KEY = "ffmpeg_read"

# AC14 — verbatim, and it travels with every number this tool prints.
REFERENCE_DEVICE_NOTE = (
    "A PC number is NEVER a mobile number. Every figure here is FEASIBILITY / "
    "RELATIVE SPEEDUP only and binds neither PERF-002 nor PERF-010. Only Story "
    "12.2, running on the reference device (Poco X5 Pro 5G, SM7325/A14, Adreno "
    "642L), can bind those; Story 12.3 re-baselines. The <10 s target is the "
    "aspiration, not an AC."
)


def _default_config() -> str:
    return os.path.join(_PKG_ROOT, "output", "map_configs", "map_config.v2.json")


def _default_labeled_root() -> str:
    return os.path.join(_PKG_ROOT, "output", "labeled")


def _write_json(payload: dict, out_path: str) -> None:
    """Deterministic write (REL-005): fixed key order, UTF-8, trailing newline."""
    text = json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    Path(out_path).write_text(text, encoding="utf-8")


def _write_png(frame_bgr: np.ndarray, out_path: str) -> bool:
    """Windows non-ASCII-path-safe PNG write — ``imencode`` + ``open().write()``.
    NEVER ``cv2.imwrite`` (hard convention)."""
    ok, buf = cv2.imencode(".png", frame_bgr)
    if not ok:
        return False
    with open(out_path, "wb") as fh:
        fh.write(buf.tobytes())
    return True


def _config_extras(config_path: str, config) -> tuple[tuple[int, int], int]:
    """``((width, height), score_screen_duration_ms)`` read from the raw config.

    Tool 9's ``MapConfig`` carries neither ``reference_resolution.width`` (its
    ``_resize_to_ref`` is aspect-preserving, so it never needs one) nor
    ``score_screen_duration_ms`` (Tool 9 is a per-frame classifier with no state
    machine). Both are required by the unified schema and both are needed here,
    and Tool 9 is READ-ONLY under AC18 — so they are read straight from the JSON.
    ``utf-8-sig`` per the BOM-tolerant config-read convention.
    """
    with open(config_path, "r", encoding="utf-8-sig") as fh:
        raw = json.load(fh)

    ref = raw.get("reference_resolution") or {}
    width = ref.get("width")
    if not isinstance(width, int) or width < 1:
        width = int(round(config.ref_height * 16.0 / 9.0 / 2.0) * 2)
        print(
            f"  WARN: reference_resolution.width missing/invalid — assuming "
            f"{width} (16:9 at height {config.ref_height})",
            file=sys.stderr,
        )

    dur = raw.get("score_screen_duration_ms")
    if not isinstance(dur, int) or isinstance(dur, bool) or dur < 0:
        raise ValueError(
            f"config '{config_path}': 'score_screen_duration_ms' must be a "
            f"non-negative integer, got {dur!r}"
        )

    return (int(width), int(config.ref_height)), int(dur)


def _profile_gpu(config, packed, frame_size) -> int:
    """Decompose the GPU cost: upload vs shader work vs readback stall.

    Why this exists as a mode rather than a one-off script: the per-stage numbers
    in the run output are MISATTRIBUTED by construction. GL uploads are
    asynchronous, so wall-clocking `upload()` returns before the transfer lands
    and the blocking `draw_and_read()` silently absorbs the remainder. The TOTAL
    is honest; the split is not. This forces completion per stage to get the
    true split, and it is the number 12.2/12.3 actually need: it says how much of
    the GPU cost the Android zero-copy path would remove.
    """
    from .shader import MegaShader

    w, h = frame_size
    # Seeded: this mode's output is quoted as a decision input for 12.2/12.3, so
    # it must be reproducible run-to-run. Upload cost is content-independent, but
    # shader cost is not entirely — branch coherence across the wrap/full-circle
    # modes varies with pixel content. Synthetic noise is still not HUD-
    # representative; it is an upper bound on branch divergence, which is the
    # conservative direction for a "GPU is cheap enough" claim.
    frame = np.random.default_rng(12_1).integers(
        0, 256, (h, w, 3), dtype=np.uint8
    )

    def timeit(fn, n=200, warmup=20):
        for _ in range(warmup):
            fn()
        ts = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn()
            ts.append(time.perf_counter() - t0)
        ts.sort()
        return ts[len(ts) // 2] * 1000.0   # median — robust to scheduler noise

    with MegaShader(packed.texture, (w, h)) as gpu:
        ctx, mgl = gpu.ctx, gpu._mgl

        def draw():
            gpu.fbo.use()
            ctx.viewport = (0, 0, MAX_RULES, 1)
            gpu.frame_tex.use(0)
            gpu.rules_tex.use(1)
            gpu.vao.render(mgl.TRIANGLES, vertices=3)

        upload = timeit(lambda: (gpu.upload(frame), ctx.finish()))
        shader = timeit(lambda: (draw(), ctx.finish()))
        shader_read = timeit(lambda: (draw(), gpu.fbo.read(components=4, dtype="f1")))
        full = timeit(lambda: (gpu.upload(frame), gpu.draw_and_read()))
        info = dict(gpu.info)

    stall = max(0.0, shader_read - shader)
    total = upload + shader + stall
    print(f"GPU cost decomposition @ {w}x{h}, {packed.n_rules} rules  (median of 200)")
    print(f"  {info['GL_RENDERER']} / {info['GL_VERSION']}\n")
    print(f"  upload  (frame CPU->GPU, {w * h * 3 / 1e6:.1f} MB)  {upload:7.3f} ms   "
          f"{upload / total * 100:4.1f}%")
    print(f"  shader  (rule evaluation)          {shader:7.3f} ms   "
          f"{shader / total * 100:4.1f}%")
    print(f"  readback stall (600 B)             {stall:7.3f} ms   "
          f"{stall / total * 100:4.1f}%")
    print(f"  ----------------------------------------------------")
    print(f"  sum of stages                      {total:7.3f} ms")
    print(f"  full path, measured end-to-end     {full:7.3f} ms")
    print()
    print("  Stages are timed with a forced completion each, so they do not sum")
    print("  exactly to the full path (~5% scheduler/driver noise). The ranking is")
    print("  what is robust: upload dominates by more than an order of magnitude.")
    print()
    print(f"  Non-blocking readback (PBO ping-pong) could recover at most "
          f"{stall:.3f} ms/frame -- noise.")
    print(f"  Zero-copy decode->texture (Android) would remove the {upload:.3f} ms")
    print(f"  upload, leaving ~{shader_read:.3f} ms of actual GPU cost.")
    print("\n" + REFERENCE_DEVICE_NOTE)
    return 0


def _gate_glsl() -> int:
    from .shader import GlslangNotFoundError, gate_both_dialects

    print("GLSL gate (AC6) — glslangValidator, both dialects:")
    # "the gate did not run" and "the gate ran and rejected the shader" are
    # opposite facts. Collapsing them into one [FAIL] line lets a box with no
    # glslang installed report exactly what a non-conformant shader reports —
    # and this gate is the ONLY thing standing between desktop-permissive GLSL
    # and an Adreno failure in 12.2. Exit 2 (not 1) so CI can tell them apart.
    try:
        with tempfile.TemporaryDirectory() as d:
            results = gate_both_dialects(d)
    except GlslangNotFoundError as exc:
        print(f"\nGATE NOT RUN: {exc}", file=sys.stderr)
        return 2
    failed = 0
    for stage, version, ok, msg in results:
        print(f"  [{'OK ' if ok else 'FAIL'}] {stage:4s}  {version}")
        if not ok:
            failed += 1
            print("        " + (msg or "").replace("\n", "\n        "))
    if failed:
        print(f"\n{failed} shader variant(s) FAILED the ES-3.0 subset gate.", file=sys.stderr)
        return 1
    print("\nAll variants compile. The body is ES-3.0-subset clean (E2).")
    return 0


def _run_accuracy(config, packed, frame_size, labeled_root, limit_per_class,
                  baseline_csv, cpu_compare=0):
    """GPU vs CPU parity over the labeled corpus (AC11/AC12/AC13/Task 8)."""
    from .shader import MegaShader

    exp_w, exp_h = frame_size
    rows = []
    n_skipped = 0
    timing = {"upload_s": 0.0, "shader_s": 0.0, "read_s": 0.0}

    # Validate the baseline CSV BEFORE the expensive loop. _compare_to_baseline
    # runs after all 2666 frames; a missing file or a missing column there
    # discards a completed GPU run for a fault knowable up front.
    if baseline_csv:
        _validate_baseline_csv(baseline_csv)

    with MegaShader(packed.texture, (exp_w, exp_h)) as gpu:
        gl_info = dict(gpu.info)
        for sf in frames_mod.iter_labeled_frames(
            labeled_root, config.ref_height, limit_per_class=limit_per_class
        ):
            h, w = sf.frame_bgr.shape[0], sf.frame_bgr.shape[1]
            if (w, h) != (exp_w, exp_h):
                n_skipped += 1
                print(
                    f"  WARN: {sf.path} is {w}x{h}, expected {exp_w}x{exp_h} "
                    f"— skipping (rules were packed against the reference frame)",
                    file=sys.stderr,
                )
                continue
            t0 = time.perf_counter()
            gpu.upload(sf.frame_bgr)
            t1 = time.perf_counter()
            rgba = gpu.draw_and_read()
            t2 = time.perf_counter()
            timing["upload_s"] += t1 - t0
            timing["shader_s"] += t2 - t1

            fires = decode_results(rgba, packed.n_rules)
            scores = score_from_fires(
                fires, packed, config, folder=sf.folder, hud_dir=sf.hud_dir
            )
            rows.append((sf, scores))

    from tools.common.labels import MAP_LABELS
    from tools.roi_detection_tester import _folder_to_in_match, _normalize_hud

    def _acc(pairs):
        n = len(pairs)
        c = sum(1 for gt, pr in pairs if gt == pr)
        return (c / float(n) if n else 0.0), n, c

    hud_pairs = [(_normalize_hud(sf.hud_dir), sc.pred_hud) for sf, sc in rows]
    im_pairs = [
        (_folder_to_in_match(sf.folder), sc.pred_in_match)
        for sf, sc in rows if sc.pred_in_match is not None
    ]
    map_pairs = [
        (sf.folder, sc.pred_map)
        for sf, sc in rows if sf.folder in MAP_LABELS and sc.pred_map is not None
    ]

    hud_acc, hud_n, hud_c = _acc(hud_pairs)
    im_acc, im_n, im_c = _acc(im_pairs)
    map_acc, map_n, map_c = _acc(map_pairs)

    parity = _compare_to_baseline(rows, baseline_csv) if baseline_csv else None

    n = len(rows)
    # A run that evaluated nothing must NOT return a well-formed payload with
    # accuracy 0.0 on all three classifiers — that is indistinguishable from a
    # genuine result and would be read as one. The common cause is a config/
    # corpus resolution mismatch (or a fabricated 16:9 reference width), which
    # rejects every frame at the guard above.
    if n == 0:
        raise ValueError(
            f"no frames were evaluated ({n_skipped} skipped for size mismatch, "
            f"expected {exp_w}x{exp_h}). Nothing was measured — check that "
            f"{labeled_root!r} holds PNGs and that the config's "
            f"reference_resolution matches the corpus."
        )
    if n_skipped:
        print(
            f"  WARN: {n_skipped} frame(s) skipped for size mismatch; accuracy "
            f"below is over the {n} surviving frame(s) only.",
            file=sys.stderr, flush=True,
        )
    gpu_ms = (timing["upload_s"] + timing["shader_s"]) * 1000.0 / n
    cpu_timing = None
    if cpu_compare:
        cpu_timing = _time_cpu_rule_eval(config, labeled_root, cpu_compare)
        cpu_timing["gpu_ms_per_frame"] = round(gpu_ms, 6)
        cpu_timing["speedup"] = (
            round(cpu_timing["ms_per_frame"] / gpu_ms, 2) if gpu_ms > 0 else None
        )

    return {
        "gl": gl_info,
        "n_frames": n,
        # Explicit, not implied: without it a shrinking denominator is invisible
        # and "accuracy 1.0" over 3 surviving frames reads like 1.0 over 2666.
        "n_frames_skipped_size_mismatch": n_skipped,
        "cpu_vs_gpu_rule_eval": cpu_timing,
        "accuracy": {
            "hud_version_classifier": {"accuracy": round(hud_acc, 6), "n_evaluated": hud_n, "n_correct": hud_c},
            "in_match_classifier": {"accuracy": round(im_acc, 6), "n_evaluated": im_n, "n_correct": im_c},
            "map_id_classifier": {"accuracy": round(map_acc, 6), "n_evaluated": map_n, "n_correct": map_c},
        },
        "per_frame_parity_vs_tool9": parity,
        "timing_ms_per_frame": {
            "upload": round(timing["upload_s"] * 1000.0 / n, 6) if n else 0.0,
            "shader_and_readback": round(timing["shader_s"] * 1000.0 / n, 6) if n else 0.0,
        },
    }


def _time_cpu_rule_eval(config, labeled_root, n_frames):
    """Time the CPU rule-evaluation path over the first ``n_frames`` of the corpus.

    This is the ENGINE-vs-ENGINE comparison AC11/AC14 need: Tool 9's total
    runtime is not comparable (it also decodes PNGs, aggregates metrics and
    writes reports), so this times exactly the work the shader replaces —
    ``zone_fires_on_frame`` over every rule — and nothing else. Frame decode is
    excluded from BOTH sides.

    NB it re-walks ``iter_labeled_frames`` from scratch rather than reusing the
    frames the GPU pass held: those are deliberately not retained (AC2 — never
    accumulate). Since decode sits outside the timer on both sides, the measured
    rule-eval cost is unaffected; the two passes see the same frames in the same
    order, not the same in-memory buffers.
    """
    from tools.roi_detection_tester import zone_fires_on_frame

    zones = (
        list(config.hud_version_detection)
        + list(config.in_match_detection)
        + [z for zs in config.map_zones.values() for z in zs]
    )
    frames_seen = 0
    elapsed = 0.0
    for sf in frames_mod.iter_labeled_frames(labeled_root, config.ref_height):
        if frames_seen >= n_frames:
            break
        t0 = time.perf_counter()
        for z in zones:
            zone_fires_on_frame(z, sf.frame_bgr)
        elapsed += time.perf_counter() - t0
        frames_seen += 1
    return {
        "n_frames": frames_seen,
        "n_rules": len(zones),
        "ms_per_frame": round(elapsed * 1000.0 / frames_seen, 6) if frames_seen else 0.0,
    }


# Columns _compare_to_baseline reads out of Tool 9's --save-frame-predictions CSV.
_BASELINE_COLUMNS = (
    "frame_path",
    "predicted_hud_version",
    "predicted_in_match",
    "predicted_map_id",
)


def _validate_baseline_csv(baseline_csv: str) -> None:
    """Fail fast on an unusable baseline CSV, BEFORE the 2666-frame GPU loop.

    Without this the comparison runs last: a missing file raises OSError and a
    missing column raises KeyError, in both cases after the entire accuracy run
    has completed — throwing away minutes of work for a fault that was knowable
    from the header alone.
    """
    with open(baseline_csv, "r", encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh), None)
    if header is None:
        raise ValueError(f"baseline CSV {baseline_csv!r} is empty")
    missing = [c for c in _BASELINE_COLUMNS if c not in header]
    if missing:
        raise ValueError(
            f"baseline CSV {baseline_csv!r} is missing required column(s): "
            f"{', '.join(missing)}. Expected Tool 9's --save-frame-predictions "
            f"output (frame_predictions.csv)."
        )


def _compare_to_baseline(rows, baseline_csv):
    """Frame-for-frame GPU-vs-Tool-9 agreement — the strongest parity check.

    Aggregate accuracy matching is necessary but not sufficient: two engines can
    hit the same accuracy while disagreeing on which frames they get right. This
    compares the actual per-frame predictions.
    """
    by_path: dict[str, dict] = {}
    with open(baseline_csv, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            by_path[os.path.normcase(os.path.abspath(row["frame_path"]))] = row

    matched = 0
    dis = {"hud": 0, "in_match": 0, "map": 0}
    examples: list[str] = []
    for sf, sc in rows:
        key = os.path.normcase(os.path.abspath(sf.path or ""))
        ref = by_path.get(key)
        if ref is None:
            continue
        matched += 1
        if ref["predicted_hud_version"] != sc.pred_hud:
            dis["hud"] += 1
            if len(examples) < 10:
                examples.append(f"hud {sf.path}: cpu={ref['predicted_hud_version']} gpu={sc.pred_hud}")
        cpu_im = ref["predicted_in_match"] or None
        if cpu_im != sc.pred_in_match:
            dis["in_match"] += 1
            if len(examples) < 10:
                examples.append(f"in_match {sf.path}: cpu={cpu_im} gpu={sc.pred_in_match}")
        cpu_map = ref["predicted_map_id"] or None
        if cpu_map != sc.pred_map:
            dis["map"] += 1
            if len(examples) < 10:
                examples.append(f"map {sf.path}: cpu={cpu_map} gpu={sc.pred_map}")

    total = dis["hud"] + dis["in_match"] + dis["map"]
    return {
        "baseline_csv": baseline_csv,
        "frames_matched": matched,
        "disagreements": dis,
        "total_disagreements": total,
        "exact_parity": total == 0,
        "examples": examples,
    }


def _run_video(
    config, packed, frame_size, score_screen_duration_ms, video_path, out_dir,
    doubt_margin, thumbnails, config_name,
):
    """ms/keyframe + phase timeline + retroactive thumbnails (AC9/AC10/AC11)."""
    from .shader import MegaShader

    exp_w, exp_h = frame_size
    prof: dict = {}
    ring = phases_mod.KeyframeRing()
    resolver = phases_mod.PhaseResolver(score_screen_duration_ms)

    timeline: list[dict] = []
    calls: list[tuple[int, int, str]] = []
    internal: list[str] = []
    map_agg: list[dict] = []
    thumbs: list[dict] = []

    t_upload = t_shader = 0.0
    n_skipped = 0
    prev_state = None
    prev_internal = None

    with MegaShader(packed.texture, (exp_w, exp_h)) as gpu:
        gl_info = dict(gpu.info)
        # Wall clock starts AFTER context creation, GLSL compile and the
        # self-test. Those are one-off setup, not per-keyframe cost, and
        # amortizing them into ms/keyframe overstates the steady-state number
        # that 12.2 re-measures on a device where context creation is far more
        # expensive and the keyframe count may be much smaller.
        t_wall0 = time.perf_counter()
        for sf in frames_mod.iter_video_keyframes(
            video_path, config.ref_height, profile_stats=prof
        ):
            h, w = sf.frame_bgr.shape[0], sf.frame_bgr.shape[1]
            if (w, h) != (exp_w, exp_h):
                n_skipped += 1
                print(
                    f"  WARN: keyframe {sf.frame_idx} is {w}x{h}, expected "
                    f"{exp_w}x{exp_h} — skipping",
                    file=sys.stderr,
                )
                continue

            t0 = time.perf_counter()
            gpu.upload(sf.frame_bgr)
            t1 = time.perf_counter()
            rgba = gpu.draw_and_read()
            t2 = time.perf_counter()
            t_upload += t1 - t0
            t_shader += t2 - t1

            fires = decode_results(rgba, packed.n_rules)
            scores = score_from_fires(fires, packed, config)

            call = phases_mod.in_match_call(
                scores.in_match_conf, doubt_margin=doubt_margin
            )
            state = resolver.push(sf.timestamp_ms, call)
            calls.append((sf.frame_idx, sf.timestamp_ms, call))
            internal.append(resolver.state)
            timeline.append({
                "frame_idx": sf.frame_idx,
                "timestamp_ms": sf.timestamp_ms,
                "state": state,
                "confidence": round(float(scores.in_match_conf), 6),
            })
            map_agg.append(scores.map_scores)

            # AC9 — 3-keyframe ring; on a PHASE CHANGE at N, emit frame N-2.
            #
            # Triggered on the INTERNAL state, not the emitted one. `doubt` is an
            # emitted-only outcome: by AC8's design a doubtful frame HOLDS the
            # machine and does not split a span (`internal` never contains
            # doubt). Testing the emitted state would make every
            # in_match -> doubt -> in_match blip look like two phase changes and
            # write two thumbnails for a transition that did not occur — with
            # filenames outside 9.13's phase vocabulary to boot.
            ring.push(sf.frame_idx, sf.timestamp_ms, sf.frame_bgr)
            cur_internal = resolver.state
            if prev_internal is not None and cur_internal != prev_internal:
                retro = ring.retro()
                if retro is not None and thumbnails:
                    r_idx, r_ts, r_frame = retro
                    name = f"phase_{prev_internal}_to_{cur_internal}_kf{r_idx:06d}.png"
                    if _write_png(r_frame, os.path.join(out_dir, name)):
                        thumbs.append({
                            "file": name, "at_frame_idx": sf.frame_idx,
                            "emitted_frame_idx": r_idx, "emitted_timestamp_ms": r_ts,
                            "transition": f"{prev_internal}->{cur_internal}",
                        })
                    else:
                        print(
                            f"  WARN: could not encode thumbnail {name} — the "
                            f"{prev_internal}->{cur_internal} transition at "
                            f"keyframe {sf.frame_idx} has no thumbnail.",
                            file=sys.stderr, flush=True,
                        )
            prev_state = state
            prev_internal = cur_internal

    wall = time.perf_counter() - t_wall0
    n = len(timeline)
    spans = phases_mod.spans_from_states(calls, internal)

    matches = []
    for start, end in spans:
        agg: dict[str, float] = {}
        for row, (idx, _ts, _c) in zip(map_agg, calls):
            if start <= idx <= end:
                for slug, v in row.items():
                    agg[slug] = agg.get(slug, 0.0) + v
        if agg:
            best = max(agg, key=lambda s: agg[s])
            conf = agg[best]
        else:
            best, conf = "unknown", 0.0
        matches.append({
            "start_frame": start, "end_frame": end,
            "map_id": best, "confidence": round(float(conf), 6),
        })

    if n == 0:
        raise ValueError(
            f"no keyframes were evaluated ({n_skipped} skipped for size "
            f"mismatch, expected {exp_w}x{exp_h}). Nothing was measured — check "
            f"that {video_path!r} decodes and that the config's "
            f"reference_resolution matches it."
        )
    if n_skipped:
        print(
            f"  WARN: {n_skipped} keyframe(s) skipped for size mismatch; the "
            f"timeline and timings below cover the {n} surviving keyframe(s) "
            f"only, and AC9's 'two keyframes back' means two SURVIVING "
            f"keyframes back.",
            file=sys.stderr, flush=True,
        )

    # decode_s underpins the story's central decode-bound claim, so a missing
    # stat must not silently degrade it to 0.000 ms/kf (which would also
    # suppress gpu_speedup_vs_decode via its falsy check and report the thesis
    # as unmeasured rather than as broken).
    if _DECODE_STAT_KEY not in prof:
        raise RuntimeError(
            f"the decoder reported no {_DECODE_STAT_KEY!r} timing "
            f"(got keys: {sorted(prof)}). decode_s underpins the decode-bound "
            f"measurement — refusing to report it as 0.0."
        )
    decode_s = float(prof[_DECODE_STAT_KEY])
    return {
        "gl": gl_info,
        "video": os.path.basename(video_path),
        "n_keyframes": n,
        "n_keyframes_skipped_size_mismatch": n_skipped,
        "timing": {
            "wall_s": round(wall, 6),
            "decode_s": round(decode_s, 6),
            "upload_s": round(t_upload, 6),
            "shader_and_readback_s": round(t_shader, 6),
            "ms_per_keyframe_total": round(wall * 1000.0 / n, 6),
            "ms_per_keyframe_decode": round(decode_s * 1000.0 / n, 6),
            "ms_per_keyframe_upload": round(t_upload * 1000.0 / n, 6),
            "ms_per_keyframe_shader": round(t_shader * 1000.0 / n, 6),
            "gpu_speedup_vs_decode": (
                round(decode_s / (t_upload + t_shader), 2)
                if (t_upload + t_shader) > 0 else None
            ),
        },
        "results": {
            "hud_version": config.hud_version,
            # 9.13's shape carries `video` and `stride` at top level; both are
            # part of "verbatim". stride is 1 by construction here — this engine
            # evaluates every keyframe, it does not subsample.
            "video": os.path.basename(video_path),
            "stride": 1,
            "config": config_name,
            "frames": timeline,
            "matches": matches,
        },
        "thumbnails": thumbs,
    }


def run(
    video: str | None = None,
    *,
    config_path: str | None = None,
    accuracy: bool = False,
    labeled_root: str | None = None,
    limit_per_class: int | None = None,
    baseline_csv: str | None = None,
    out_dir: str | None = None,
    doubt_margin: float = phases_mod.DEFAULT_DOUBT_MARGIN,
    thumbnails: bool = True,
    cpu_compare: int = 0,
) -> dict:
    """Core logic. Returns the results dict; writes deliverables under ``out_dir``."""
    cfg_path = config_path or _default_config()
    config = load_map_config(cfg_path)

    frame_size, score_dur_ms = _config_extras(cfg_path, config)
    ref_w, ref_h = frame_size
    packed = pack_rules(config, (ref_h, ref_w, 3))
    print(
        f"Packed {packed.n_rules} rules (of {MAX_RULES} texels) from "
        f"{os.path.basename(cfg_path)} @ {ref_w}x{ref_h}"
    )

    if accuracy:
        root = labeled_root or _default_labeled_root()
        out = out_dir or os.path.join(_PKG_ROOT, "output", "keyframe_engine_bench")
        os.makedirs(out, exist_ok=True)
        payload = _run_accuracy(
            config, packed, frame_size, root, limit_per_class, baseline_csv,
            cpu_compare=cpu_compare,
        )
        payload["reference_device_note"] = REFERENCE_DEVICE_NOTE
        _write_json(payload, os.path.join(out, "accuracy.json"))
        print(f"\nWrote {os.path.join(out, 'accuracy.json')}")
        return payload

    if not video:
        raise ValueError("a video path is required unless --accuracy is given")

    stem = Path(video).stem
    out = out_dir or os.path.join(_PKG_ROOT, "output", stem)
    os.makedirs(out, exist_ok=True)
    payload = _run_video(
        config, packed, frame_size, score_dur_ms, video, out, doubt_margin,
        thumbnails, os.path.basename(cfg_path),
    )
    payload["reference_device_note"] = REFERENCE_DEVICE_NOTE
    # AC10 — 9.13's results.json shape, verbatim (+ the extended state enum).
    _write_json(payload["results"], os.path.join(out, "results.json"))
    _write_json(payload, os.path.join(out, "bench.json"))
    print(f"\nWrote {os.path.join(out, 'results.json')} + bench.json")
    return payload


def _parse_args(argv):
    p = argparse.ArgumentParser(
        prog="python -m tools.keyframe_engine_bench",
        description=(
            "Tool 12 — keyframe-only decode + GPU mega-shader bench (Story 12.1). "
            "Reports ms/keyframe AND accuracy parity vs the Tool 9 CPU baseline."
        ),
        epilog=REFERENCE_DEVICE_NOTE,
    )
    p.add_argument("video", nargs="?", help="video to bench (omit with --accuracy)")
    p.add_argument("--config", default=None, help="map_config.<hud>.json (default: latest v2)")
    p.add_argument("--accuracy", action="store_true",
                   help="run the accuracy comparison on the labeled corpus instead")
    p.add_argument("--labeled-root", default=None, help="labeled corpus root")
    p.add_argument("--limit-per-class", type=int, default=None,
                   help="cap frames per class (smoke runs)")
    p.add_argument("--baseline-csv", default=None,
                   help="Tool 9 frame_predictions.csv for per-frame parity")
    p.add_argument("--cpu-compare", type=int, default=0, metavar="N",
                   help="also time the CPU rule-eval path on the first N frames "
                        "(engine-vs-engine speedup; decode excluded from both)")
    p.add_argument("--out", default=None, help="output directory")
    p.add_argument("--doubt-margin", type=float, default=phases_mod.DEFAULT_DOUBT_MARGIN,
                   help="split-vote band around the in_match threshold; 0 disables doubt")
    p.add_argument("--no-thumbnails", action="store_true", help="skip retroactive thumbnails")
    p.add_argument("--gate-glsl", action="store_true",
                   help="compile the shader under both dialects and exit (AC6)")
    p.add_argument("--profile-gpu", action="store_true",
                   help="decompose the GPU cost (upload vs shader vs readback "
                        "stall) and exit; the run output's split is misattributed "
                        "because GL uploads are async")
    return p.parse_args(argv)


# Every failure class that can reach main() and deserves a diagnosed `error: ...`
# + exit 1 rather than a raw traceback through wardentooling's run_tool:
#   ValueError               — config/LUT validation (pack_rules, _config_extras)
#   OSError                  — file I/O, and CalledProcessError (an OSError
#                              subclass) from ffprobe on a corrupt input
#   RuntimeError             — check_ffmpeg()/get_video_info() PATH+stream
#                              guards, and MegaShader._selftest(), which is the
#                              single most likely failure on a flaky driver
#   ImportError              — moderngl not installed
#   KeyError                 — a --baseline-csv missing a required column
# moderngl.Error is caught via its own base class at the call site (see _gl_errors).
_DIAGNOSED = (ValueError, OSError, RuntimeError, ImportError, KeyError)


def main(argv=None) -> int:
    args = _parse_args(argv)

    if args.limit_per_class is not None and args.limit_per_class < 1:
        print("error: --limit-per-class must be >= 1", file=sys.stderr)
        return 2
    if args.cpu_compare < 0:
        print("error: --cpu-compare must be >= 0", file=sys.stderr)
        return 2
    # A margin at or above the threshold makes EVERY ratio in (0, 1) fall inside
    # the split-vote band, so every keyframe calls `doubt` (a hold) and the state
    # machine can only ever advance on a ratio of exactly 0.0 or 1.0: the
    # timeline goes near-uniformly `doubt` and `matches` comes back empty. That
    # is a silently useless run, not a strict one.
    if args.doubt_margin < 0.0:
        print("error: --doubt-margin must be >= 0", file=sys.stderr)
        return 2
    if args.doubt_margin >= IN_MATCH_THRESHOLD:
        print(
            f"error: --doubt-margin must be < the in_match threshold "
            f"({IN_MATCH_THRESHOLD}); at {args.doubt_margin} every "
            f"frame calls doubt, the state machine never advances, and the run "
            f"yields an all-doubt timeline with no matches.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.gate_glsl:
            return _gate_glsl()

        if args.profile_gpu:
            cfg_path = args.config or _default_config()
            config = load_map_config(cfg_path)
            frame_size, _ = _config_extras(cfg_path, config)
            packed = pack_rules(config, (frame_size[1], frame_size[0], 3))
            return _profile_gpu(config, packed, frame_size)

        if not args.video and not args.accuracy:
            print("error: give a video path, --accuracy, --gate-glsl, or --profile-gpu",
                  file=sys.stderr)
            return 2
        if args.video and args.accuracy:
            # --accuracy runs the labeled-PNG corpus and returns before `video`
            # is ever consulted (AC8b: two corpora, one engine). Silently
            # ignoring a named video reads as "it was benched".
            print(f"  WARN: --accuracy runs the labeled corpus; the video "
                  f"argument {args.video!r} is NOT benched. Drop --accuracy to "
                  f"bench it.", file=sys.stderr, flush=True)

        payload = run(
            args.video,
            config_path=args.config,
            accuracy=args.accuracy,
            labeled_root=args.labeled_root,
            limit_per_class=args.limit_per_class,
            baseline_csv=args.baseline_csv,
            out_dir=args.out,
            doubt_margin=args.doubt_margin,
            thumbnails=not args.no_thumbnails,
            cpu_compare=args.cpu_compare,
        )
    except _DIAGNOSED as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.accuracy:
        a = payload["accuracy"]
        print("\nGPU accuracy (in-sample PARITY TARGET, not a generalization claim):")
        for k, v in a.items():
            print(f"  {k:26s} {v['accuracy']:.4f}  ({v['n_correct']}/{v['n_evaluated']})")
        par = payload.get("per_frame_parity_vs_tool9")
        if par:
            verdict = "EXACT" if par["exact_parity"] else "DIVERGENT"
            print(f"\nPer-frame parity vs Tool 9: {verdict} "
                  f"({par['total_disagreements']} disagreement(s) over "
                  f"{par['frames_matched']} frames)")
        cpu = payload.get("cpu_vs_gpu_rule_eval")
        if cpu:
            print(f"\nRule-eval cost over {cpu['n_rules']} rules "
                  f"({cpu['n_frames']} frames, decode excluded from both):")
            print(f"  CPU (cv2.inRange) {cpu['ms_per_frame']:8.3f} ms/frame")
            print(f"  GPU (mega-shader) {cpu['gpu_ms_per_frame']:8.3f} ms/frame")
            if cpu["speedup"]:
                print(f"  -> {cpu['speedup']}x")
    else:
        t = payload["timing"]
        print(f"\nKeyframes: {payload['n_keyframes']}")
        print(f"  decode        {t['ms_per_keyframe_decode']:8.3f} ms/kf  ({t['decode_s']:.2f} s)")
        print(f"  upload        {t['ms_per_keyframe_upload']:8.3f} ms/kf  ({t['upload_s']:.2f} s)")
        print(f"  shader+read   {t['ms_per_keyframe_shader']:8.3f} ms/kf  ({t['shader_and_readback_s']:.2f} s)")
        print(f"  TOTAL (wall)  {t['ms_per_keyframe_total']:8.3f} ms/kf  ({t['wall_s']:.2f} s)")
        if t["gpu_speedup_vs_decode"]:
            print(f"\n  decode is {t['gpu_speedup_vs_decode']}x the GPU cost — decode-bound.")

    print("\n" + REFERENCE_DEVICE_NOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
