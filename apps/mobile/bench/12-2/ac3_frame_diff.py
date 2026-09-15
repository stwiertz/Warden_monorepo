"""Story 12.2 AC3 — PC-vs-device frame diff, in OpenCV HSV units.

12.1's literal instruction: "Gate 12.2 on a cheap PC-vs-device frame diff before
any rule-porting work." This compares the SAME keyframe of the SAME capture,
decoded on PC via FFmpeg `rgb24` and on device via each colour path, and reports
ΔH/ΔS/ΔV as a mean AND as a distribution over the 68 low-saturation rule regions
specifically — because those are the ones that matter.

DIAGNOSTIC SIGNATURES (12.1, measured):

  ~16 offset / ~9% gain  => RANGE error (limited->full): ΔS 19.68, ΔV 7.64, ΔH 1.22
  saturated-hue shift,
  greys stable           => MATRIX error (709->601):     ΔS  1.64, ΔV 0.43, ΔH 1.12

A clean Path P must show ΔH = ΔS = ΔV = 0 against FFmpeg. If it does not, the
YUV->RGB constants are wrong and every downstream number is unanchored — STOP and
fix before proceeding.

    cd apps/tooling
    uv run python ../mobile/bench/12-2/ac3_frame_diff.py <pc.png> <device.png> [...]
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLING = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "tooling"))
if _TOOLING not in sys.path:
    sys.path.insert(0, _TOOLING)

from tools.keyframe_engine_bench.lut import pack_rules  # noqa: E402
from tools.roi_detection_tester import load_map_config  # noqa: E402

REF_W, REF_H = 1920, 1080
CONFIG = os.path.join(_TOOLING, "output", "map_configs", "map_config.v2.json")
# The low-saturation cut that defines the exposed population: 68 of the 134
# shipped rules sit at s_center <= 8 having surrendered hue (h_tol = 180).
LOW_SAT_S_CENTER_MAX = 8

# The per-channel BGR residual a chroma-upsampling policy difference can produce.
# Nearest-neighbour vs interpolated chroma moves a pixel between two ADJACENT
# chroma samples, so the error is bounded by the local chroma gradient and, on
# these captures, measured at <= 3/255. A wrong matrix or range is affine in the
# pixel's own chroma and has no such bound — which is what makes this the
# discriminator AC3's stop rule actually needed.
CHROMA_UPSAMPLING_MAX_BGR = 3


def load_bgr(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"cannot read {path}")
    if img.shape[:2] != (REF_H, REF_W):
        raise SystemExit(f"{path} is {img.shape[1]}x{img.shape[0]}, expected {REF_W}x{REF_H}")
    return img


def hsv_stats(a_bgr, b_bgr, mask=None) -> dict:
    """Δ in OpenCV HSV units. Hue is compared CIRCULARLY (mod 180)."""
    a = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2HSV).astype(np.int16)
    b = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2HSV).astype(np.int16)
    dh = np.abs(a[..., 0] - b[..., 0])
    # 179 and 0 are ADJACENT on the circle; a naive |diff| would report 179.
    dh = np.minimum(dh, 180 - dh)
    ds = np.abs(a[..., 1] - b[..., 1])
    dv = np.abs(a[..., 2] - b[..., 2])
    if mask is not None:
        dh, ds, dv = dh[mask], ds[mask], dv[mask]
    # Hue is meaningless at low saturation, so the hue mean is ALSO reported over
    # S > 40 only — that is the cut 12.1's matrix-vs-range signature is quoted at.
    sat = (a[..., 1] > 40) if mask is None else (a[..., 1][mask] > 40)
    # REVIEW 2026-09-15: an empty mask (a config with no zone at
    # s_center <= LOW_SAT_S_CENTER_MAX, or an all-off-frame rule set) made
    # `dh[mask]` zero-size, so `.mean()` returned NaN with a RuntimeWarning and
    # `.max()` raised "zero-size array to reduction". Report the emptiness.
    if dh.size == 0:
        return {
            "n_px": 0,
            "empty_mask": True,
            "note": "the mask selected no pixels — no statistic is defined",
        }

    def pct(arr, q):
        return float(np.percentile(arr, q))

    return {
        "n_px": int(dh.size),
        "dH_mean": float(dh.mean()), "dH_max": int(dh.max()),
        "dH_mean_S_gt_40": float(dh[sat].mean()) if sat.any() else 0.0,
        "dS_mean": float(ds.mean()), "dS_max": int(ds.max()),
        "dV_mean": float(dv.mean()), "dV_max": int(dv.max()),
        # AC3 asked for the low-saturation delta "as a DISTRIBUTION over the
        # low-saturation rule regions", not just a mean. Only means were
        # reported before the 2026-09-15 review, which is how a dS_max of 50
        # inside rule rects sat behind a dS_mean of 2.46.
        "dS_p50": pct(ds, 50), "dS_p95": pct(ds, 95), "dS_p99": pct(ds, 99),
        "dH_p50": pct(dh, 50), "dH_p95": pct(dh, 95), "dH_p99": pct(dh, 99),
        "dV_p95": pct(dv, 95),
        "identical": bool(dh.max() == 0 and ds.max() == 0 and dv.max() == 0),
    }


def rule_masks():
    """(all-rule mask, low-sat-rule mask) over the reference frame."""
    config = load_map_config(CONFIG)
    packed = pack_rules(config, (REF_H, REF_W, 3))
    allm = np.zeros((REF_H, REF_W), dtype=bool)
    lowm = np.zeros((REF_H, REF_W), dtype=bool)
    n_low = 0
    zones = list(config.hud_version_detection) + list(config.in_match_detection)
    for zl in config.map_zones.values():
        zones.extend(zl)
    for z in zones:
        r = z.rect.clamp_to((REF_H, REF_W, 3))
        if r.width <= 0 or r.height <= 0:
            continue
        sl = (slice(r.y, r.y + r.height), slice(r.x, r.x + r.width))
        allm[sl] = True
        if z.band.s_center <= LOW_SAT_S_CENTER_MAX:
            lowm[sl] = True
            n_low += 1
    return allm, lowm, n_low, packed.n_rules


def bgr_residual(a_bgr, b_bgr, mask=None) -> dict:
    """
    Per-channel BGR residual — the statistic that separates the two remaining
    hypotheses.

    A wrong MATRIX or a wrong RANGE is a per-pixel affine error: it scales with
    the pixel's own chroma and is unbounded. A chroma UPSAMPLING policy
    difference (our resolve shader samples chroma nearest-neighbour; FFmpeg's
    swscale interpolates) can only ever move a pixel between two neighbouring
    chroma samples, so it is bounded and concentrated at chroma edges.
    """
    a = a_bgr.astype(np.int16)
    b = b_bgr.astype(np.int16)
    d = np.abs(a - b)
    if mask is not None:
        d = d[mask]
    if d.size == 0:
        return {"n_px": 0, "empty_mask": True}
    return {
        "n_px": int(d.size // 3) if mask is None else int(d.shape[0]),
        "max_abs": int(d.max()),
        "mean_abs": float(d.mean()),
        "p99_abs": float(np.percentile(d, 99)),
        "frac_nonzero": float((d != 0).mean()),
    }


def diagnose(st: dict, bgr: dict) -> str:
    """
    12.1's measured signature, applied — plus the bound that distinguishes a
    chroma-upsampling difference from a colour-conversion error.

    🔴 REVIEW 2026-09-15: this function previously returned
    "MATRIX-ERROR-scale discrepancy (709 vs 601)" for BOTH paths on the shipped
    capture, while REPORT.md section 6 declared AC3's gate passed and attributed
    the same residual to chroma-upsampling policy. The tool and the report
    disagreed, in the same delivery, about the same numbers. It also asserted
    that "the 68 low-sat rules are IMMUNE to this one" — AC13 measured 44 of the
    69 low-saturation rules diverging between the two paths, so that claim was
    false as written. The bounded-residual test below is what actually separates
    the hypotheses, and it is computed rather than asserted.
    """
    if st["identical"]:
        return "IDENTICAL - bit-exact against FFmpeg."
    ds, dv, dh = st["dS_mean"], st["dV_mean"], st["dH_mean_S_gt_40"]
    bmax = bgr.get("max_abs")
    if ds > 10.0:
        return (f"RANGE ERROR signature (limited->full not applied): dS {ds:.2f} "
                f"vs 12.1's measured 19.68 for a pure range error. This is the "
                f"error the low-sat rules are MAXIMALLY exposed to.")
    if bmax is not None and bmax <= CHROMA_UPSAMPLING_MAX_BGR:
        return (f"CHROMA-UPSAMPLING POLICY difference: the BGR residual is bounded "
                f"at {bmax}/255 per channel (mean {bgr['mean_abs']:.4f}, "
                f"{bgr['frac_nonzero'] * 100:.2f}% of samples non-zero). A wrong "
                f"matrix or range is affine in the pixel's own chroma and is "
                f"UNBOUNDED, so a hard bound of <= {CHROMA_UPSAMPLING_MAX_BGR} "
                f"rules both out. Our resolve shader samples chroma "
                f"nearest-neighbour (ivec2(p.x / 2, p.y / 2)); swscale "
                f"interpolates. dS {ds:.2f} / dH {dh:.2f} follow from that, and "
                f"dS=0 against an interpolating reference was never reachable "
                f"without a matched-upsampling mode.")
    if ds > 0.5 or dh > 0.5:
        return (f"MATRIX-ERROR-scale discrepancy (709 vs 601): dS {ds:.2f} / dH "
                f"{dh:.2f} vs 12.1's measured 1.64 / 1.12, with an UNBOUNDED BGR "
                f"residual (max {bmax}/255). Low-saturation rules surrendered hue "
                f"so they are less exposed to the hue half - but NOT immune "
                f"overall: AC13 measured 44 of 69 diverging between the paths.")
    return (f"Sub-unit discrepancy (dS {ds:.3f} / dV {dv:.3f} / dH {dh:.3f}) - "
            f"consistent with rounding, not with a wrong matrix or range.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pc", help="FFmpeg rgb24 PNG of the keyframe")
    p.add_argument("device", nargs="+", help="device PNG(s), one per colour path")
    p.add_argument("--out", default=os.path.join(_HERE, "ac3_frame_diff.json"))
    a = p.parse_args(argv)

    pc = load_bgr(a.pc)
    allm, lowm, n_low, n_rules = rule_masks()
    print(f"rule regions: {n_rules} rules, {n_low} at s_center <= "
          f"{LOW_SAT_S_CENTER_MAX} ({int(allm.sum())} px / {int(lowm.sum())} px)\n")

    results = {}
    for dpath in a.device:
        name = os.path.basename(dpath)
        dev = load_bgr(dpath)
        entry = {
            "whole_frame": hsv_stats(pc, dev),
            "rule_regions": hsv_stats(pc, dev, allm),
            "low_sat_rule_regions": hsv_stats(pc, dev, lowm),
            "bgr_residual_whole_frame": bgr_residual(pc, dev),
            "bgr_residual_rule_regions": bgr_residual(pc, dev, allm),
        }
        entry["diagnosis"] = diagnose(
            entry["low_sat_rule_regions"], entry["bgr_residual_whole_frame"]
        )
        results[name] = entry
        print(f"=== {name} ===")
        for k in ("whole_frame", "rule_regions", "low_sat_rule_regions"):
            s = entry[k]
            # ASCII in stdout: a Windows console is cp1252 and would raise
            # UnicodeEncodeError on the delta glyph mid-report. The JSON keeps
            # the real names.
            print(f"  {k:22s} dH {s['dH_mean']:7.4f} (max {s['dH_max']:3d})  "
                  f"dS {s['dS_mean']:7.4f} (max {s['dS_max']:3d})  "
                  f"dV {s['dV_mean']:7.4f} (max {s['dV_max']:3d})")
        print(f"  -> {entry['diagnosis']}\n")

    json.dump(results, open(a.out, "w", encoding="utf-8"), indent=1)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
