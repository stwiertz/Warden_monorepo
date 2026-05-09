# Story 9.5: Video Timeline Labeler (Tool 6)

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane** (sole tooling user; preparing the new-HUD re-fingerprinting cycle),
I want **a desktop video-timeline labeler that lets me scrub a raw EVA capture, hit a hotkey at any moment, and have the tool snap to the nearest keyframe and write a labeled PNG into a HUD-version-aware directory tree (`labeled/v<ver>/<class>/<seq>_<ts>.png`)**,
so that **I can rapidly produce the labeled dataset that Tool 7 (Story 9.6) will consume to mine fresh ROI/HSV signatures for the redesigned EVA HUD ("HUD 2.0"), unblocking the rework of `gameDetector` + `mapIdentifier` whose legacy ROIs no longer fire on new-HUD content.**

**Strategic context:** This work backfills the "new-HUD work" prerequisite that `_bmad-output/sprint-status.yaml` line 2 originally bound to the (now-cancelled) Story 1.1.1. EVA shipped a HUD redesign; the existing KDA/map-bar ROIs in `apps/tooling/config/config.yaml` target the legacy HUD ("HUD 1.0") and no longer match — `gameDetector` returns false-negatives, `mapIdentifier` returns null on new-HUD frames. Re-fingerprinting requires a labeled dataset partitioned by HUD version. Tool 1 + Tool 2 cannot produce HUD-version-aware labels and don't expose a video-timeline scrub workflow — hence Tool 6 as a separate, complementary tool. Tool 2 (`frame_labeler.py`) is **not** replaced; it retains its `tooling-LABEL-001/002` post-Tool-1 PNG-labeling role.

**Type:** Standard tooling feature story. Track C (tooling chain). No spike-or-split flag. Single-PR delivery.

## Acceptance Criteria (checklist)

> **AC checkbox convention:** Items whose endpoint depends on **post-merge actions** (sprint-status `review → done` flip, PR merge) are held `[ ]` with carve-out notes per the AC-checkbox-tighten convention (see `feedback_ac_checkbox_tighten.md` precedent). All other items flip to `[x]` on dev-agent completion.

1. [x] **AC1 — New tool file at `apps/tooling/tools/video_timeline_labeler.py`.** Runs as a standalone CLI: `python tools/video_timeline_labeler.py <video.mp4> [-o OUTPUT_DIR] [--snap nearest|prior|after]`. Default `OUTPUT_DIR` = `<project_root>/output/labeled` (matching the existing `frame_labeler.py` default-output convention). Default snap policy = `nearest`.

2. [x] **AC2 — HUD version prompt on session open.** A modal/dialog at startup forces selection between `1.0` and `2.0` before the player UI is interactive. The chosen version is stored as session metadata and **all** PNGs written this session are routed to `<output>/v<hud_version>/<class>/`. The version cannot be changed mid-session (re-launch to switch). The selection is logged to stdout: `HUD version: 2.0 — output root: <output>/v2.0/`.

3. [x] **AC3 — ffprobe keyframe-list extraction at video open.** On open, the tool calls `utils.video.get_keyframe_timestamps(video_path, scan_duration=int(get_video_duration(video_path)) + 1)` to pull the FULL keyframe PTS list (not just the first 30 s — the existing default). Result is cached in memory. The status bar shows `keyframes: <count>` once the scan completes.

4. [x] **AC4 — Snap policy honored.** Three CLI policies: `nearest` (closest in absolute time), `prior` (closest keyframe at or before cursor), `after` (closest keyframe at or after cursor). On any label hotkey, the cursor's float-second position is snapped per policy and the snapped PTS is what gets decoded + written. The status bar briefly displays `snapped <cursor> → <pts>` after each label. If the cursor is outside the keyframe range for the policy (e.g. `prior` and cursor is before the first keyframe), the tool plays a system bell and refuses the label (no PNG written, no counter increment).

5. [x] **AC5 — Tk player UI.** Tkinter root window with:
   - **Canvas** rendering the current frame (decoded via OpenCV `VideoCapture` for scrub/play, RGB-converted for PIL display, scaled to fit canvas — `frame_labeler.py:_render_image` is the reference pattern).
   - **Scrubber slider** spanning the full video duration; dragging seeks; the cursor float-seconds value is the canonical position.
   - **Play/pause** via `Space`. Frame stepping: `Left` / `Right` = -1 / +1 frame (decoded sequentially via `VideoCapture.set(CAP_PROP_POS_FRAMES, ...)`); `Shift+Left` / `Shift+Right` = -10 / +10 frames; `J` / `K` = -1 / +1 second.
   - **Status bar** shows: `<MM:SS.mmm> | frame <idx>/<total> | last: <class>/<filename> | session: lobby=<n>, <map1>=<n>, …` (only nonzero counts shown to avoid clutter).

6. [x] **AC6 — Hotkey label set (18 hotkeys).** Bindings:
   - `L` → `lobby`
   - `T` → `transition` (negative class / discard bucket)
   - `S` → `score` (round-end score screen)
   - `1`–`9`, `0`, `q`, `w`, `e`, `r` → 14 maps from `MAP_LABELS` at `apps/tooling/tools/frame_labeler.py:23-38` (mapping is positional, identical to Tool 2 to avoid muscle-memory conflict).
   On press: snap → decode keyframe via `utils.video.extract_frame_at_timestamp(video_path, snapped_pts, src_w, src_h)` → write PNG via `cv2.imwrite(<dest>, frame)` (BGR, matching the format `extract_frame_at_timestamp` returns and the convention `game_detector.py` uses). Output path: `<output>/v<hud_version>/<class>/<seq:03d>_<HHmMSs>.png` where `seq` is per-`(version, class)` directory (count existing `*.png` files at write-time + 1; same pattern as `frame_labeler.next_game_counter`). Timestamp suffix uses the existing `utils.format.format_timestamp` helper if compatible, or inline format `f"{int(pts//3600):02d}h{int((pts%3600)//60):02d}m{int(pts%60):02d}s"`.

7. [x] **AC7 — Backspace undo.** Pressing `Backspace` removes the most recently written PNG (via `os.remove`), decrements its per-`(version, class)` counter (the next label to that class will reuse the freed sequence number), and updates the status bar. Undo history depth = 1 (single-step, matching Tool 2's `_undo` behavior at `frame_labeler.py:365`). After undo, the undo action is consumed; pressing Backspace again with no further label written is a no-op + system bell.

8. [x] **AC8 — TUI registration.** `apps/tooling/wardentooling.py`:
   - Adds `flow_tool6() -> tuple[list[str], str | None]` mirroring the `flow_tool1`/`flow_tool5` shape (video file picker via `browse_video_file`, optional `-o` prompt, optional `--snap` choice prompt).
   - Inserts `"Tool 6 — Label Frames from Video Timeline"` into `choices_main` at [wardentooling.py:522-530](apps/tooling/wardentooling.py#L522-L530) between current `"Tool 5 — Analyze Rounds"` and `"Dev Tools"`.
   - Adds branch handler in `menu_main`'s while-loop matching the `flow_tool5` pattern: collect args → confirm → `run_tool` → `save_last_run("video_timeline_labeler", "Tool 6 — …", args, video_path)` on `returncode == 0`.
   - Adds `"video_timeline_labeler": ("Tool 6 — Label Frames from Video Timeline", flow_tool6)` to `_TOOL_MAP` at [wardentooling.py:436-442](apps/tooling/wardentooling.py#L436-L442).
   - Adds a `_reprompt_source` branch for `tool_key == "video_timeline_labeler"` that re-prompts only the video path (same shape as the `game_detector` branch at [wardentooling.py:453-457](apps/tooling/wardentooling.py#L453-L457)).

9. [x] **AC9 — Pytest at `apps/tooling/tests/test_video_timeline_labeler.py`.** Covers (no GUI; pure-function unit tests):
   - `_snap_to_keyframe(cursor, pts_list, policy)` — given `pts_list = [0.0, 2.0, 4.0, 6.0]` and `cursor = 2.7`: `nearest` → `2.0`; `prior` → `2.0`; `after` → `4.0`. Edge: `cursor = 5.0` → `nearest` ties resolved by picking the prior PTS. Edge: `cursor = -1` with `prior` → returns `None` (out of range; tool refuses the label).
   - `_output_path(output_root, version, class_, seq, pts)` — returns `<root>/v<ver>/<class>/<seq:03d>_<ts>.png` exactly.
   - `_next_seq(dest_dir)` — given a directory with files `001_00m12s.png`, `002_00m34s.png` returns `3`. Empty dir returns `1`. Resilient to non-conforming filenames (skipped).
   - `_undo` — given a written file path, removes it; subsequent `_next_seq` returns the freed number. Calling `_undo` twice without an intervening write returns False (and produces no FS change).
   The pure helpers (`_snap_to_keyframe`, `_output_path`, `_next_seq`, `_undo`) are top-level module functions (NOT methods on the Tk app class) so they're testable without instantiating `Tk()`. The Tk app class composes these helpers.

10. [ ] **AC10 — Sprint-status flip.** `_bmad-output/sprint-status.yaml` `development_status[9-5-video-timeline-labeler-tool-6]` flips `backlog → ready-for-dev → in-progress → review → done` across the work; `epic-9` flips `backlog → in-progress` when this story file is created (verify: this happened at create-story time before the dev agent reads this file). _Held `[ ]` for the `review → done` portion — that flip is **post-merge admin** per the AC-checkbox-tighten convention; ships in a tiny follow-up commit/PR after the main PR merges (Two-PR pattern, `feedback_two_pr_docs_execution.md`)._

11. [ ] **AC11 — Single-PR delivery.** All file modifications ship in **one PR** titled `feat: Tool 6 — video timeline labeler (Story 9.5)`. Branch name: `tool-6-video-timeline-labeler`. PR body links: this story file; Epic 9 charter at `_bmad-output/epics-and-stories.md:2614`; the `architecture-tooling.md` pipeline table. The follow-up `review → done` flip is a separate tiny commit/PR per AC10 carve-out.

## Tasks / Subtasks

> **Implementation order:** wire imports + ffmpeg helpers first, then Tk skeleton, then hotkey behavior, then tests, then TUI registration. Run the tool manually on at least one local MP4 before the test pass — the cursor-snap math is the single highest-value behavior to eyeball.

- [x] **Task 1: Module skeleton + imports + CLI parsing (AC: 1, 4)**
  - [x] Create `apps/tooling/tools/video_timeline_labeler.py` with the module docstring (mirror the `frame_labeler.py:1-10` style — short one-liner + 2-3 sentence elaboration + `Usage:` block).
  - [x] `sys.path.insert(0, ...)` to lift `utils/` onto the import path (same pattern as `game_detector.py:21-22`).
  - [x] Imports: `argparse`, `os`, `glob`, `re`, `sys`, `tkinter as tk`, `from tkinter import filedialog`, `cv2`, `from PIL import Image, ImageTk`, `from utils.video import check_ffmpeg, get_video_info, get_video_duration, get_keyframe_timestamps, extract_frame_at_timestamp`. _`utils.format.format_timestamp` is incompatible (returns `MMmSSs`, no hour component) — inlined `_format_hhmmss(pts)` helper instead per AC6 carve-out._
  - [x] Reuse `MAP_LABELS` and `LABEL_DISPLAY` constants by importing from `frame_labeler.py` (`from tools.frame_labeler import MAP_LABELS, LABEL_DISPLAY`) — single source of truth per `tooling-LABEL-002`.
  - [x] `argparse` flags: positional `video` (optional — fallback to `filedialog.askopenfilename` if omitted), `-o/--output` (default `<project_root>/output/labeled`), `--snap` choice of `nearest|prior|after` (default `nearest`).

- [x] **Task 2: Pure helpers — snap, path, seq, undo (AC: 4, 6, 7, 9)**
  - [x] Implement `_snap_to_keyframe(cursor: float, pts_list: list[float], policy: str) -> float | None`. For `nearest`: return PTS minimizing `abs(pts - cursor)`; tie-break = pick the prior. For `prior`: return max PTS where `pts <= cursor`, or `None` if cursor < pts_list[0]. For `after`: return min PTS where `pts >= cursor`, or `None` if cursor > pts_list[-1]. Empty `pts_list` → `None`.
  - [x] Implement `_output_path(output_root: str, version: str, class_: str, seq: int, pts: float) -> str`. Builds `<root>/v<version>/<class>/<seq:03d>_<HHmMSs>.png`. The `HHmMSs` formatter zero-pads (`01h05m23s`); for sub-1-hour videos prefix is `00h`.
  - [x] Implement `_next_seq(dest_dir: str) -> int`. Globs `<dest_dir>/*.png`, parses leading `001_…` integer per filename via regex `r'^(\d+)_'`, returns `max(...) + 1` or `1` if none. Skips non-conforming names silently.
  - [x] Implement `_undo(last_written_path: str | None) -> bool`. If path is None or doesn't exist, return False. Else `os.remove(path)`, return True.

- [x] **Task 3: Tk app class — UI build + frame rendering (AC: 5)**
  - [x] `class VideoTimelineLabelerApp(tk.Tk)` constructor takes `(video_path, output_dir, hud_version, snap_policy, keyframe_pts)`. Sets `self.title("Warden Video Timeline Labeler")`, `self.geometry("1400x900")`, `self.minsize(900, 600)`.
  - [x] Open video with `cv2.VideoCapture(video_path)`. Pull `frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))`, `fps = cap.get(cv2.CAP_PROP_FPS)`. Store `self.cap`, `self.fps`, `self.frame_count`, `self.duration_s`.
  - [x] `_build_ui()`: top frame with HUD-version label (read-only) + snap-policy label. Center: `tk.Canvas` for frame display (mirror [frame_labeler.py:236-243](apps/tooling/tools/frame_labeler.py#L236-L243)). Bottom: `tk.Scale(orient=tk.HORIZONTAL, from_=0, to=self.duration_s, resolution=0.001, command=self._on_slider)` + status `tk.Label`.
  - [x] `_render_current_frame()`: read frame, `cv2.cvtColor(BGR2RGB)`, `Image.fromarray`, scale-to-canvas (same math as `frame_labeler.py:279-295`), display via `ImageTk.PhotoImage`. Hold the `PhotoImage` reference on `self._tk_image` to prevent GC.
  - [x] `_on_slider(value_str)`: convert to seconds float, set `self._cursor_s = value`, debounce 50 ms via `self.after`, then seek + render.

- [x] **Task 4: Playback + frame-step + second-step keys (AC: 5)**
  - [x] `Space` → toggle `self._playing`; while playing, `self.after(int(1000/self.fps), self._tick)` advances one frame and re-renders until paused or EOF.
  - [x] `Left` / `Right` bound to `_step_frames(-1)` / `_step_frames(+1)`; `Shift-Left` / `Shift-Right` → ±10. `_step_frames(delta)` updates the slider value (which fires `_on_slider`).
  - [x] `J` / `K` bound to `_step_seconds(-1)` / `_step_seconds(+1)`.

- [x] **Task 5: Hotkey labels — snap → decode → write (AC: 4, 6, 7)**
  - [x] Bind 18 hotkeys: `L` → label `lobby`, `T` → `transition`, `S` → `score`, `1`-`9`,`0`,`q`,`w`,`e`,`r` → maps from `MAP_LABELS`.
  - [x] `_label_current(class_name)` snap → makedirs → `_next_seq` → `_output_path` → `extract_frame_at_timestamp` → `cv2.imwrite`; updates `_last_written`, increments session count, logs to stdout, refreshes status bar with `snapped <cursor> → <pts>`.
  - [x] `Backspace` → `_undo()`: if `_undo(self._last_written)` returned True, decrement session count for that class, clear `self._last_written`, status bar update, log `[undo] removed <basename>`. Else `self.bell()`.

- [x] **Task 6: HUD-version prompt + bootstrap (AC: 2, 3)**
  - [x] In `main()`: after CLI parsing, before instantiating the Tk app, run `check_ffmpeg()` (raises if missing — let it propagate; user gets a clean error).
  - [x] Pull duration via `get_video_duration(video_path)`, then `keyframe_pts = get_keyframe_timestamps(video_path, scan_duration=int(duration) + 1)`. Print `Found <N> keyframes spanning <duration:.1f>s` to stdout.
  - [x] Show a Tk modal — custom `tk.Toplevel` with two buttons `"HUD 1.0"` / `"HUD 2.0"`, modal-grabbed via `wait_window()`. The selection is the only way to dismiss; closing the window without selecting → exit cleanly.
  - [x] Pass version + keyframes into `VideoTimelineLabelerApp` and `mainloop()`.

- [x] **Task 7: Tests (AC: 9)**
  - [x] Create `apps/tooling/tests/test_video_timeline_labeler.py`. Added minimal `apps/tooling/tests/conftest.py` that prepends `apps/tooling/` onto `sys.path` so `from tools.video_timeline_labeler import ...` resolves under `pytest`.
  - [x] Tests for `_snap_to_keyframe` — eight cases (six per AC9 + empty list + unknown policy).
  - [x] Tests for `_output_path` + `_format_hhmmss` — sub-1-hour, over-1-hour, seq padding, negative-clamp.
  - [x] Tests for `_next_seq` — empty dir, populated dir, non-conforming filenames, missing dir.
  - [x] Tests for `_undo` — happy path, None path, missing-file no-op, freed-number reuse, double-undo no-op.
  - [x] All FS-touching tests use `tmp_path`. 21 tests, all pass: `cd apps/tooling && uv run pytest tests/test_video_timeline_labeler.py -v` → `21 passed in 2.40s`.

- [x] **Task 8: TUI registration in wardentooling.py (AC: 8)**
  - [x] Added `flow_tool6` flow function mirroring `flow_tool1`. Prompts: `browse_video_file`, optional `-o` text, optional `--snap` `questionary.select` over `["nearest", "prior", "after"]`.
  - [x] Updated `_TOOL_MAP` to include `"video_timeline_labeler": ("Tool 6 — Label Frames from Video Timeline", flow_tool6)`.
  - [x] Updated `choices_main` in `menu_main` to insert `"Tool 6 — Label Frames from Video Timeline"` between Tool 5 and Dev Tools.
  - [x] Added `elif choice == "Tool 6 — …":` branch in the `menu_main` while-loop following the Tool 5 branch shape.
  - [x] Updated `_reprompt_source` with a `tool_key == "video_timeline_labeler"` branch (re-prompt video path only; preserve `-o` and `--snap` from saved args) — same pattern as the `game_detector` branch.

- [ ] **Task 9: Manual smoke test (AC: 1-7)**
  - [ ] Run `python apps/tooling/wardentooling.py` → select Tool 6 → pick a real EVA MP4 (1080p, 30fps; one of the 3 reference videos Stephane has staged). HUD prompt fires. Player renders. Scrub. Try every hotkey. Confirm output files appear at `<output>/v2.0/<class>/001_<HHmMSs>.png`. Confirm `Backspace` removes the latest. Confirm `--snap prior` and `--snap after` produce different sequencing on a deliberately-between-keyframes cursor.

- [ ] **Task 10: PR + sprint-status flip (AC: 10, 11)**
  - [ ] Branch `tool-6-video-timeline-labeler`. Single PR with title `feat: Tool 6 — video timeline labeler (Story 9.5)`.
  - [ ] In the same commit set: flip sprint-status `9-5-video-timeline-labeler-tool-6: backlog → review`.
  - [ ] Open PR, link this story file + Epic 9 charter + Track C section.
  - [ ] Post-merge: tiny follow-up commit/PR flips `review → done` and bumps `last_updated` (Two-PR pattern per `feedback_two_pr_docs_execution.md`).

## Dev Notes

### Strategic context

This story produces the **input** for Story 9.6 (Tool 7 — Overlay Stack Analyzer, follow-up). 9.6 reads `labeled/v<ver>/<class>/*.png` and emits per-class mean.png + stddev.png to surface ROI candidates for the new-HUD `gameDetector` rework. Tool 6 must produce sequenced, version-partitioned PNGs in a directory layout 9.6 can scan trivially. **DO NOT** attempt the overlay/stacking analysis in this story — that's 9.6's scope and we don't yet know the right ROI shape; ship Tool 6 first, label real data, then design 9.6 against observed dataset shape.

### Key code patterns to reuse (NOT reinvent)

| Need | Source | Notes |
|---|---|---|
| ffmpeg keyframe PTS list | [`utils/video.py:99 get_keyframe_timestamps`](apps/tooling/utils/video.py#L99) | Pass `scan_duration=int(duration)+1` to get the FULL list. Default of 30 s is for spot-checks only. |
| Single-frame keyframe decode | [`utils/video.py:276 extract_frame_at_timestamp`](apps/tooling/utils/video.py#L276) | Returns BGR numpy ready for `cv2.imwrite`. |
| Video duration | [`utils/video.py:70 get_video_duration`](apps/tooling/utils/video.py#L70) | Returns float seconds. |
| ffmpeg availability check | [`utils/video.py:22 check_ffmpeg`](apps/tooling/utils/video.py#L22) | Raises `RuntimeError` with clean message. Cache prevents repeat checks. |
| Tk Canvas frame rendering | [`tools/frame_labeler.py:279 _render_image`](apps/tooling/tools/frame_labeler.py#L279) | RGB scale-to-canvas math; PhotoImage GC pattern. |
| Per-class sequence counter | [`tools/frame_labeler.py:136 next_game_counter`](apps/tooling/tools/frame_labeler.py#L136) | Glob `*.png`, count, +1. |
| MAP_LABELS source-of-truth | [`tools/frame_labeler.py:23 MAP_LABELS`](apps/tooling/tools/frame_labeler.py#L23) | Per `tooling-LABEL-002` — DO NOT duplicate; import. |
| TUI registration shape | [`wardentooling.py:167 flow_tool1`](apps/tooling/wardentooling.py#L167) + [`wardentooling.py:436 _TOOL_MAP`](apps/tooling/wardentooling.py#L436) | Mirror flow_tool1's questionary structure; mirror Tool 5 branch in menu_main. |
| Last-run persistence | [`wardentooling.py:47 save_last_run`](apps/tooling/wardentooling.py#L47) | Called on `returncode == 0` only. |

### Anti-patterns / disasters to avoid

- **DO NOT** re-decode keyframe lists on every label press. Cache the full PTS list once at video open (Task 6). This is one ffprobe call per video — cheap once, ruinous per-keystroke.
- **DO NOT** use `cv2.VideoCapture.set(CAP_PROP_POS_MSEC, ...)` to extract the keyframe for the PNG write — `VideoCapture` may return a non-keyframe due to GOP seek behavior. Use `extract_frame_at_timestamp` (ffmpeg subprocess) for the WRITE; `VideoCapture` is for the player display only. The two paths are intentionally separate per the architecture-tooling.md decode-boundary commitment ("FFmpeg subprocess for I-frame-only extraction; OpenCV's VideoCapture cannot selectively decode keyframes only").
- **DO NOT** import `MAP_LABELS` by copy-paste. Per `tooling-LABEL-002`: single source at [`frame_labeler.py:23-38`](apps/tooling/tools/frame_labeler.py#L23). Use `from tools.frame_labeler import MAP_LABELS, LABEL_DISPLAY`.
- **DO NOT** allow HUD-version change mid-session. The output partition is per-session — re-launching is the right way to switch. A version-toggle button would invite contamination across `v1.0/` and `v2.0/`.
- **DO NOT** auto-advance to "next frame to label" after a label press. This is a manual-cursor tool, not a queue tool — Stephane stays in control of the cursor; the keyframe at the cursor gets labeled and the player remains where it was. (Tool 2 auto-advances because it's stepping through a fixed list of pre-extracted PNGs; Tool 6's input is a continuous video.)
- **DO NOT** add the overlay/stacking analysis. That's Story 9.6 — explicitly out of scope per AC list.

### File structure

```
apps/tooling/
  tools/
    video_timeline_labeler.py        # NEW (this story)
    frame_labeler.py                  # UNCHANGED (Tool 2; provides MAP_LABELS import)
  tests/
    test_video_timeline_labeler.py   # NEW (this story)
  wardentooling.py                    # UPDATED (TUI registration: Tool 6 + _TOOL_MAP + _reprompt_source)

# Output (not committed; gitignored already by `output/` convention)
output/labeled/
  v1.0/
    lobby/
      001_00h05m12s.png
      002_00h08m43s.png
    horizon/
      001_00h12m34s.png
    transition/
    score/
    ...
  v2.0/
    lobby/
    ...
```

### Testing standards

- pytest 8.0+ already in `apps/tooling/pyproject.toml` `[project.optional-dependencies] dev` (no install action required if running `uv run pytest`).
- The tooling tests directory is currently empty — `apps/tooling/tests/test_video_timeline_labeler.py` will be the first `test_*.py` file. Confirm `uv run pytest` discovers it. If a `conftest.py` is required, add the minimal one (probably just a `sys.path` insert so `from tools.video_timeline_labeler import _snap_to_keyframe` works); copy any pattern from the existing `tools/` directory layout's import style.
- **No GUI testing.** Tk-headless test infrastructure is not worth setting up for a one-user tool. Pure helpers (`_snap_to_keyframe`, `_output_path`, `_next_seq`, `_undo`) get full coverage; the Tk app class is exercised by manual smoke test (Task 9).
- Run command: `cd apps/tooling && uv run pytest tests/test_video_timeline_labeler.py -v`. Pre-commit / CI: per architecture-tooling.md, `pnpm --filter tooling test` is the orchestrator wrapper — it should pick up the new test file automatically.

### Library / framework requirements

- **Python ≥ 3.11** (pyproject baseline).
- **OpenCV** (`opencv-python ≥ 4.8, < 5`) — already a dep. Used for `VideoCapture` (player), `cv2.imwrite` (write), `cv2.cvtColor` (BGR→RGB for PIL).
- **Pillow** — used by [`frame_labeler.py:21`](apps/tooling/tools/frame_labeler.py#L21) for `PIL.Image` + `PIL.ImageTk`. Currently NOT in `pyproject.toml` `dependencies` — must be a transitive dep (verify via `uv tree | grep -i pillow` after install). If it's not transitive (i.e. `pip` grabs it ad-hoc on the local dev box but `uv` doesn't pull it), add `pillow>=10,<12` to `dependencies` in `pyproject.toml` as part of this story. Don't ship Tool 6 with an undeclared runtime dep.
- **Tkinter** — Python stdlib on Windows + standard Linux/macOS python builds. No install action.
- **FFmpeg / ffprobe** — system dep, already required by Tools 1/3/5; `check_ffmpeg()` enforces.
- No new dependencies should be required beyond the Pillow declaration check.

### Sprint-fit + dependencies

- **Track C** (tooling chain) per [sprint-plan.md:111](_bmad-output/sprint-plan.md#L111). Runs in parallel with Track A (Firebase auth) + Track B (foundation). Independent of AR-SPIKE outcome.
- **No upstream story dependencies.** Tool 6 is a new entry point; doesn't read or modify `map_config.json`. Stories 9.1–9.4 do not block this and are not blocked by it.
- **Downstream:** Story 9.6 (Tool 7 — Overlay Stack Analyzer) consumes Tool 6's output. Future re-fingerprinting story (TBD, post-9.6) will produce the new-HUD `map_config.json` — that work depends on Tool 6 + Tool 7 both shipping but is out of this story's scope.

### Project Structure Notes

- Naming: `video_timeline_labeler.py` follows the existing snake_case + descriptive-noun convention (`game_detector.py`, `frame_labeler.py`, `map_config_generator.py`, `hash_validator.py`, `warden_analyzer.py`).
- Tool 6 sits next to Tool 2 in `tools/`, but they are independent — Tool 2 still serves Tool 1's PNG output flow per `tooling-LABEL-001`.
- Output path is under `output/labeled/` — same parent directory as Tool 2's labeled output (which writes to `output/labeled/<map>/`). The HUD-version prefix `v<ver>/` keeps Tool 6's output cleanly separated from Tool 2's; no collision possible.
- No conflict with the canonical 14-map list. The `lobby` / `transition` / `score` classes are NEW class folders that did not previously exist under `output/labeled/` — the dev agent should NOT add them to `MAP_LABELS` (that constant is the **map** source-of-truth, not the **class** source-of-truth).

### References

- [Source: _bmad-output/epics-and-stories.md#Epic-9](_bmad-output/epics-and-stories.md#L2614) — Epic 9 charter
- [Source: _bmad-output/sprint-status.yaml](_bmad-output/sprint-status.yaml#L2) — `last_updated` line citing "new-HUD work" prerequisite
- [Source: _bmad-output/sprint-plan.md#Track-C](_bmad-output/sprint-plan.md#L111) — Track C tooling chain
- [Source: docs/architecture-tooling.md](docs/architecture-tooling.md) — pipeline architecture; ffmpeg keyframe-only decode boundary
- [Source: apps/tooling/tools/frame_labeler.py:23-38](apps/tooling/tools/frame_labeler.py#L23-L38) — MAP_LABELS canonical list (do not duplicate)
- [Source: apps/tooling/utils/video.py:99-135](apps/tooling/utils/video.py#L99-L135) — `get_keyframe_timestamps`
- [Source: apps/tooling/utils/video.py:276-312](apps/tooling/utils/video.py#L276-L312) — `extract_frame_at_timestamp`
- [Source: apps/tooling/wardentooling.py:436-442](apps/tooling/wardentooling.py#L436-L442) — `_TOOL_MAP` registration site
- Memory: `feedback_ac_checkbox_tighten.md` — AC checkbox convention for post-merge items
- Memory: `feedback_two_pr_docs_execution.md` — Two-PR pattern for sprint-status flips
- Memory: `project_warden_new_hud_labeler.md` — Tool 6/7 plan + locked design decisions

## Dev Agent Record

### Agent Model Used

`claude-opus-4-7[1m]` (Claude Opus 4.7, 1M-context). Implementation date: 2026-05-09.

### Debug Log References

- Confirmed Pillow is a transitive dep via `imagehash` (`uv tree | grep -i pillow` → `pillow v12.2.0`). No `pyproject.toml` change needed; this matches the `frame_labeler.py` precedent.
- `utils.format.format_timestamp` returns `MMmSSs` (no hour component), incompatible with the AC6/AC9 `HHmMSs` requirement → inlined `_format_hhmmss(pts)` per the carve-out in Task 2.
- `apps/tooling/tests/` was previously empty (only a `fixtures/` subdir). Added `conftest.py` so `from tools.video_timeline_labeler import ...` resolves; verified pytest discovery via `uv sync --extra dev` followed by a full run.
- **Smoke-test feedback loop (2026-05-09):** First smoke attempt against a 73-min / 2.2 GB capture appeared to hang. Diagnosed three causes: (1) the original `utils.video.get_keyframe_timestamps` uses `-show_frames` which inspects every frame in the scan range — on a 73-min H.264 capture this exceeded 5 minutes; (2) the tool printed nothing during the scan, so the wait looked like a crash; (3) the HUD modal used `tk.Toplevel(transient=withdrawn_root)` which can render the dialog invisible/behind on Windows. Fixes applied in this session: `utils.video.get_keyframe_timestamps` switched to packet-level inspection (`-show_packets ... flags=K`) — same signature, same return value, same callers (`get_gop_interval`, `bsd_roi_debugger.py`, this tool); benchmarked 1.81 s vs >5 min on the 2.2 GB capture, identical PTS values. Added flushed progress prints around the slow operations. Replaced the HUD prompt with a single visible `Tk()` window (`-topmost` flash, screen-centered, no `transient`).

### Completion Notes List

- **Implementation**: 1 new tool module (`video_timeline_labeler.py`, ~470 LOC including the Tk app), 1 new test module (`test_video_timeline_labeler.py`, 21 tests), 1 new `tests/conftest.py`, and 5 surgical edits to `wardentooling.py` (flow function + `_TOOL_MAP` entry + `_reprompt_source` branch + `choices_main` entry + `menu_main` branch).
- **Pure helpers (`_snap_to_keyframe`, `_output_path`, `_format_hhmmss`, `_next_seq`, `_undo`)** are top-level module functions (NOT methods on the Tk app class) so they're testable without instantiating `Tk()`. The Tk app class composes these helpers.
- **Decode boundary preserved**: `cv2.VideoCapture` is used only for the player display; the WRITE path goes through `extract_frame_at_timestamp` (ffmpeg subprocess) per the architecture-tooling.md commitment that "OpenCV's VideoCapture cannot selectively decode keyframes only."
- **MAP_LABELS source-of-truth preserved**: tool 6 imports `MAP_LABELS` and `LABEL_DISPLAY` from `tools.frame_labeler` rather than duplicating the list.
- **Tests**: 21/21 passing in 2.40 s under `pytest 9.0.3`.
- **Task 9 (manual smoke test) is a human-driven gate** that the dev agent cannot execute — the AC checkbox stays `[ ]` pending Stephane's run against a real EVA MP4. Before marking the story `review`, exercise: HUD prompt fires, player renders, scrub via slider/J/K/Left/Right/Shift-arrows works, all 18 hotkeys produce `<output>/v<ver>/<class>/001_<HHmMSs>.png`, Backspace undoes the most recent, and `--snap prior` vs `--snap after` produce different sequencing on a between-keyframes cursor.
- **AC10/AC11 + Task 10** are post-merge admin per the AC-checkbox-tighten convention; held `[ ]` until the PR (and the tiny follow-up `review → done` flip) lands.

### File List

- **Added** `apps/tooling/tools/video_timeline_labeler.py`
- **Added** `apps/tooling/tools/video_timeline_labeler.md` (concise launch + smoke-test guide; sibling-doc rather than expanding the stale `apps/tooling/README.md`)
- **Added** `apps/tooling/tests/test_video_timeline_labeler.py`
- **Added** `apps/tooling/tests/conftest.py`
- **Modified** `apps/tooling/wardentooling.py` (Tool 6 flow + `_TOOL_MAP` + `_reprompt_source` + `choices_main` + `menu_main` branch)
- **Modified** `apps/tooling/utils/video.py` (`get_keyframe_timestamps` switched to packet-level `-show_packets` strategy — orders-of-magnitude speedup on long captures; signature, return value, and `scan_duration` semantics preserved. Benefits all callers: `get_gop_interval`, `bsd_roi_debugger.py`, Tool 6.)
- **Modified** `_bmad-output/sprint-status.yaml` (`9-5-video-timeline-labeler-tool-6: ready-for-dev → in-progress`; `last_updated` to be flipped at Step-9 close)
- **Modified** `_bmad-output/implementation-artifacts/9-5-video-timeline-labeler-tool-6.md` (this file: status, ACs, tasks, Dev Agent Record, File List, Change Log)

### Change Log

| Date       | Author             | Summary |
|------------|--------------------|---------|
| 2026-05-09 | dev-agent (Opus 4.7 1M) | Story 9.5 implementation: Tool 6 video_timeline_labeler — pure helpers + Tk app + TUI registration + 21-test pytest suite. Tasks 1–8 closed. Task 9 (manual GUI smoke test) and AC10/AC11 + Task 10 held `[ ]` per AC-checkbox-tighten convention pending Stephane's smoke run + PR merge. Sprint-status flipped `ready-for-dev → in-progress` (final `→ review` flip deferred to post-smoke-test commit). |
| 2026-05-09 | dev-agent (Opus 4.7 1M) | Smoke-feedback patch: (a) `utils.video.get_keyframe_timestamps` switched from frame-level (`-show_frames`) to packet-level (`-show_packets ... flags=K`) inspection — 1.81 s vs >5 min on the 73-min/2.2 GB reference capture, identical 1,061-keyframe PTS list; (b) flushed progress prints around the slow probe + scan; (c) HUD-version modal rebuilt as a single visible top-level `Tk()` (no withdrawn root + transient) with `-topmost` flash and screen-centering. Tool 6 launch unblocked; 21/21 tests still green. |
| 2026-05-09 | dev-agent (Opus 4.7 1M) | Smoke-pass UX add (Stephane request): (a) HUD prompt now shows the video's first frame as a 360-px thumbnail (uses `extract_frame_at_timestamp_scaled`); (b) added a **Custom…** button on the HUD prompt that opens a `simpledialog.askstring` and validates the entry through new pure helper `_is_valid_hud_version` (allows `[A-Za-z0-9._-]+`, rejects empty / `.` / `..` / path-separators / whitespace / specials); (c) added a dual-row label-button bar to the player UI — special classes (Lobby/Transition/Score) + Undo on row 1, the 14 maps on row 2, every button labeled with its hotkey in parens, click-equivalent to keypress. AC2 still satisfied (modal blocks until selection); AC2 spec wording "1.0 and 2.0" is extended to allow custom versions per Stephane's request — non-breaking superset. 5 new tests for `_is_valid_hud_version` (26/26 green). |
| 2026-05-09 | dev-agent (Opus 4.7 1M) | Auto-advance after label (Stephane request): on every successful label write — button or hotkey — the cursor now jumps to the next keyframe in `self._keyframe_pts`. **Deviates from the original Dev Notes anti-pattern "DO NOT auto-advance"**: the rationale there was "Stephane stays in control of the cursor", but in practice during the smoke run it created friction (cursor frozen after labeling looked like nothing happened). Backspace undo intentionally does NOT advance — leaves the cursor on the just-undone position so a re-label is one-click. Also added `self.focus_set()` at the start of `_label_current` and `_on_backspace` so hotkeys keep firing after a button click. No new tests (UI-only behavior; pure helpers untouched). 26/26 still green. |
| 2026-05-10 | dev-agent (Opus 4.7 1M) | Minute-sample workflow + same-class auto-backfill (Stephane request — "save me a lot of time"): cursor advance step changed from "next keyframe" to **+60s snapped to nearest keyframe**, configurable via `self._advance_step_s` (default 60.0). Added auto-backfill: if `self._last_label_class == class_name` and `class_name != "transition"` and `self._last_label_pts < snapped`, the tool writes a labeled PNG for every keyframe strictly between the two label positions — same class, individual seq numbers, full per-frame ffmpeg decode. Two consecutive `Horizon` labels at min 5 and min 6 ≈ 15 backfilled PNGs. Refactored `self._last_written: str | None` → `self._last_written_batch: list[str]`; Backspace now undoes the entire last batch (single label OR full backfill). Status bar gained a top-right "Advance: +60s + same-class backfill (skip transition)" indicator. Added defensive routing assertion in `_label_current` to surface any future class/path mismatch loudly. Print statements gained `flush=True` so terminal log is reliable for diagnosing the still-open "artefact-folder pollution" report. UI-only changes; 26/26 tests still green. |
| 2026-05-10 | dev-agent (Opus 4.7 1M) | Backfill not firing — diagnostic refactor: extracted the backfill decision into a pure helper `_backfill_between(last_class, last_pts, current_class, current_pts, keyframes, skip_classes)` and added 7 unit tests covering same-class consecutive, mismatched class, no-previous-label, transition skip, equal/backwards PTS (no-op), exclusive endpoints, and custom skip-class set. All 33/33 tests pass — the logic is verified. Added a one-line diagnostic print before each backfill check (`[backfill-check] last_class=... current_class=... last_pts=... snapped=... -> N keyframe(s)`) so the next run's terminal log will show exactly why backfill skipped: most likely a non-consecutive same-class call (intervening label) or `Backspace` between the two labels (which intentionally resets `_last_label_class` to None). |
| 2026-05-10 | dev-agent (Opus 4.7 1M) | **ROOT CAUSE — artefact pollution + non-firing backfill: Tk binding ambiguity.** Stephane's terminal log proved every intended label was paired with an artefact write at the same PTS. `self.bind("<1>", …)` does NOT bind to the digit "1" key — Tk treats bare `<1>`..`<5>` as `<Button-1>`..`<Button-5>` (mouse buttons). Every left-click anywhere in the player (including clicks on the map buttons) fired the `<1>` handler routed to `MAP_LABELS[0] = "artefact"`. That spurious artefact write also broke the same-class-backfill check: between two intended `lobby` clicks, an artefact sneak-in flipped `_last_label_class` to "artefact", so the second lobby never matched. Backfill correctly fired for **artefact** (consecutive artefact writes) — the only class that could ever satisfy the check under the bug. **Fix:** every key binding now uses the explicit `<KeyPress-X>` form (digits, letters, special keys, modifier combos). Tk no longer ambiguates the digit keys with mouse buttons. Cleanup advice for Stephane's existing `output/labeled/v2.0/artefact/` folder: nuke it entirely and re-label only the actual artefact map sessions (false positives outnumber genuine artefact frames). 33/33 tests still green; UI-only fix, no test changes needed (Tk-binding semantics aren't worth a headless-Tk test rig per the original story Dev Notes). |
