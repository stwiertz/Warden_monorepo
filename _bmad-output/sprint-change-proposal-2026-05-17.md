# Sprint Change Proposal — Tooling Desktop GUI (Post-V1 Scope Capture)

**Date:** 2026-05-17
**Author:** Stephane (via /bmad-correct-course)
**Mode:** Incremental
**Scope classification:** Moderate (backlog reorganization — new epic; no in-flight story or code change)

---

## Section 1 — Issue Summary

**Problem statement.** A desktop-GUI prototype (HTML/React mock) was produced to replace the questionary TUI launcher (`apps/tooling/wardentooling.py`) for the Warden tooling pipeline. A design review against the *delivered* tools surfaced six behavioral mismatches plus one dominant toolkit decision. This proposal navigates whether/how that work enters the plan.

**Discovery context.** The mismatches were found by reviewing the mock against the source of truth for current tool behavior — `apps/tooling/wardentooling.py` — not the stale `apps/tooling/tools/roi_detection_tester.md` doc.

**Triggering artifact.** No triggering *story* — this is design-validation feedback. Closest delivered context: Stories 9-5 (`review`), 9-12 / 9-13 / 9-14 (`done`).

**Evidence — the six mismatches + toolkit decision:**
1. Tool 9 (`roi_detection_tester`) reports **three** classifiers (HUD-version, binary `in_match`, per-map ID); the report-viewer mock shows only one. Needs per-classifier accuracy + confusion matrices.
2. The mock wires step 4 straight to the report viewer, skipping Tool 9's headless run UI and its real knobs: `--hud-version-threshold`, `--in-match-threshold`, `--map-threshold`, `--limit`, `--save-frame-predictions`.
3. The video-tester mock invents a sample-rate control; `video_test.py` accepts only positional video + `--config` + `--output`.
4. HUD version is globalized to a `v1/v2/v3` enum in the mock; reality is a free-form custom string (labeler modal, e.g. `2.0`), path token `v<ver>` incl. `v2.0`, normalized by the 9.14 `_normalize_hud()` (`v2.0`↔`v2`).
5. Labeler snap policy (`--snap nearest|prior|after`) and snapped-PTS feedback are unsurfaced in the mock.
6. Undo is designed as 20-step in the mock; the delivered labeler is single-step (Backspace = undo last batch).
7. **Toolkit decision:** Tkinter vs PySide6/PyQt6 rebuild. Reusable as-is: `tools/common/zones.py`, `zone_picker/fragments.py`, `variance.py`. Discarded under a Qt rewrite: all Tk GUI glue (`zone_picker/app.py`, `image_inspector/canvas.py` `ImageCanvas`, `ROIMode`/`HSVFilterMode`).

---

## Section 2 — Impact Analysis

**Epic impact.** **Epic 9 is unaffected and completes as planned.** All tools referenced by the mismatches are delivered (9-12/9-13/9-14 `done`; 9-5 `review`); no Epic 9 acceptance criterion depends on a GUI. No Epic 9 story is modified, rolled back, or rescoped. No future epic (incl. Epic 10 launch gate) is invalidated. A **new Epic 11** is required solely to *hold* the GUI initiative and freeze the constraints.

**Story impact.** None. Zero in-flight or completed stories change. No new stories are created now — Epic 11 stories are authored post-V1 via `bmad-create-story`.

**Artifact conflicts.**
- **PRD** — A full GUI conflicts with a deliberate standing decision: PRD:766 "no `--no-tui` headless flag in V1"; PRD:967–970 tooling-TUI-001 (TUI launcher is the V1 entry point). Resolution: keep GUI **post-V1**, add a one-line forward-reference at the existing decision site. No FR/NFR added/removed/modified; MVP integrity preserved.
- **Architecture** — No V1 conflict. The Tk-vs-Qt decision is an **Epic 11** architecture spike, not an Epic 9 change.
- **UX** — No V1 tooling UX spec exists (CLI/TUI). The mock + six constraints become Epic 11's founding UX/AC inputs.
- **Other** — `sprint-status.yaml`, `epics-and-stories.md` register the new epic; `deferred-work.md` carries a discoverable cross-link.

**Technical impact.** None to V1 code. Forward-looking only: the toolkit boundary (pure logic reusable; Tk glue discarded under Qt) is recorded as an Epic 11 spike input.

---

## Section 3 — Recommended Approach

**Selected path: Hybrid — add a new post-V1 Epic 11; do not touch Epic 9.**

Options evaluated:
- *Direct Adjustment (modify Epic 9)* — **Not viable.** Nothing in Epic 9 is wrong; edits would be fabricated work.
- *Rollback* — **Not viable.** No shipped work is defective.
- *MVP Review* — **Not needed.** MVP integrity is *preserved* precisely by keeping the GUI out of V1.

**Rationale.** The honest course correction is that this is not a sprint change to in-flight work — it is net-new post-V1 scope that contradicts a standing PRD decision if pulled into V1. Capturing it as Epic 11 with binding founding constraints (C1–C7) prevents design drift from delivered tool behavior, costs no V1 timeline, and keeps Decision #ES-1's 11-epic V1 structure intact. Effort **Low**; Risk **Low**; timeline impact **None**.

---

## Section 4 — Detailed Change Proposals

### 4.1 `epics-and-stories.md` — add Epic 11 (post-V1)

Append a new `## Epic 11: Tooling — Desktop GUI (POST-V1, NOT V1-BLOCKING)` section after Epic 10, declaring status `backlog · post-V1`, rationale (supersedes nothing; V1 entry point stays the questionary TUI), and **founding constraints C1–C7**:

- **C1** — Tool 9 report MUST expose all three classifiers (hud_version, binary in_match, per-map) with per-classifier accuracy + confusion matrix. Source of truth: `wardentooling.py flow_tool9` (not the stale `.md`).
- **C2** — Tool 9 screen MUST present a configure→run step exposing `--hud-version-threshold`, `--in-match-threshold`, `--map-threshold`, `--limit`, `--save-frame-predictions` before the report view.
- **C3** — Video tester MUST NOT invent controls; `video_test.py` = positional video + `--config` + `--output` only. A sample-rate control is a separate feature request against `video_test.py`.
- **C4** — HUD-version handling MUST adopt the delivered model: free-form custom strings, path token `v<ver>` incl. `v2.0`, normalized via 9.14 `_normalize_hud()`. No invented `v1/v2/v3` global enum.
- **C5** — Labeler MUST surface snap policy (`--snap nearest|prior|after`) and snapped-PTS feedback.
- **C6** — Undo MUST match delivered single-step (Backspace = undo last batch); multi-step undo is a scoped enhancement story.
- **C7** — Toolkit (Tkinter vs PySide6/PyQt6) is an Epic 11 architecture spike. Reusable: `tools/common/zones.py`, `zone_picker/fragments.py`, `variance.py`. Discarded under Qt: `zone_picker/app.py`, `image_inspector/canvas.py` `ImageCanvas`, `ROIMode`/`HSVFilterMode`.

Stories: none yet (post-V1 via `bmad-create-story`). Amend the "Total epics: 11" line (~:668) with a non-destructive addendum noting post-V1 Epic 11 does not alter the V1 structure or Decision #ES-1.

### 4.2 `sprint-status.yaml` — register Epic 11

Append after `epic-10-retrospective: optional`:

```
  epic-11: backlog  # POST-V1, NOT V1-BLOCKING. Tooling Desktop GUI. Added 2026-05-17 (Stephane, /bmad-correct-course): holds a future GUI initiative so its design cannot drift from delivered tool behavior. V1 operator entry point stays the questionary TUI (wardentooling.py) per PRD tooling-TUI-001 + PRD:766. No Epic 9/10/Decision #ES-1 impact. Founding constraints C1–C7 in epics-and-stories.md Epic 11. No stories until post-V1 (bmad-create-story). See sprint-change-proposal-2026-05-17.md.
  epic-11-retrospective: optional
```

### 4.3 `prd.md:766` — one-line forward-reference (no requirement change)

Append to the existing "no `--no-tui` headless flag in V1" bullet: *"A desktop GUI replacing the TUI is likewise post-V1 — tracked as Epic 11 (backlog, non-V1-blocking) with founding constraints C1–C7; see sprint-change-proposal-2026-05-17.md. V1 operator entry point remains the questionary TUI (tooling-TUI-001)."*

### 4.4 `deferred-work.md` — cross-link pointer

Append one bullet in the file's existing idiom pointing at Epic 11, summarizing C1–C7, naming `wardentooling.py` as source of truth, and marking **Deferred to Epic 11 (post-V1)**.

---

## Section 5 — Implementation Handoff

**Scope:** Moderate (backlog reorganization; documentation-only; no code, no in-flight story change).

**Recipient:** Developer agent (direct implementation) — the four edits are mechanical doc changes with exact before/after defined in Section 4.

**Deliverables:**
1. `epics-and-stories.md` — Epic 11 section + ":668" addendum.
2. `sprint-status.yaml` — `epic-11` + `epic-11-retrospective` entries.
3. `prd.md:766` — forward-reference appended.
4. `deferred-work.md` — cross-link bullet.

**Success criteria:**
- Epic 9 and all its stories remain byte-unchanged.
- `sprint-status.yaml` parses; `epic-11: backlog` present; no story keys under it.
- PRD records the post-V1 GUI decision at the original decision site without altering any FR/NFR.
- The six mismatches + toolkit decision are preserved verbatim as binding constraints C1–C7.

**Next step (post-V1):** when V1 ships, run `bmad-create-story` against Epic 11 — first story recommended: the Tk-vs-Qt architecture spike (C7), as it gates all GUI screen work.
