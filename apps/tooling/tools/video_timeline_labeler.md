# Tool 6 — Video Timeline Labeler

Scrub a raw EVA capture, hit a hotkey, and the tool snaps to the nearest keyframe and writes a labeled PNG into `output/labeled/v<ver>/<class>/`. Feeds Tool 7 (Story 9.6) for HUD-2.0 ROI mining.

## Launch

From `apps/tooling/`:

```powershell
# Via the TUI (recommended — picks up `Tool 6 — Label Frames from Video Timeline`)
uv run python wardentooling.py

# Or direct CLI
uv run python tools/video_timeline_labeler.py <video.mp4> [-o OUTPUT_DIR] [--snap nearest|prior|after]
```

Defaults: `OUTPUT_DIR = <repo>/output/labeled`, `--snap = nearest`.

On launch:
1. ffprobe scans the full keyframe list via packet-level inspection (printed: `Found N keyframes spanning Ts`; ~2 s on a 73-min capture).
2. A modal opens with the video's first frame as a thumbnail and three buttons: **HUD 1.0**, **HUD 2.0**, **Custom…** (custom strings must match `[A-Za-z0-9._-]+`, e.g. `1.5`, `2.0-beta`, `hud_v3`). Non-skippable; locks the session.
3. Player window opens with a dual-row label-button bar above the canvas: special classes (Lobby / Transition / Score / Undo) on row 1, the 14 maps on row 2. Each button shows its keyboard shortcut in parens, e.g. `Lobby (L)`, `Horizon (8)`. Click or press the key — same effect.

## Keys

| Key                 | Action                                       |
|---------------------|----------------------------------------------|
| `Space`             | Play / pause                                 |
| `Left` / `Right`    | Step ±1 frame                                |
| `Shift+Left/Right`  | Step ±10 frames                              |
| `J` / `K`           | Step ±1 second                               |
| `1`–`9`, `0`, `q`, `w`, `e`, `r` | Label as map (positional, matches Tool 2) |
| `L`                 | Label `lobby`                                |
| `T`                 | Label `transition` (negative class)          |
| `S`                 | Label `score` (round-end screen)             |
| `Backspace`         | Undo last label (single step). Cursor stays put. |

**After every label** (button click or hotkey), the cursor auto-advances **+60 seconds** then snaps to the nearest keyframe — minute-sample workflow.

**Auto-backfill:** if your most recent label and the one before it are the **same class** (and that class is **not** `transition`), the tool fills in every keyframe between the two with that same class. Two consecutive `Horizon` labels at minutes 5 and 6 → ~15 backfilled keyframes labeled `horizon`. Big time-saver when a single map plays for several minutes.

**Backspace undoes the entire last batch** — one label or one backfill batch, whichever was the most recent action.

Map-key positions: `1=artefact`, `2=atlantis`, `3=bastion`, `4=ceres`, `5=coliseum`, `6=engine`, `7=helios`, `8=horizon`, `9=lunar_outpost`, `0=outlaw`, `q=polaris`, `w=silva`, `e=the_cliff`, `r=the_rock`. (Source of truth: `tools/frame_labeler.py:23`.)

## Output

```
output/labeled/v2.0/lobby/001_00h05m12s.png
output/labeled/v2.0/horizon/001_00h12m34s.png
output/labeled/v2.0/transition/001_00h08m43s.png
...
```

`seq` is per `(version, class)` directory, zero-padded to 3 digits. Timestamp is the *snapped* keyframe PTS, formatted `HHhMMmSSs`. After undo, the freed seq number is reused on the next label to that class.

## Snap policies

- `nearest` (default): closest keyframe in absolute time; ties go to the prior PTS.
- `prior`: largest keyframe ≤ cursor. Refuses (system bell, no PNG) if cursor is before the first keyframe.
- `after`: smallest keyframe ≥ cursor. Refuses if cursor is after the last keyframe.

The decoded PNG comes from `extract_frame_at_timestamp` (ffmpeg subprocess, full-resolution), not from `cv2.VideoCapture` — `VideoCapture` only drives the player display.

## Smoke test (5 min)

Stage one EVA MP4, then verify:

1. HUD modal blocks the player until you click 1.0 or 2.0.
2. Slider scrubs; `Space`, `J/K`, `Left/Right`, `Shift+arrows` step correctly.
3. Press `1` (or any map key) → check `output/labeled/v2.0/<map>/001_<HHmMSs>.png` exists; status bar shows `snapped <cursor> → <pts>`.
4. Press `L`, `T`, `S` → equivalent files in `lobby/`, `transition/`, `score/`.
5. `Backspace` removes the most recent PNG; press again → bell, no FS change.
6. Relaunch with `--snap prior` then `--snap after` on a deliberately-between-keyframes cursor → snapped PTS differs.

## Tests (no GUI)

```powershell
uv run pytest tests/test_video_timeline_labeler.py -v
```

Covers `_snap_to_keyframe`, `_output_path`, `_format_hhmmss`, `_next_seq`, `_undo` (21 cases). The Tk app class is intentionally untested in pytest — exercised via the smoke test above.
