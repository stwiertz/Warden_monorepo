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
    dup_after = len(order_after) - len(set(order_after))

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
        "identical": (
            n_before == n_after
            and not missing
            and not extra
            and not changed
            and dup_after == 0
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
