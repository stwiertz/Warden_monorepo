---
date: 2026-05-05
project_name: Warden
author: Bob (Scrum Master) -- BMAD correct-course workflow
trigger_decision: Proposals 4+6 approved 2026-04-20
status: APPROVED + APPLIED (Incremental Mode)
inputDocuments:
  - docs/planning-artifacts/prd.md
  - docs/planning-artifacts/epics.md
  - docs/planning-artifacts/architecture.md
  - docs/planning-artifacts/ux-design-specification.md
  - docs/sprint-status.yaml
  - docs/stories/sprint-status.yaml
---

# Sprint Change Proposal -- 2026-05-05

> **Status:** This proposal was processed in **Incremental Mode** during a `/bmad-bmm-correct-course` workflow on 2026-05-05. All proposed edits were reviewed and approved artifact-by-artifact and have already been applied to the canonical planning documents and downstream story files. This document serves as the formal record of what changed and why.

---

## Section 1: Issue Summary

### Problem statement

While experimenting with different detection methods to identify game transitions in EVA After-h match recordings, **stwiertz discovered that a KDA/HSV-based game-state detector combined with a pHash-based map identifier outperforms the originally-planned luminosity black-screen detector + OpenCV template matcher** -- both in detection accuracy and in operational footprint (Firestore-served config vs. bundled template assets that must ship with the app).

This discovery led to **Proposals 4 + 6, formally approved on 2026-04-20**, which retire Stories 2.3 (black-screen detector) and 2.4 (template matcher) in favor of a new **Sprint 2.5 / Epic 7** delivering Story 7.5 (replacement detectors) plus accompanying view-mode data-model expansion (`pov`/`minimap` -> `full`/`minimap`/`minimap_hud`).

### Categorization

**Failed approach requiring different solution** (primary). The original Sprint 2 plan assumed a luminosity-threshold black-screen detector + OpenCV template matching against bundled map assets would be sufficient to slice game transitions. Hands-on R&D revealed a better methodology -- KDA/HSV game-state detection + pHash map identification -- which is more accurate, more maintainable (config-driven via Firestore vs. shipping bundled templates), and less brittle.

### Discovery context

The detection-methodology pivot was approved 2026-04-20 and reflected in sprint-tracking files ([docs/sprint-status.yaml](sprint-status.yaml), [docs/stories/sprint-status.yaml](../stories/sprint-status.yaml)) and the directly-affected story files ([2.3.md](../stories/2.3.md), [2.4.md](../stories/2.4.md)) earlier this week.

The artifact-drift problem surfaced on **2026-05-04** during sprint-status review while [Story 2.2](../stories/2.2.md) (FFmpeg keyframe extraction) is in-progress. The user observed that two sprint-status files existed -- one canonical, one BMAD-tracker -- and that downstream planning artifacts (PRD, epics, architecture, UX, several story files) still described the old methodology. This course-correction propagates the approved change through the rest of the docs.

### Evidence

1. Sprint-status root file ([docs/sprint-status.yaml](sprint-status.yaml)) defines Sprint 2.5 stories 7.1-7.6 with FRs and supersession notes
2. Stories 2.3 and 2.4 had already been marked `superseded` in both sprint-status YAMLs and via banners in the story files themselves
3. Pre-existing supersession precedent for Story 3.5 -> 7.3 confirms the team operates in this mode
4. The PRD's FR5/FR6 wording (pre-edit) hardcoded methodology ("black screen timestamps", "template matching") -- methodology-specific FRs are an architectural anti-pattern
5. The architecture doc's SQLite schema (pre-edit) had `view_mode CHECK(view_mode IN ('pov', 'minimap'))` -- the 2-value constraint that Story 7.1 changes
6. No completed story rolls back -- Stories 2.3 and 2.4 were never started; Story 2.1 (done) and Story 2.2 (in-progress) are detector-agnostic

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Status | Change |
|---|---|---|
| **Epic 1** Auth/Setup | Untouched | No detector or view-mode references |
| **Epic 2** Video Import & Auto-Slice | **Scope reduced** | Stories 2.3 / 2.4 removed (superseded); Story 2.5 rewired to consume Story 7.5 output; FRs 5/6 move to Epic 7 |
| **Epic 3** Playback & Navigation | **Description refreshed** | Story 3.5 already marked superseded by 7.3 (pre-existing precedent); Epic narrative aligned with 3-value view-mode model |
| **Epic 4** Clip Creation | Untouched | Only references `view_mode` indirectly via clip_exports |
| **Epic 5** Export & Sharing | **Description refreshed** | Stories 5.1/5.2 narrative aligned with view-mode-aware export pipeline coming from Story 7.6; FRs 22-25 jointly owned with Epic 7 |
| **Epic 6** Persistence | Untouched | Auto-save and resume are detector-agnostic |
| **Epic 7** Detection Redesign | **Newly expanded** | Was a one-line summary in epics.md; now has full 6-story breakdown matching Epics 1-6 format |

### Story Impact

| Story | Pre-change | Post-change |
|---|---|---|
| 1.1 - 1.5 | done / ready-for-dev | unchanged |
| 2.1 | done | unchanged |
| 2.2 | in-progress | **3 minor edits** to point downstream consumers to 7.5 (replaces 2.3/2.4 references in user story + dev notes) |
| 2.3 | ready-for-dev | **superseded** by 7.5 (banner added; sprint-status YAMLs updated) |
| 2.4 | ready-for-dev | **superseded** by 7.5 (banner added; sprint-status YAMLs updated) |
| 2.5 | ready-for-dev | **major rewrite** -- now consumes 7.5 detection output instead of 2.3+2.4 (story narrative, AC list, tasks, dev notes, references) |
| 2.6 | ready-for-dev | **1 minor dev note edit** (template matching reference removed) |
| 2.7 | ready-for-dev | unchanged |
| 3.1 - 3.4, 3.6 | not_started | unchanged |
| 3.5 | superseded | unchanged (already marked) |
| 4.1 - 4.6 | not_started | unchanged |
| 5.1 - 5.4, 6.1 - 6.3 | not_started | unchanged |
| 7.1 - 7.6 | ready-for-dev | unchanged in sprint-status; **expanded into full epic detail** in epics.md; **1 cosmetic file-path fix** in 7.5.md (`pipeline.ts` -> `processingPipeline.ts`) |

### Artifact Conflicts (Pre-Change) and Resolutions (Post-Change)

| Artifact | Pre-change conflicts | Post-change state |
|---|---|---|
| **[docs/planning-artifacts/prd.md](prd.md)** | 11 sections referenced old methodology (FR5, FR6, FR14, FR15 wording; MVP table; Processing Pipeline; Tech Stack; Risks; Must-Have Capabilities; Risk Mitigation Strategy; Dépendances Techniques) | All 8 edit batches applied; FRs are now methodology-agnostic (behavior-focused); 3-value view-mode model reflected throughout |
| **[docs/planning-artifacts/epics.md](epics.md)** | Epic 2 description hardcoded methodology; Stories 2.3/2.4/2.5/3.5 entries described old detection; Epic 7 was a 3-line stub; FR Coverage Map mapped 8 FRs to old stories | All 10 edit batches applied; Epic 2/3/5 descriptions refreshed; Stories 2.3/2.4/3.5 marked superseded with pointers; Story 2.5 rewritten to consume 7.5; Epic 7 expanded to full 6-story breakdown; FR Coverage Map updated |
| **[docs/planning-artifacts/architecture.md](architecture.md)** | "OpenCV Integration" section described template matching as primary use case; project structure listed `templateMatcher.ts` and `assets/images/map-templates/`; SQLite schema had 2-value view_mode CHECK constraint; Data Flow diagram showed black-screen + template flow; External Integrations missed Firestore for detection config; NFR1 coverage cited template matching; Gap Analysis #3 listed template assets as unresolved | All 10 edit batches applied; "Detection Methodology" section replaces OpenCV Integration; project structure shows new detector files (gameDetector.ts, mapIdentifier.ts, blackScreenDetector.ts as fallback, detectionConfig.ts); SQLite CHECK constraint = 3-value; Data Flow + External Integrations + NFR1 coverage + Gap Analysis all aligned |
| **[docs/planning-artifacts/ux-design-specification.md](ux-design-specification.md)** | 9 sections used "POV/Minimap" toggle terminology; gestures referenced binary toggle; Component Strategy described 2-value system | All 9 edit batches applied; terminology refreshed to "view-mode" with 3-value semantics; double-tap top-left now cycles Full -> Minimap -> Minimap+HUD; new "View Mode System" sub-section consolidates the 3-mode model into a single explainer block |
| **[docs/stories/2.2.md](../stories/2.2.md)** | User story line cited 2.3/2.4 as downstream consumers; Dev Notes had no supersession context; testing approach pointed at Story 2.3 as the unit-testable seam | 3 edits applied; downstream consumer list redirected to 7.5; supersession note added in "Why this story matters more than it looks"; testing approach updated to point at gameDetector + mapIdentifier (7.5) |
| **[docs/stories/2.5.md](../stories/2.5.md)** | Story narrative, all AC items, Task 1+2, Dev Notes Segmentation algorithm, References block all assumed 2.3/2.4 deliver detection | Major rewrite applied; story is now framed as a CONSUMER of Story 7.5's output; 7 ACs (was 6) including new AC4 for unknown-map handling; tasks reference GameDetectorEvent + MapIdentificationResult types; dev notes explicitly state segmentation does not re-implement detector logic |
| **[docs/stories/2.6.md](../stories/2.6.md)** | One Dev Note line cited "template matching" in performance target | 1 edit applied; performance target now cites gameDetector + mapIdentifier |
| **[docs/stories/7.5.md](../stories/7.5.md)** | File-path typo: `pipeline.ts` (should be `processingPipeline.ts`) | 1 edit applied; file path now consistent with architecture and Story 2.5 |
| **[docs/planning-artifacts/implementation-readiness-report-2026-02-02.md](implementation-readiness-report-2026-02-02.md)** | No indication that the snapshot was outdated by Epic 7 insertion | 1 edit applied; dated footnote at top noting Epic 7 inserted post-report; body intact (preserves historical record) |

### Technical Impact

- **No code changes** -- the entire course-correction is documentation reconciliation. Stories 2.3 and 2.4 were never started, so there's no detector code to remove (Story 7.5 will handle the deletions in `templateMatcher.ts` and `assets/images/map-templates/` when it ships).
- **No data migration** -- pre-production project; SQLite schema CHECK constraint update (Story 7.1) is a future task tracked in the existing Epic 7 stories, not part of this course-correction.
- **No deployment / CI / IaC changes** -- pre-production.
- **In-progress work unblocked** -- Story 2.2 (FFmpeg keyframe extraction) is unaffected by the methodology change and continues toward review.

### MVP Impact

**None.** All 33 FRs preserved. All 4 user journeys (J1: coach happy path, J2: interruption/resume, J3: passive player, J4: active player) preserved. All success criteria preserved. The methodology change is invisible to the user-facing value proposition: import video -> auto-slice -> review -> clip -> share.

---

## Section 3: Recommended Approach

### Selected: Option 1 -- Direct Adjustment

Out of the three options evaluated in the workflow checklist:

| Option | Verdict | Rationale |
|---|---|---|
| **1. Direct Adjustment** | **Selected** ✓ | Update existing stories' narratives + propagate the already-approved Sprint 2.5/Epic 7 change through the canonical planning artifacts and downstream story files |
| 2. Potential Rollback | Not viable | No completed work to revert (Stories 2.3/2.4 never started; 2.1 done + 2.2 in-progress are detector-agnostic) |
| 3. PRD MVP Review | Not viable | MVP scope is unchanged -- methodology change is invisible to user-facing value |

### Justification

| Factor | Reasoning |
|---|---|
| **Implementation effort & timeline** | Low -- ~9 documents, no code changes; completed inline within this workflow run (single session, no follow-up needed) |
| **Technical risk & complexity** | Negligible -- pure documentation reconciliation. No code paths affected, no DB migrations, no behavioral changes to in-progress work |
| **Team morale & momentum** | Positive -- the planning system caught artifact drift; closing it cleanly demonstrates the discipline. Keeps Story 2.2 unblocked |
| **Long-term sustainability** | High -- restores single source of truth across PRD <-> epics <-> architecture <-> UX <-> stories. Future dev agents and human team members read consistent specs. Mitigates the "future agent re-litigates the inconsistency" failure mode |
| **Stakeholder expectations & business value** | Unchanged MVP, improved detection methodology, same delivery shape |

### Trade-offs and alternatives considered

- **Defer the reconciliation** -- rejected. Drift compounds; future Claude sessions reading inconsistent docs would propose to "fix" the inconsistency repeatedly. The cost of one course-correction pass is much lower than re-litigating it across future sessions.
- **Hand off PRD edits to PM agent, architecture edits to Architect agent, UX edits to UX Designer agent** -- rejected. For a solo dev with a settled methodology decision, the off-domain edits are mechanical (terminology updates + FR rewording) and don't require domain expertise re-deliberation. SM proxied all edits with user (stwiertz) acting as the de-facto domain owner during Incremental review.

---

## Section 4: Detailed Change Proposals (Applied)

All edits below were reviewed and approved during the Incremental workflow on 2026-05-05 and have been applied to the files. The "Edit IDs" reference the proposal IDs used during the live review.

### 4.1 -- PRD edits (8 batches, all applied)

- **Edit 1.1** -- MVP Feature Set table: "Découpage écran noir + template matching" -> "Détection des transitions de jeu (game-state KDA/HSV) + identification de la carte (pHash)"; "Toggle POV/Minimap" -> "Toggle vue de clip ... Full / Minimap / Minimap+HUD"
- **Edit 1.2** -- Processing Pipeline table: replaced "Détection écran noir" + "Template matching" rows with "Game state detection (KDA/HSV)" + "Map identification (pHash)" + "Detection config (Firestore + MMKV)" rows
- **Edit 1.3** -- Dépendances Techniques: clarified OpenCV's role (HSV + pHash, not template matching); added Firestore entry
- **Edit 1.4** -- Risques & Mitigations: replaced "Template non reconnu" risk with "Carte non identifiée (pHash mismatch)" + "Detection config Firestore inaccessible" rows
- **Edit 1.5** -- Tech Stack: split "Template Matching" row into "Computer Vision (HSV + pHash)" + "Detection Config (Firestore)"
- **Edit 1.6** -- Must-Have Capabilities: descriptions updated to current methodology + 3-value toggle
- **Edit 1.7** -- Risk Mitigation Strategy: noted R&D 2026-04 validation
- **Edit 1.8** -- FR5, FR6, FR7 (text), FR14, FR15: rewritten to be methodology-agnostic where possible (behavior-focused) and reflect 3-value view-mode model

### 4.2 -- epics.md edits (10 batches, all applied)

- **Edit 2.1** -- Epic 2 summary description: detection methodology delegated to Epic 7; Epic 2 owns import/keyframes/segmentation/UX
- **Edit 2.2** -- Epic 2 detailed narrative: explicitly notes 2.3/2.4 superseded by 7.5
- **Edit 2.3** -- Story 2.3 entry: replaced with single-paragraph SUPERSEDED banner + pointer to [2.3.md](../stories/2.3.md)
- **Edit 2.4** -- Story 2.4 entry: replaced with single-paragraph SUPERSEDED banner + pointer to [2.4.md](../stories/2.4.md)
- **Edit 2.5** -- Story 2.5 entry: rewritten to consume Story 7.5 output (gameDetector + mapIdentifier)
- **Edit 2.6** -- Story 3.5 entry: replaced with single-paragraph SUPERSEDED banner pointing to Story 7.3
- **Edit 2.7** -- Epic 3 narrative: 3-value view-mode model
- **Edit 2.8** -- Epic 5 narrative: view-mode-aware export pipeline from Story 7.6
- **Edit 2.9** -- FR Coverage Map: 8 row updates (FR5, FR6 -> 7.5; FR14, FR15 -> 7.3; FR22-25 -> joint Epic 5 + Epic 7)
- **Edit 2.10** -- Epic 7 expansion: was a 3-line summary; now a full 6-story breakdown (Stories 7.1-7.6) appended after Epic 6, matching the format of Epics 1-6

### 4.3 -- architecture.md edits (10 batches, all applied)

- **Edit 3.1** -- Domains table: FR5-10 description rewritten
- **Edit 3.2** -- "OpenCV Integration" section renamed to "Detection Methodology (Game State + Map Identification)" and rewritten to describe HSV game detector + pHash map identifier + Firestore config + historical note about superseded approach
- **Edit 3.3** -- Implementation Sequence: 10 steps -> 12 steps (added detection config service step + detector implementation step + view-mode toggle step)
- **Edit 3.4** -- Project Directory Structure: removed `assets/images/map-templates/`; replaced `templateMatcher.ts` with `gameDetector.ts` + `mapIdentifier.ts` + `detectionConfig.ts` (and kept `blackScreenDetector.ts` as long-GOP fallback)
- **Edit 3.5** -- SQLite Schema: `view_mode CHECK(view_mode IN ('pov', 'minimap'))` -> `view_mode CHECK(view_mode IN ('full', 'minimap', 'minimap_hud'))`
- **Edit 3.6** -- Requirements to Structure Mapping: video-processing files updated to match new structure
- **Edit 3.7** -- Data Flow diagram: replaced black-screen+template flow with KDA/HSV + pHash flow, added DetectionConfig as upstream feed, added ViewModeToggle in playback flow
- **Edit 3.8** -- External Integrations: added Firestore entry for detection config
- **Edit 3.9** -- NFR1 coverage: profiled approach updated
- **Edit 3.10** -- Gap Analysis #3 (template assets): marked as resolved by methodology change

### 4.4 -- ux-design-specification.md edits (9 batches, all applied)

- **Edit 4.1** -- Effortless Interactions table: "Minimap toggle" row replaced with "View-mode toggle" describing 3-mode + sub-toggle
- **Edit 4.2** -- Design Implications row: tactical understanding now includes Minimap+HUD mode
- **Edit 4.3** -- Novel UX Patterns: "Full-screen minimap toggle" -> "Three-mode view toggle (Full / Minimap / Minimap+HUD)"
- **Edit 4.4** -- Spacing & Layout Foundation double-tap: cycle 3 modes
- **Edit 4.5** -- Cinema Mode Details controls list + double-tap: 3-mode cycling
- **Edit 4.6** -- Journey 1 narrative: view-mode cycle shortcut
- **Edit 4.7** -- Component Strategy -> Video Player Actions + Gestures: cycle view mode
- **Edit 4.8** -- Gestures table: cycle view mode
- **Edit 4.9** -- **NEW sub-section** "View Mode System (Full / Minimap / Minimap+HUD)" inserted in Component Strategy between Video Player and Timeline Scrubber -- consolidates the 3-mode model into a single explainer block

### 4.5 -- Story file edits (4 stories, all applied)

- **Edit 5.1** -- [Story 2.2](../stories/2.2.md): 3 edits (user story downstream consumers, supersession note in dev notes, testing approach seam)
- **Edit 5.2** -- [Story 2.5](../stories/2.5.md): major rewrite (status note, story narrative, 7 ACs, Tasks 1-2, Dev Notes algorithm + lobby + unknown-map handling, References block)
- **Edit 5.3** -- [Story 2.6](../stories/2.6.md): 1 dev note edit (performance target wording)
- **Edit 5.4** -- [Story 7.5](../stories/7.5.md): cosmetic file-path fix (`pipeline.ts` -> `processingPipeline.ts`)

### 4.6 -- Historical doc footnote (1 edit, applied)

- **Edit 6.1** -- [implementation-readiness-report-2026-02-02.md](implementation-readiness-report-2026-02-02.md): added dated footnote noting Epic 7 was inserted post-report (2026-04-20), with pointer to current source-of-truth artifacts; body intact

---

## Section 5: Implementation Handoff

### Scope Classification

**Moderate** -- backlog reorganization with cross-artifact propagation.

- Not Major (no fundamental product or architecture replan; methodology decision was settled 2026-04-20 via Proposals 4+6, not redeliberated here)
- Not Minor (touched PRD, architecture, UX, multiple owner domains)

### Ownership Model (As Executed)

| Edit Domain | Owner | Mode |
|---|---|---|
| Sprint backlog (sprint-status YAMLs, Story 2.3/2.4 banners, story file narratives) | **SM (Bob)** | Direct edit during workflow (option a) |
| PRD FR wording + sections | **PM-domain** | SM proxied edits inline; user (stwiertz) approved as de-facto PM during Incremental review |
| Architecture detailed updates (SQLite CHECK, project structure, OpenCV Integration -> Detection Methodology) | **Architect-domain** | SM proxied edits inline; user approved as de-facto Architect |
| UX terminology refresh + new View Mode System sub-section | **UX Designer-domain** | SM proxied edits inline; user approved as de-facto UX Designer |
| Historical readiness-report footnote | **SM** | Direct edit |

### Success Criteria (As Verified)

| Criterion | Status |
|---|---|
| Every reference to "black screen detection" or "template matching" in canonical planning artifacts either describes the new methodology accurately or is explicitly marked historical/superseded | ✓ |
| SQLite `view_mode` CHECK constraint reflects 3-value model in architecture.md schema | ✓ |
| FR Coverage Map maps every FR to its current owning story | ✓ |
| A dev agent reading any single artifact in isolation gets a coherent picture of the current methodology | ✓ |
| In-progress Story 2.2 is unblocked | ✓ (no changes to Story 2.2's tasks/ACs that affect implementation) |

### Next Steps

| # | Action | Owner | When |
|---|---|---|---|
| 1 | Continue Story 2.2 to review (device-side smoke tests, RAM measurement) per existing handoff plan in [2.2.md](../stories/2.2.md) | Dev (Amelia or stwiertz) | When Android device available |
| 2 | When Story 2.2 reaches `done`, pick up Sprint 2.5 stories per the dependency graph in [docs/sprint-status.yaml](sprint-status.yaml): start with 7.4 (remote config) since it's a no-op shim until 7.5 lands; 7.1+7.2 can ship as same PR; 7.5 then 2.5 | SM + Dev | After Story 2.2 done |
| 3 | After Sprint 2.5 lands, resume Sprint 2 closure with Stories 2.5 and 2.6 (now consuming 7.5 detectors) | Dev | After 7.5 done |
| 4 | Optional follow-up: ultra-review the rewritten Epic 7 in [epics.md](epics.md) once Story 7.5 lands and the implementation reveals any AC tweaks | SM | After 7.5 review |

### Deliverables Produced (This Workflow)

- ✅ Sprint Change Proposal document (this file)
- ✅ All 6 artifacts updated inline with reviewer-approved edits (~50 individual edits across PRD, epics, architecture, UX, 4 story files, 1 historical doc)
- ✅ Sprint-status YAMLs already reflect epic-level changes (updated earlier in session, pre-workflow)
- ✅ Implementation handoff plan (this section)

---

## Appendix: Workflow Audit Trail

| Step | Status | Notes |
|---|---|---|
| Step 1: Initialize Change Navigation | ✓ Complete | Trigger confirmed as discovery-driven (R&D revealed better methodology); mode = Incremental |
| Step 0.5: Discover and load project documents | ✓ Complete | Loaded 4 planning artifacts (no tech-spec, no project-context.md) |
| Step 2: Execute Change Analysis Checklist | ✓ Complete | All 6 sections of the checklist passed; no halt conditions triggered |
| Step 3: Draft Specific Change Proposals | ✓ Complete | 6 artifacts processed in incremental mode; user approved each batch |
| Step 4: Generate Sprint Change Proposal | ✓ Complete | This document |
| Step 5: Finalize and Route for Implementation | (next) | Awaiting final user ack |
| Step 6: Workflow Completion | (next) | Summary report |
