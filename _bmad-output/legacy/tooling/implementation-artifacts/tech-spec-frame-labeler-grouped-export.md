---
title: 'Frame Labeler — Grouped Multi-Frame Export'
slug: 'frame-labeler-grouped-export'
created: '2026-03-19'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['python3.8+', 'pillow', 'tkinter', 're']
files_to_modify: ['tools/frame_labeler.py']
code_patterns: ['modular CLI in tools/', 'argparse CLI pattern', 'file-based I/O between tools', 'tkinter GUI with keyboard shortcuts']
test_patterns: ['none established']
---

# Tech-Spec: Frame Labeler — Grouped Multi-Frame Export

**Created:** 2026-03-19

## Overview

### Problem Statement

Tool 2 (`frame_labeler.py`) currently exports only the score frame when labeling a game session. Tool 3 (hash comparator) needs all three frame types — start, end, and score — to test different hashing strategies. If the score screen is not reliable for map recognition, the entire labeling session is wasted: the user would need to redo labeling from scratch to get start/end frames. All three frame types must be exported together, linked, and available so any combination can be used for hashing without re-labeling.

### Solution

When the user labels a score frame in Tool 2, automatically find and co-export the matching start and end frames from the same game session. All three files are renamed to `{counter:03d}_{type}.png` and placed flat in `labeled/<map>/`. The counter is per-map and increments with each labeled game. Linking is done by sequence number extracted from the original filename: for a score frame with sequence N, find the most recent `start` with seq < N, and the most recent `end` with seq between start and N.

### Scope

**In Scope:**
- `tools/frame_labeler.py` only
- New helper: `parse_seq_num(filename) -> int | None`
- New helper: `find_linked_frames(score_path) -> tuple[str|None, str|None]`
- New helper: `next_game_counter(dest_dir) -> int`
- Modified `_label_current()` — copy all three frames with new names
- Modified `_undo()` — remove all three copied files

**Out of Scope:**
- Tool 3 (`hash_comparator.py`)
- Tool 1 (frame extraction / Black Screen Detector)
- `config/config.yaml`
- GUI/UX changes (tool still shows only score frames for labeling)

## Context for Development

### Codebase Patterns

- `tools/frame_labeler.py` is a standalone `tkinter` app with `argparse` CLI, no dependencies on `utils/`
- Current labeling: `shutil.copy2(src, dest)` — non-destructive copy, keep this behavior
- `_last_action` currently stores `(src, dest)` 2-tuple for single-file undo — must become a list of dest paths
- Frame filenames from Tool 1: `{timestamp}_{type}_{seqnum}.png` — e.g. `00m14s_start_001.png`, `07m12s_end_002.png`, `08m10s_score_003.png`
- Sequence numbers are global across all frame types, increasing chronologically
- Game session order: `start_N` → gameplay → `end_M` (M > N) → `score_P` (P > M)
- `find_score_images()` uses recursive glob (`**/*score*.png`), so score frames may live in subdirectories of `source_dir`

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/frame_labeler.py` | Only file being modified — lines 55–60 (`find_score_images`), 212–225 (`_label_current`), 227–238 (`_undo`) |
| `tests/fixtures/astera_expected.json` | Real frame filename examples and sequence number pattern |

### Technical Decisions

- **Linking by sequence number**: Parse trailing `_NNN` integer via `r'_(\d+)\.png$'`. For `score_P`: start = max seq among start files where seq < P; end = max seq among end files where start_seq < seq < P.
- **Counter is per-map**: `next_game_counter(dest_dir)` counts existing `*_score.png` files in the dest dir and returns count + 1. Robust to undo — removed files naturally decrement the count.
- **Copy, not move**: Keep `shutil.copy2` — non-destructive, source files preserved.
- **Graceful missing frames**: If no matching start or end found, copy only what exists and print a console warning. Do not block labeling.
- **Scan same directory**: `find_linked_frames` scans `os.path.dirname(score_path)`, not `source_dir` root. Since `find_score_images` is recursive, score frames may be in subdirectories (e.g. `source/video_name/score.png`). Scanning the same dir avoids cross-session false matches.
- **Undo covers all three**: `_last_action` becomes a list of dest paths. `_undo()` iterates and removes all.

## Implementation Plan

### Tasks

- [x] Task 1: Add `import re` and helper `parse_seq_num`
  - File: `tools/frame_labeler.py`
  - Action: Add `import re` after line 13 (`import sys`). Add the following function at module level after the `find_score_images` function (after line 60):
    ```python
    def parse_seq_num(filename):
        """Return the trailing sequence integer from a filename like '00m14s_start_001.png', or None."""
        match = re.search(r'_(\d+)\.png$', filename)
        return int(match.group(1)) if match else None
    ```
  - Notes: `re` is stdlib, no new dependency.

- [x] Task 2: Add helper `find_linked_frames`
  - File: `tools/frame_labeler.py`
  - Action: Add the following function at module level after `parse_seq_num`:
    ```python
    def find_linked_frames(score_path):
        """Find the start and end frames that belong to the same game session as the given score frame.

        Scans the same directory as score_path. Uses the global sequence number
        embedded in filenames to identify the most recent start/end before the score.
        Returns (start_path, end_path); either may be None if not found.
        """
        score_seq = parse_seq_num(os.path.basename(score_path))
        if score_seq is None:
            return None, None

        scan_dir = os.path.dirname(score_path)
        start_candidates = []  # (seq, full_path)
        end_candidates = []

        for fname in os.listdir(scan_dir):
            if not fname.endswith('.png'):
                continue
            seq = parse_seq_num(fname)
            if seq is None or seq >= score_seq:
                continue
            full = os.path.join(scan_dir, fname)
            if 'start' in fname:
                start_candidates.append((seq, full))
            elif 'end' in fname:
                end_candidates.append((seq, full))

        start_path = max(start_candidates, key=lambda x: x[0])[1] if start_candidates else None
        start_seq = parse_seq_num(os.path.basename(start_path)) if start_path else -1

        valid_ends = [(s, p) for s, p in end_candidates if s > start_seq]
        end_path = max(valid_ends, key=lambda x: x[0])[1] if valid_ends else None

        return start_path, end_path
    ```
  - Notes: Returns `(None, None)` if score has no sequence number. Returns `(start_path, None)` or `(None, end_path)` for partial matches.

- [x] Task 3: Add helper `next_game_counter`
  - File: `tools/frame_labeler.py`
  - Action: Add the following function at module level after `find_linked_frames`:
    ```python
    def next_game_counter(dest_dir):
        """Return the next sequential game counter for a labeled map directory.

        Counts existing *_score.png files to determine the next number.
        """
        existing = glob.glob(os.path.join(dest_dir, '*_score.png'))
        return len(existing) + 1
    ```
  - Notes: `glob` is already imported. Per-map counter because each map dir is separate.

- [x] Task 4: Rewrite `_label_current` in `FrameLabelerApp`
  - File: `tools/frame_labeler.py`, lines 212–225
  - Action: Replace the entire `_label_current` method body with:
    ```python
    def _label_current(self, label):
        if self.current_index >= len(self.images):
            return

        src = self.images[self.current_index]
        dest_dir = os.path.join(self.output_dir, label)
        counter = next_game_counter(dest_dir)
        start_src, end_src = find_linked_frames(src)

        score_dest = os.path.join(dest_dir, f"{counter:03d}_score.png")
        shutil.copy2(src, score_dest)
        copied = [score_dest]

        if start_src:
            start_dest = os.path.join(dest_dir, f"{counter:03d}_start.png")
            shutil.copy2(start_src, start_dest)
            copied.append(start_dest)
        if end_src:
            end_dest = os.path.join(dest_dir, f"{counter:03d}_end.png")
            shutil.copy2(end_src, end_dest)
            copied.append(end_dest)

        if not start_src or not end_src:
            missing = [t for t, p in [('start', start_src), ('end', end_src)] if not p]
            print(f"  [warn] no {'/'.join(missing)} found for {os.path.basename(src)}")

        extra = f"(+ start, end)" if start_src and end_src else f"({len(copied) - 1} linked)"
        print(f"  [{label}] {counter:03d}_score.png {extra}")

        self._last_action = copied
        self._btn_undo.config(state=tk.NORMAL)
        self._next()
    ```
  - Notes: `copied` is a list of dest paths — compatible with updated `_undo`. Score is always copied first.

- [x] Task 5: Rewrite `_undo` in `FrameLabelerApp`
  - File: `tools/frame_labeler.py`, lines 227–238
  - Action: Replace the entire `_undo` method body with:
    ```python
    def _undo(self):
        if self._last_action is None:
            return
        for dest in self._last_action:
            if os.path.exists(dest):
                os.remove(dest)
                print(f"  [undo] removed {os.path.basename(dest)}")
        self._last_action = None
        self._btn_undo.config(state=tk.DISABLED)
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current()
    ```
  - Notes: Iterates over all paths in the list, removing each. Logic for `current_index` is identical to the original.

### Acceptance Criteria

- [x] AC 1: Given source dir contains `00m14s_start_001.png`, `07m12s_end_002.png`, `08m10s_score_003.png`, when I label the score frame as "horizon", then `labeled/horizon/001_start.png`, `labeled/horizon/001_end.png`, and `labeled/horizon/001_score.png` are created, and the source files remain unchanged.

- [x] AC 2: Given `labeled/horizon/` already contains `001_*.png` files, when I label a second game as "horizon", then the new files are named `002_start.png`, `002_end.png`, `002_score.png`.

- [x] AC 3: Given `labeled/horizon/` contains `001_*`, `002_*`, `003_*` files, when I sort the directory by name, then files group as `001_end`, `001_score`, `001_start`, `002_end`, `002_score`, `002_start` — all frames for the same game are adjacent.

- [x] AC 4: Given I just labeled a game creating `001_start.png`, `001_end.png`, `001_score.png`, when I click Undo, then all three files are removed from `labeled/horizon/` and the GUI returns to the score frame.

- [x] AC 5: Given a score frame with seq 001 and no preceding start/end files in its directory, when I label it, then only `001_score.png` is created, a console warning listing the missing types is printed, and the labeler advances normally.

- [x] AC 6: Given a source dir where the score frame lives in a subdirectory (`source/video_name/score.png`), when I label it, then the correct start/end from the same subdirectory are found (not from a different session in a sibling subdirectory).

## Additional Context

### Dependencies

No new dependencies. `re` is Python stdlib. `glob`, `os`, `shutil` are already imported in `frame_labeler.py`.

### Testing Strategy

No formal test framework established. Manual validation steps:
1. Run tool on a source dir with at least 3 complete triplets (start/end/score)
2. Label 2 games to the same map — verify `001_*` and `002_*` naming
3. Verify undo removes all three files and counter resets correctly on next label
4. Test with a source dir containing only a score frame — verify graceful warning and no crash
5. Test with source frames in a subdirectory — verify correct session linking

### Notes

- Only `parse_seq_num()` needs updating if Tool 1 ever changes its filename convention.
- The module docstring on line 1–7 references "score frames" only — update it to reflect multi-frame export after implementation.
- Undo only covers the **last** labeling action. Multiple consecutive undos are not supported (same as original behavior).

## Review Notes
- Adversarial review completed
- Findings: 7 total, 7 fixed, 0 skipped
- Resolution approach: auto-fix
