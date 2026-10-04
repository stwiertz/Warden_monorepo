"""Which labeled PNGs come from the reference capture, and does the detection agree with them?

Matches each labeled PNG to the reference capture's keyframe at its timestamp by pixels
(downscaled grey, mean abs diff), then compares the human label with the oracle's
per-keyframe output — which the device reproduces exactly (0 / 142,174, story 12.4d).
"""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np, cv2

ROOT = Path(r"C:\Users\stwie\Documents\dev\Warden_monorepo")
VIDEO = ROOT / "videos/V2/2026-04-27 22-05-34.mp4"
LABELED = ROOT / "apps/tooling/output/labeled/v2"
ORACLE = json.loads((ROOT / "apps/mobile/bench/12-4c/video_oracle_fires.json").read_text())
W, H = 192, 108

frames = ORACLE["frames"]
pts_ms = np.array([f["timestamp_ms"] for f in frames])

# Decode every keyframe once, downscaled grey.
cmd = ["ffmpeg", "-v", "error", "-skip_frame", "nokey", "-i", str(VIDEO), "-vsync", "0",
       "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"]
raw = subprocess.run(cmd, capture_output=True, check=True).stdout
kf = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.int16)
assert len(kf) == len(frames), (len(kf), len(frames))

def match_of(i):
    for m in ORACLE["matches"]:
        if m["start_frame"] <= i <= m["end_frame"]:
            return m
    return None

rows = []
for png in sorted(LABELED.glob("*/*.png")):
    cls = png.parent.name
    mt = re.search(r"(\d\d)h(\d\d)m(\d\d)s", png.name)
    t = (int(mt[1]) * 3600 + int(mt[2]) * 60 + int(mt[3])) * 1000
    if t > pts_ms[-1] + 5000:
        continue
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    small = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA).astype(np.int16)
    # timestamps are truncated to whole seconds: try the keyframes within ±5 s
    cand = np.where(np.abs(pts_ms - t) <= 5000)[0]
    if len(cand) == 0:
        continue
    diffs = [(float(np.abs(kf[i] - small).mean()), int(i)) for i in cand]
    d, i = min(diffs)
    if d > 4.0:
        continue  # another capture
    f = frames[i]
    m = match_of(i)
    rows.append({"png": f"{cls}/{png.name}", "label": cls, "kf": i, "diff": round(d, 2),
                 "emitted": f["emitted"], "pred_map": f["pred_map"],
                 "match_map": m["map_id"] if m else None})

maps = {"artefact","atlantis","bastion","ceres","coliseum","engine","helios","horizon",
        "lunar_outpost","outlaw","polaris","silva","the_cliff","the_rock"}
summary = {}
def bump(k, ok):
    s = summary.setdefault(k, [0, 0]); s[0] += ok; s[1] += 1
errors = []
for r in rows:
    L = r["label"]
    if L in maps:
        in_match = r["match_map"] is not None
        bump("map frame lands inside a detected match", in_match)
        if in_match:
            ok = r["match_map"] == L
            bump("…and the match carries the right map", ok)
            if not ok: errors.append(r)
        else:
            errors.append(r)
    elif L in ("lobby", "transition"):
        ok = r["match_map"] is None or r["emitted"] != "in_match"
        bump(f"{L} frame NOT read as in-match", ok)
        if not ok: errors.append(r)
    elif L == "score":
        ok = r["emitted"] == "score_screen"
        bump("score frame read as score_screen", ok)
        if not ok: errors.append(r)

out = {"video": VIDEO.name, "labeled_pngs_from_this_capture": len(rows),
       "by_label": {k: sum(1 for r in rows if r["label"] == k) for k in sorted({r["label"] for r in rows})},
       "checks": {k: {"ok": v[0], "n": v[1], "rate": round(v[0] / v[1], 4)} for k, v in summary.items()},
       "matches": [{k: m[k] for k in ("start_ms", "end_ms", "map_id")} for m in ORACLE["matches"]],
       "match_label_votes": [], "errors": errors}
for m in ORACLE["matches"]:
    votes = {}
    for r in rows:
        if m["start_frame"] <= r["kf"] <= m["end_frame"]:
            votes[r["label"]] = votes.get(r["label"], 0) + 1
    out["match_label_votes"].append({"map_id": m["map_id"], "start_s": m["start_ms"] / 1000,
                                     "end_s": m["end_ms"] / 1000, "human_labels_inside": votes})
Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("labeled_pngs_from_this_capture", "by_label", "checks")}, indent=1))
for v in out["match_label_votes"]:
    print(f'{v["start_s"]:8.1f}-{v["end_s"]:8.1f}s  {v["map_id"]:<14} humans: {v["human_labels_inside"]}')
print("errors:", len(errors))
for e in errors[:25]:
    print(" ", e)
