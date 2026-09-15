"""Story 12.2 — PC-side GPU reference + device parity comparator (AC8/AC14).

Two jobs, neither of which Tool 12 does today:

1. ``dump`` — run Tool 12's GPU path over the labeled corpus and emit the
   **per-rule fire bits** for every frame. Story 12.1 pinned accuracy and
   per-frame classifications but NOT per-rule bits, so AC8/AC14's "compare
   per-rule fire bits against 12.1's pinned GPU output" had no artifact to
   compare against. This produces it, from the unmodified Tool 12 modules.

2. ``compare`` — diff the device's ``parity_fires.json`` against that reference
   and report EXACT disagreements (which rule, which frame, which branch), not
   just an accuracy number. Two engines can post identical accuracy while
   disagreeing on which frames they get right; per-rule bits close that gap.

Tool 12 is NOT modified (it is `done`, and this is 12.2's analysis surface). E7's
tooling conventions do not bind here — 12.2 is on the mobile surface — but this
script must run in the tooling venv because it imports Tool 12:

    cd apps/tooling
    uv run python ../mobile/bench/12-2/pc_reference.py dump
    uv run python ../mobile/bench/12-2/pc_reference.py compare <device_parity_fires.json>
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

from tools.keyframe_engine_bench.lut import decode_results, pack_rules  # noqa: E402
from tools.keyframe_engine_bench.shader import MegaShader  # noqa: E402
from tools.roi_detection_tester import load_map_config  # noqa: E402

REF_W, REF_H = 1920, 1080
CONFIG = os.path.join(_TOOLING, "output", "map_configs", "map_config.v2.json")
CORPUS = os.path.join(_TOOLING, "output", "labeled", "v2")
DEFAULT_OUT = os.path.join(_HERE, "pc_reference_fires.json")


def bits_to_hex(bits) -> str:
    """4 bits per hex char, LSB first — the SAME packing WardenEngineBench uses."""
    out = []
    for i in range(0, len(bits), 4):
        nib = 0
        for j in range(4):
            if i + j < len(bits) and bits[i + j]:
                nib |= 1 << j
        out.append("0123456789abcdef"[nib])
    return "".join(out)


def hex_to_bits(s: str, n: int) -> list[bool]:
    bits = []
    for ch in s:
        nib = int(ch, 16)
        for j in range(4):
            bits.append(bool(nib & (1 << j)))
    return bits[:n]


def dump(out_path: str) -> int:
    config = load_map_config(CONFIG)
    packed = pack_rules(config, (REF_H, REF_W, 3))
    print(f"packed {packed.n_rules} rules")

    frames = {}
    skipped = []
    gl_info: dict = {}
    with MegaShader(packed.texture, (REF_W, REF_H)) as shader:
        print("GL:", shader.info)
        # 🔴 REVIEW 2026-09-15: this payload used to hard-code `"gl": {}`, so the
        # GPU that produced the reference was recorded NOWHERE — which is why the
        # claim that it was regenerated on an RTX 4060 (and therefore constitutes
        # free cross-vendor evidence against 12.1's Intel UHD 770) has no artifact
        # behind it. Record whatever the driver reports, whatever shape it is in.
        gl_info = (
            dict(shader.info) if isinstance(shader.info, dict) else {"info": str(shader.info)}
        )
        classes = sorted(
            d for d in os.listdir(CORPUS) if os.path.isdir(os.path.join(CORPUS, d))
        )
        for cls in classes:
            d = os.path.join(CORPUS, cls)
            for name in sorted(os.listdir(d)):
                if not name.endswith(".png"):
                    continue
                # cv2.imread gives OpenCV-native BGR, which is exactly what the
                # shader's uFrame expects (.r == blue).
                img = cv2.imread(os.path.join(d, name), cv2.IMREAD_COLOR)
                if img is None or img.shape[:2] != (REF_H, REF_W):
                    # Skips are RECORDED, not just `continue`d: a silent skip here
                    # is half of how a parity comparison can end up covering a
                    # subset while reporting "EXACT PARITY".
                    skipped.append(f"{cls}/{name}")
                    continue
                shader.upload(img)
                bits = decode_results(shader.draw_and_read(), packed.n_rules)
                frames[f"{cls}/{name}"] = bits_to_hex(bits)
            print(f"  {cls}: {len(frames)} cumulative")

    if skipped:
        print(f"\n⚠ skipped {len(skipped)} image(s) (unreadable or not "
              f"{REF_W}x{REF_H}), e.g. {skipped[:5]}")

    payload = {
        "n_rules": packed.n_rules,
        "gl": gl_info,
        "skipped": skipped,
        "rule_ids": [[r.owning_class, r.zone_id, r.kind] for r in packed.refs],
        "frames": frames,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    print(f"wrote {out_path} ({len(frames)} frames)")
    return 0


def compare(device_path: str, ref_path: str) -> int:
    ref = json.load(open(ref_path, encoding="utf-8"))
    dev = json.load(open(device_path, encoding="utf-8"))
    n = ref["n_rules"]
    rule_ids = ref["rule_ids"]

    dev_frames = {row["frame"]: row["fires"] for row in dev["frames"]}
    common = sorted(set(ref["frames"]) & set(dev_frames))
    print(f"reference frames: {len(ref['frames'])}")
    print(f"device frames:    {len(dev_frames)}")
    print(f"compared:         {len(common)}")

    # 🔴 REVIEW 2026-09-15 — PARITY OVER AN INTERSECTION IS NOT PARITY.
    #
    # There was no assertion that `common` covered either side. The device drops
    # frames silently in two places (`evaluateBitmap` returns None on a decode
    # failure or a geometry mismatch and the loop continues; `dump()` skips any
    # image whose shape is not REF_H x REF_W), so a fixture push that landed 30
    # of 2666 PNGs produced `frames_compared: 30`, printed "EXACT PARITY", and
    # wrote `total_rule_disagreements: 0` — which is the file the headline
    # "0 disagreements across 357,244 rule-frame decisions" is sourced from.
    # The 2666/357,244 happens to be right; nothing here would have said so if it
    # were not. Refuse to report parity over a subset.
    missing_on_device = sorted(set(ref["frames"]) - set(dev_frames))
    extra_on_device = sorted(set(dev_frames) - set(ref["frames"]))
    if missing_on_device or extra_on_device:
        print("\n🔴 FRAME SETS DO NOT MATCH — refusing to report parity.")
        if missing_on_device:
            print(f"  {len(missing_on_device)} reference frame(s) absent from the device "
                  f"dump, e.g. {missing_on_device[:5]}")
        if extra_on_device:
            print(f"  {len(extra_on_device)} device frame(s) absent from the reference, "
                  f"e.g. {extra_on_device[:5]}")
        print("  A parity figure computed over the intersection would be a claim "
              "about whichever frames happened to survive on both sides.")
        return 2

    per_rule = [0] * n
    disagreeing_frames = 0
    examples = []
    for f in common:
        a = hex_to_bits(ref["frames"][f], n)
        b = hex_to_bits(dev_frames[f], n)
        diff = [i for i in range(n) if a[i] != b[i]]
        if diff:
            disagreeing_frames += 1
            for i in diff:
                per_rule[i] += 1
            if len(examples) < 20:
                examples.append(
                    {"frame": f, "rules": [
                        {"texel": i, "id": rule_ids[i], "pc": a[i], "device": b[i]}
                        for i in diff[:8]
                    ]}
                )

    total = sum(per_rule)
    print(f"\nframes with >=1 disagreement: {disagreeing_frames} / {len(common)}")
    print(f"total per-rule disagreements: {total} "
          f"(of {len(common) * n} rule-frame decisions)")
    if total:
        print("\nper-rule breakdown (non-zero only):")
        for i, c in enumerate(per_rule):
            if c:
                print(f"  texel {i:3d}  {rule_ids[i][0]}/{rule_ids[i][1]}"
                      f" ({rule_ids[i][2]}): {c} frames")
        print("\nexamples:")
        print(json.dumps(examples[:5], indent=1))
    else:
        print("\nEXACT PARITY — 0 per-rule disagreements.")

    # AC14 — the three per-classifier accuracies, RECOMPUTED here rather than
    # quoted from prose. Best-effort: it needs `apps/tooling` importable, which
    # a bare `python pc_reference.py compare` on a machine without the tooling
    # venv does not have. A failure is reported, never silently swallowed —
    # publishing the table with no producing code path is exactly what the
    # 2026-09-15 review found.
    accuracy: dict = {}
    for side, fires in (("pc_reference", ref["frames"]), ("device", dev_frames)):
        try:
            accuracy[side] = accuracy_from_fires(fires, n)
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            accuracy[side] = {"error": f"{type(exc).__name__}: {exc}"}
    print("\nclassifier accuracy:")
    print(json.dumps(accuracy, indent=1))

    out = os.path.join(_HERE, "parity_comparison.json")
    json.dump(
        {
            "frames_compared": len(common),
            "reference_frames": len(ref["frames"]),
            "device_frames": len(dev_frames),
            "frame_sets_identical": True,
            "frames_with_disagreement": disagreeing_frames,
            "total_rule_disagreements": total,
            "rule_frame_decisions": len(common) * n,
            "per_rule_disagreements": {
                f"{rule_ids[i][0]}/{rule_ids[i][1]}": per_rule[i]
                for i in range(n) if per_rule[i]
            },
            "examples": examples,
            "ac14_classifier_accuracy": accuracy,
        },
        open(out, "w", encoding="utf-8"), indent=1,
    )
    print(f"\nwrote {out}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump", help="run Tool 12's GPU path, emit per-rule fire bits")
    d.add_argument("--out", default=DEFAULT_OUT)
    c = sub.add_parser("compare", help="diff device fire bits against the reference")
    c.add_argument("device", help="parity_fires.json pulled from the device")
    c.add_argument("--ref", default=DEFAULT_OUT)
    a = p.parse_args(argv)
    return dump(a.out) if a.cmd == "dump" else compare(a.device, a.ref)


# 🔴 REVIEW 2026-09-15 — THIS BLOCK USED TO SIT **BELOW** THE `__main__`
# GUARD, i.e. after `raise SystemExit(main())`, so it was DEAD CODE that no
# CLI path could ever reach. `main()` dispatched only `dump`/`compare`,
# `compare()` emitted fire-bit counts and no accuracy fields, and
# `parity_comparison.json` confirms that shape — yet REPORT.md section 7 and the
# story both publish a three-row accuracy table (hud 2614/2666 = 0.980495 /
# in_match 2666/2666 / map_id 2286/2286) presented as reproduced on Adreno.
# Nothing in the repo recomputed those numbers. It is now defined before the
# guard and wired into `compare()`, which writes the table it claims.
# ---------------------------------------------------------------------------
# AC14 — the THREE per-classifier formulas, applied to a fire-bit set.
#
# Reusing Tool 12's `score_from_fires` verbatim rather than re-deriving: AC14
# warns that `SCP:285`'s "Tool 9 sums raw weighted" is true of the MAP-ID
# classifier ONLY (HUD is `fires/n_hud` normalized; in_match is `fires/n_im`
# normalized THEN hard-binary), and implementing the raw form everywhere
# silently breaks two of the three numbers.
# ---------------------------------------------------------------------------
def accuracy_from_fires(fires_by_frame: dict, n_rules: int) -> dict:
    """``{"cls/name.png": hexbits}`` -> the three classifier accuracies."""
    from tools.common.labels import MAP_LABELS
    from tools.keyframe_engine_bench.scoring import score_from_fires
    from tools.roi_detection_tester import _folder_to_in_match, _normalize_hud

    config = load_map_config(CONFIG)
    packed = pack_rules(config, (REF_H, REF_W, 3))

    hud_pairs, im_pairs, map_pairs = [], [], []
    for key, hexbits in fires_by_frame.items():
        folder = key.split("/", 1)[0]
        bits = hex_to_bits(hexbits, n_rules)
        # The corpus is flat `<class>/<file>.png` under a single v2 HUD root, so
        # hud_dir is the config's own version for every frame — matching how
        # iter_labeled_frames resolves it for this corpus.
        sc = score_from_fires(
            bits, packed, config, folder=folder, hud_dir=config.hud_version
        )
        hud_pairs.append((_normalize_hud(config.hud_version), sc.pred_hud))
        if sc.pred_in_match is not None:
            im_pairs.append((_folder_to_in_match(folder), sc.pred_in_match))
        if folder in MAP_LABELS and sc.pred_map is not None:
            map_pairs.append((folder, sc.pred_map))

    def acc(pairs):
        n = len(pairs)
        c = sum(1 for gt, pr in pairs if gt == pr)
        return {"accuracy": (c / float(n) if n else 0.0), "n": n, "correct": c}

    return {
        "hud_version_classifier": acc(hud_pairs),
        "in_match_classifier": acc(im_pairs),
        "map_id_classifier": acc(map_pairs),
    }

if __name__ == "__main__":
    raise SystemExit(main())
