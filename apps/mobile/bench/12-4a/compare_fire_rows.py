#!/usr/bin/env python3
"""Story 12.4a AC5 — the decode-order tripwire.

`pc_reference.py compare` (the parity run AC5 names) runs the LABELED PNG CORPUS
through DIRECT_RGB. It never opens the video and never touches
`decodeKeyframesBySeek`, so it cannot see a decode-order defect. It is still worth
running — it proves the engine and the packed LUT are untouched — but it is not the
tripwire AC5 describes.

THIS is. `timing_fires_bit_parity_seek_1061.json` carries one row per decoded
keyframe: `{pts_us, fires}`, where `fires` is the 134-bit rule mask evaluated on
that keyframe's PIXELS, keyed by the PTS the decoder reported. Story 12.4a
pipelines the decode loop and matches outputs to requests by PTS; the specific way
that goes wrong is a frame delivered under the wrong PTS. That moves these rows and
moves nothing else.

A byte-identical result across the whole capture means the restructured loop
returned the same pixels for the same timestamps, 1061 times.

    python compare_fire_rows.py BEFORE.json AFTER.json [-o out.json]
"""

import argparse
import json
import sys


def load(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return d["n_rules"], d["frames"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    n_before, before = load(args.before)
    n_after, after = load(args.after)

    b_by_pts = {r["pts_us"]: r["fires"] for r in before}
    a_by_pts = {r["pts_us"]: r["fires"] for r in after}

    missing = sorted(set(b_by_pts) - set(a_by_pts))
    extra = sorted(set(a_by_pts) - set(b_by_pts))
    shared = sorted(set(b_by_pts) & set(a_by_pts))
    changed = [p for p in shared if b_by_pts[p] != a_by_pts[p]]

    # Order matters only as evidence: the rows are matched BY PTS, so a pure
    # reordering is not a defect. Report it so a reader can tell the two apart.
    order_before = [r["pts_us"] for r in before]
    order_after = [r["pts_us"] for r in after]

    # Duplicate PTS would mean the same frame was delivered twice — the other half
    # of the pipelining failure mode, and invisible to a dict comparison alone.
    # 🔴 REVIEW 2026-09-17 — BOTH SIDES. Only `after` was checked, so a BEFORE file
    # with a duplicated row silently collapsed in `b_by_pts` and then compared clean
    # against an AFTER that was genuinely missing that keyframe.
    dup_after = len(order_after) - len(set(order_after))
    dup_before = len(order_before) - len(set(order_before))

    # 🔴 REVIEW 2026-09-17 — THIS TRIPWIRE USED TO PASS VACUOUSLY.
    #
    # `identical` was `n_before == n_after and not missing and not extra and not
    # changed and dup_after == 0` — EVERY term of which is satisfied by two files
    # whose `frames` arrays are EMPTY. A truncated rescue file, or an AFTER capture
    # that aborted and emitted `{"n_rules": 134, "frames": []}`, printed
    # "OK — 0 keyframes x 134 rules = 0 rule-frame decisions, 0 disagreements"
    # and exited 0. For the one artifact AC5(b) rests on, a green result did not
    # establish that anything had been compared.
    #
    # These preconditions are deliberately hard failures, not warnings: an
    # instrument that cannot tell "proved identical" from "compared nothing" is
    # worse than no instrument, because it looks like evidence.
    problems = []
    if not before:
        problems.append(f"BEFORE file {args.before!r} contains zero frame rows")
    if not after:
        problems.append(f"AFTER file {args.after!r} contains zero frame rows")
    if n_before <= 0 or n_after <= 0:
        problems.append(f"n_rules must be positive (before={n_before}, after={n_after})")
    if dup_before:
        problems.append(f"BEFORE file contains {dup_before} duplicate pts_us rows")
    if len(b_by_pts) != len(before):
        problems.append(
            f"BEFORE collapsed on load: {len(before)} rows -> {len(b_by_pts)} unique PTS"
        )
    if len(a_by_pts) != len(after):
        problems.append(
            f"AFTER collapsed on load: {len(after)} rows -> {len(a_by_pts)} unique PTS"
        )
    if problems:
        print(
            "FAIL — the comparison was not performed. This is not a pass:\n  "
            + "\n  ".join(problems),
            file=sys.stderr,
        )
        return 2

    result = {
        "story": "12.4a",
        "what_this_proves": (
            "Per-keyframe rule-fire masks are derived from DECODED PIXELS and keyed by "
            "the PTS the decoder reported. Identical rows across the full capture mean "
            "the pipelined decode loop returned the same pixels for the same timestamps."
        ),
        "before_file": args.before,
        "after_file": args.after,
        "n_rules_before": n_before,
        "n_rules_after": n_after,
        "rows_before": len(before),
        "rows_after": len(after),
        "duplicate_pts_in_before": dup_before,
        "duplicate_pts_in_after": dup_after,
        "pts_missing_from_after": missing[:20],
        "n_pts_missing_from_after": len(missing),
        "pts_extra_in_after": extra[:20],
        "n_pts_extra_in_after": len(extra),
        "n_shared_pts": len(shared),
        "n_rows_with_changed_fires": len(changed),
        "first_changed_pts": changed[:20],
        "delivery_order_identical": order_before == order_after,
        "rule_frame_decisions_compared": len(shared) * n_before,
        # Guards against a mask width that disagrees with the declared n_rules —
        # `rule_frame_decisions_compared` multiplies by the DECLARED count, so a
        # short mask would inflate it silently.
        "mask_hex_chars": sorted({len(v) for v in b_by_pts.values()} | {len(v) for v in a_by_pts.values()}),
        "identical": (
            n_before == n_after
            and bool(shared)
            and len(shared) == len(before) == len(after)
            and not missing
            and not extra
            and not changed
            and dup_after == 0
            and dup_before == 0
        ),
    }

    print(json.dumps(result, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)

    if not result["identical"]:
        print(
            "\nFAIL — the decode change moved pixels or mismatched timestamps. "
            "STOP: this is AC5's tripwire, not a tolerance.",
            file=sys.stderr,
        )
        return 1
    print(
        f"\nOK — {len(shared)} keyframes x {n_before} rules = "
        f"{len(shared) * n_before} rule-frame decisions, 0 disagreements."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
