---
title: "Sprint Change Proposal — Engine-First Pivot: GPU Mega-Shader Detection POC"
date: "2026-07-16"
author: "Stephane"
facilitator: "Claude Opus 4.8 (/bmad-correct-course)"
status: "approved"
scope_classification: "Moderate — backlog reorganization + artifact amendments; PRD MVP scope unaffected"
supersedes: "nothing"
amends:
  - _bmad-output/epics-and-stories.md
  - _bmad-output/architecture.md
  - _bmad-output/prd.md
  - _bmad-output/sprint-status.yaml
source_brief: "Brief — Moteur d'Analyse Vidéo Warden (POC, engine-first), supplied by Stephane 2026-07-16"
---

# Sprint Change Proposal — Engine-First Pivot: GPU Mega-Shader Detection POC

## Section 1 — Issue Summary

### Problem statement

Warden's V1 detection path is planned as a CPU pipeline (FFmpeg I-frame extract → OpenCV via JSI → pHash map identification, latterly re-cut to ROI/HSV `cv2.inRange` zone matching). Three independent problems converge on it:

1. **The performance ceiling is unacceptable and the approach is the ceiling.** PERF-002 budgets auto-slice at ≤5% of source duration — 4 minutes for a 1h20 session (`epics-and-stories.md:241`). Stephane's assessment is that this is unacceptable UX and that the per-frame CPU `cv2.inRange` path cannot reach the target under any amount of tuning. The proposed engine targets < 10 s for the same input — a ~24× improvement, which is an approach change, not an optimization.

2. **V1 currently plans to ship auto-slice that does not fire.** The posture on record:

   > **post-V1** — V1 ships with the legacy v1 `map_config.json` in place but bypassed by the new-HUD detection chain (mobile consumers `gameDetector.ts` / `mapIdentifier.ts` continue reading v1 pHash data, which won't fire on HUD 2.0 footage; **auto-slice produces `unknown` map labels on HUD 2.0 sessions until the consumer rewrite ships post-V1**). — `epics-and-stories.md:2748`

   And the story that would close it does not exist:

   > **Mobile consumer rewrite (out of all three sub-stories' scope):** … **The TS rewrite to read v2 ROI/HSV-band data is a separate post-V1 story (TBD; not yet enumerated in any epic).** — `epics-and-stories.md:2750`

   This is not a pivot away from something working. It is a pivot away from something with an unenumerated hole where its V1 payload should be.

3. **Development sequencing is UI-first over an unproven engine.** In Stephane's words: *"oui UI c'est sympa ça donne une idée de ce qu'on aura à la fin mais ça ralentit le dev de ce que fait réellement l'app, et engine-first je pourrais surtout target le debug jusqu'à avoir l'engine que je veux."* Epics 5/6/7 comprise ~20 stories of mobile review UI sitting directly on auto-slice output — scheduled ahead of both the engine that produces that output and the consumer rewrite that would deliver it.

**Issue categories:** technical limitation discovered · failed approach requiring different solution · strategic pivot (sequencing).

### The proposed engine (source brief, condensed)

- Keyframe-only decode (`ffmpeg -skip_frame nokey`), piped to RAM, no disk write.
- One **mega-shader**: ~150 pixel/HSV rules tested in parallel from a data-texture LUT (150×3 — position + HSV + V), output to a 150×1 FBO, one 0/1 score per rule.
- **CPU-side** scoring and phase resolution; no combination logic in GLSL.
- **"Doubt"** is a valid classification outcome, resolved by the reliability of surrounding transition screens — stream processing, no sliding window, no two-pass.
- 3-keyframe circular buffer for retroactive thumbnail capture (frame N-2 on a phase change at N).
- Two sequential POCs: **PC** (Python + ModernGL + FFmpeg), then **Android** (Kotlin + MediaCodec + GLES 3.0).

### Evidence gathered during analysis

**The pivot is charter-compliant.** The only absolute prohibition in the architecture is cloud CV (`architecture.md:858` — *"FORBIDDEN — fall back to cloud CV / NEVER"*). A GPU shader is on-device: **[INVARIANT 3]** (`architecture.md:1239-1242`) is satisfied and Innovation #1's privacy + marginal-cost claim is preserved intact.

**GPU is a greenfield surface.** `GPU`, `GLES`, `OpenGL`, `shader`, `GLSL`, `ModernGL`, `EGL`, `FBO`, `MediaCodec` appear **nowhere** in `architecture.md`. The single token "GPU" occurs at `architecture.md:294` — a rejected-alternative footnote about the *Dear PyGui* diagnostic GUI toolkit requiring a GPU. It concerns a GUI library, not a compute engine, and must not be cited as prior art either way. Consequence: there is **no prior decision to overturn**, and equally **none authorizing it** — every GPU element needs a new decision entry.

**The schema already anticipated an engine swap.** Story 9.9c defined `schema_version` as **"config-shape version, NOT the detection-method version"** (`epics-and-stories.md:2624`, `:2777`). A detection-engine change does not, by the schema's own charter, force a version bump.

**Volet B of the source brief is ~80% already shipped.** Story 9.12 (Unified Zone Picker, `done`, merge `54724ed`) already delivers: reference-image loading, manual HSV margin entry (`image_inspector/modes.py:101-131`), a pass/fail readout, direct JSON export with merge-safe 4-fragment writes plus emitter round-trip validation (`zone_picker/app.py:432-444`), multi-zone-per-phase grouping with weights, and Welford/circular-hue auto-seeding that **already only writes the entry boxes** — `_add_zone` reads whatever the operator typed (`zone_picker/app.py:340`), so the brief's "manual margins, no auto-recompute" requirement needs **zero code change**.

**The brief's normalized-coordinate concern (§3.5) is already solved.** The schema stores absolute integer pixels at a fixed `reference_resolution` of 1920×1080 (`contracts/map-config.schema.json:23-32`), and every tool `_resize_to_ref`s before reading (`zone_picker/app.py:59-65`; `roi_detection_tester.py:498-505`; `video_test.py:839`). A fixed denominator *is* normalization.

**The rule-shape decision has no performance justification.** Worked through: 1h20 at GOP 2s ≈ 2400 keyframes; a <10 s target ≈ 4.2 ms/keyframe. Per frame: I-frame decode ≈ 1–3 ms; 6.2 MB texture upload ≈ 0.6 ms; the shader at 150 rules × 400 texels ≈ 60k fetches ≈ 0.01–0.02 ms. **The shader is ~0.2 % of the budget either way — the < 10 s target is decode-bound, not shader-bound.** Points would have cost a `schema_version` bump plus rewrites of `map_config_emitter.py`, `roi_detection_tester.py` and `video_test.py` (the only live REL-006 enforcement), and would have discarded `min_ratio` — the per-rule defense against exactly the compression/lighting variance the brief's §3.1 names as its reason for score-based matching. **Decision: rects retained. A rect with `w=1, h=1` is a point; the shipped schema already expresses it.**

---

## Section 2 — Impact Analysis

### Epic impact

| Epic | Status | Impact |
|---|---|---|
| **Epic 12** *(NEW)* | — | Created. Holds the whole engine question and its verdict. |
| **Epic 9** — Tooling / New-HUD detection chain | `in-progress` | **Charter Amendment #3.** 9.9b + 9.10 blocked on the verdict; 9.15 + 9.16 added. Cannot close while 9.9b/9.10 are open. |
| **Epic 1** — Foundations | `in-progress` | Goal de-mechanized; Story 1.1's binding verdict superseded (frozen, not re-opened); spike gate re-points to 12.3; Story 1.13 annotated. Firebase/contracts work untouched. |
| **Epics 5 / 6 / 7** — Card View+Cinema / Clips+voice+export / Auto-save | `backlog` | **Held behind 12.3 + 12.4** (~20 UI stories). Order change only — no status change (see §4). |
| **Epics 2 / 3 / 4 / 8** | `backlog` | **Unaffected.** Engine-independent (telemetry, entitlement, web UI, i18n). Float freely. |
| **Epic 10** — V1 launch | `backlog` | Unaffected; still last. |
| **Epic 11** — post-V1 GUI | `backlog` | Unaffected. |

### Story impact

**Invalidated as scoped (held, not cancelled):**

- **9.9b — Iterative Zone Population** (`ready-for-dev`, fully unblocked as of 9.14 landing). Its 8-pass measure-and-adjust loop is wired to a specific toolchain (zone_picker → emitter → video_test/Tool 9) and to a CPU `cv2.inRange` fire model. The **zone data survives** an engine swap; the loop's tooling contract does not. At ~1.5 weeks per HUD version, this is the single most expensive collision — and it is the work most exposed to being spent before the engine that consumes it is proven.
- **9.10 — PRD/Architecture Editorial Pass.** Exists to rewrite pHash-era prose *into* ROI/HSV-pivot prose, with Cohort B citing 9.9b's measured floors. A third engine changes the destination again. Its own AC0 rationale — *"hold to avoid editing the same paragraphs twice"* — now applies a third time.

**Retroactively superseded (frozen, audit trail preserved):**

- **1.1 / AR-SPIKE** (`done`). Validated `react-native-fast-opencv` JSI as *the* mechanism (`epics-and-stories.md:748`) and set the ladder rungs from that binding's numbers (`:756`). A MediaCodec + GLES 3.0 path is a different binding. Mitigating: the measurement follow-up 1.1.1 was already cancelled in favour of ship-and-observe (2026-05-09), and the FORBIDDEN cloud-fallback outcome (`:757`) is unaffected.

**Architecture-invalidated at the frame-source layer (already merged; loss is sunk, not prospective):**

- **9.13 — Video Detection Tester** (`done`). Deliberately uses stride-sampled `cv2.VideoCapture`, **not** codec keyframes, because *"true codec-keyframe isolation needs a forbidden new dep"* was recorded as a disaster-prevention finding. **The proposed `-skip_frame nokey` decode is exactly what 9.13 was forbidden from doing.** Its `results.json` shape and `{in_match → score_screen → not_in_match}` state machine survive; the decode path and CPU classifier do not.
- **9.14 — Tool 9 Refit** (`done`). CPU `cv2.inRange` classifiers. Ground-truth derivation and report schema survive; the prediction engine is replaced. **9.14 is also the accuracy instrument 9.9b depends on** — see the REL-006 gap below.

**Reusable as-is — the preserved assets:**

- **9.5 — Video Timeline Labeler (Tool 6).** Fully reusable, untouched. A labeled-PNG ground-truth corpus is engine-agnostic. Explicitly protected across the last re-cut (`epics-and-stories.md:2626`, `:2797`). **The most valuable preserved asset.**
- **9.12 — Unified Zone Picker (Tool 10).** High leverage. Emits exactly the tuple a LUT row needs, and already ships circular-hue/hue-wrap math ported verbatim from `overlay_stack_analyzer@ba6b326` + `auto_roi_discoverer.derive_band_for_rect`. **The shader's hue-wraparound requirement is already solved on the authoring side.** Its three modes (HUD-version / in-match / per-map) map 1:1 onto rule categories. Precedent for logic-survives-engine-swap is already on record at `epics-and-stories.md:3215` (Epic 11 C7).
- **9.11 — Retire Legacy Tooling.** Beneficial as-is; `tools/common/{labels,zones,labeled_dataset}.py` is the engine-agnostic substrate CPU-side scoring still leans on.
- **9.9c — Schema Unification.** The pivot's best friend (see the `schema_version` finding above). `score_screen_duration_ms` and the binary `in_match` collapse are engine-agnostic modelling wins inherited for free.

### Artifact conflicts

**`architecture.md` — 7 amendments** (detail in §4). Severity-ordered: the pre-PRD spike (gates all Sprint 3 mobile scope), the un-armed fallback ladder, the iOS cross-platform assertion, Brownfield Item 6's rationale, Decision #2's moat framing, REL-006's instrument, and a new 5th-native-module decision.

**`prd.md` — 5 amendments** (detail in §4). All de-mechanize the same way. **MVP scope, personas, journeys, entitlement state machine and business targets are untouched** — this is what keeps the change Moderate rather than Major.

**Unaffected, verified:** `ux-design.md` (no detection-engine surface; J3's graceful-degradation flows are engine-agnostic and the "doubt" state maps onto the existing `unknown` fallback), Decisions #1/#3/#6/#9 (entitlement/Stripe/web-side), Brownfield Items 1/2/5, Decision #7 (`firestore.rules` — payload-agnostic), **Brownfield Item 7** (`schema_version: 1` survives — no bump).

### Technical impact

- **New dependency class.** `moderngl` + FFmpeg-as-decoder. Two manifests to update (`apps/tooling/pyproject.toml` + `requirements.txt`). This breaks two live norms: every recent Epic 9 story carried an explicit "no new deps" constraint, and 9.13 recorded the keyframe-dep question as a disaster-prevention item. **Must be a recorded decision in Story 12.1, not a silent drift.**
- **Fifth native module on mobile.** `architecture.md:2178` enumerates exactly four (FFmpeg, OpenCV, MMKV, SQLite), accessed only via `shared/services/*.ts`. GLES/MediaCodec is a fifth; needs a SEC-007 allowlist entry (`architecture.md:122`).
- **Reference device.** Only the Poco X5 Pro 5G (SM7325/A14, Adreno 619, GLES 3.2-capable) can bind PERF-010. **A desktop GPU proves feasibility, never the mobile budget.**
- **In-charter placement.** `apps/tooling` is chartered as *"a lab, not a runtime dependency"* (`architecture.md:432`, `:1016`) — a Python POC is squarely in-charter. Spike reports have an established home: `_bmad-output/architecture-spike-<topic>.md` (`architecture.md:1040`, `:860`).
- **Conventions the POC inherits:** Python ≥3.11 · uv workspace · **argparse, not Typer/click** (`architecture.md:281`) · `run()` + `main()` entry pattern (`:990`) · `tools/<tool>.py` or `tools/<tool>/` package (`:1015`) · pytest at `apps/tooling/tests/` · outputs to `apps/tooling/output/<video_stem>/` (`:1034`) · Conventional Commits, scope `tooling` (`:1277-1280`).
- **Friction to name:** `architecture.md:1136` prescribes *"stateless pure functions (np in → np out)"* for shared utils. A persistent GL context is stateful. Isolate it behind a `run()`-shaped seam.

---

## Section 3 — Recommended Approach

**Selected path: Hybrid — Direct Adjustment + gated spike (checklist Option 1), with an explicit sequencing change.**

- **Option 2 (Rollback): NOT VIABLE and not needed.** Nothing merged needs reverting. 9.11's deletions help the pivot; 9.5/9.12's outputs are engine-agnostic assets; 9.13/9.14's losses are partial (logic layers port) and already sunk.
- **Option 3 (PRD MVP Review): NOT VIABLE — and deliberately avoided.** The MVP definition survives. Escalating to a PRD MVP change would require PM/Architect handoff and would reopen scope that is not in question. Rejected in favour of the gated spike.
- **Option 1 (Direct Adjustment): VIABLE — selected.** Effort: Medium. Risk: Low.

### Rationale

**Gate, don't commit.** The POC binds the engine with measured evidence *before* the expensive, irreversible bets are placed. If the shader disappoints, 9.9b resumes with ~1.5 wk/HUD of work unspent and four merged Epic 9 stories still valid. The reversibility is the point.

**Sequence the cheap de-risk first.** Story 9.15's pilot zone set (hours, via the already-shipped Tool 10) both unblocks the POC *and* pilots 9.9b's 8-pass loop end-to-end on a small sample. A broken loop surfaces in an afternoon rather than on pass 6 of 8.

**Preserve the accuracy gate.** Story 9.16 re-points Tool 9/13 at the bound engine, which downgrades 9.9b from "invalidated" to "mechanism-swapped" and keeps the entire measurement apparatus alive across the pivot.

**Engine-first is a dev-focus decision, stated plainly.** Epics 5/6/7 do not *strictly* depend on the engine — the app supports manual clips and J3 explicitly designs for graceful degradation. This hold is a focus decision, not a dependency-driven one. It is recorded as such so a future reader who checks the dependency graph is not misled. What it buys: the `:2750` hole gets enumerated and built **before** ~20 stories of UI are built on top of it, instead of V1 shipping `:2748`'s *"`unknown` map labels on HUD 2.0 sessions."*

### Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Shader engine underdelivers; pivot rejected | Medium | The gate. 9.9b/9.10 held, not cancelled — resume cost ≈ 0. |
| GLES 3.0 subset incompatibility found late (at 12.2) | Medium | GLSL written in the ES-3.0-compatible subset from line one is a **12.1 AC**, making 12.2 a port not a rewrite. |
| PC POC numbers mistaken for mobile numbers | **High** | Explicit: only 12.2 on the Poco X5 Pro binds PERF-010. Written into 12.1's and 12.3's scope. |
| REL-006 loses all enforcement during the pivot | **High** | Story 9.16, sequenced with 12.3. Called out as non-optional. |
| iOS Phase 2 silently becomes a refactor | Medium | Amendment 5c makes the cost explicit and deferred to V3, rather than letting a false assertion rot. |
| New-dep norm broken silently | Low | Recorded decision in 12.1. |
| Third Epic 9 re-cut compounds frozen prose strata | Low | 9.10's widened scope + the housekeeping reconciliation in this SCP. |

### Timeline impact

V1 launch date is not bound at brief level and none is committed. The critical path lengthens by 12.1 + 12.2 + 12.3 and shortens by whatever 9.9b would have spent populating zones against an engine that may not ship. Epics 2/3/4/8 continue in parallel and absorb schedule.

---

## Section 4 — Detailed Change Proposals

### 4.1 Epics & Stories (`_bmad-output/epics-and-stories.md`)

#### NEW — Epic 12: Detection Engine — GPU Mega-Shader POC (V1-GATING)

> **Goal:** Bind whether a keyframe-only FFmpeg → GPU mega-shader engine can replace the CPU OpenCV/pHash/`cv2.inRange` detection path, with measured evidence, **before** any further zone-population or mobile-UI investment.

| Story | Scope | Fit |
|---|---|---|
| **12.1 — PC POC: Python + ModernGL + FFmpeg keyframe bench** | Volet A of the brief. Lives in `apps/tooling/tools/<name>/`. Consumes the **shipped unified `map_config.<hud>.json` unchanged**. Reuses Tool 6's labeled corpus + Tool 9 as accuracy gate. Reports ms/keyframe + accuracy vs the CPU baseline. **ACs must include:** GLSL restricted to the ES-3.0-compatible subset; an explicit recorded new-dep decision (`moderngl`, FFmpeg-as-decoder); hue-wraparound handling (`H_min > H_max` crosses 0.0/1.0); the "doubt" state as a first-class outcome; 3-keyframe circular buffer; RAM pipe, no disk write. | `needs-spike-or-split` |
| **12.2 — Android POC: Kotlin + MediaCodec + GLES 3.0 port** | Gated on 12.1. Same GLSL source of truth. Runs on the **Poco X5 Pro 5G** — the only thing that can bind a real mobile number. | `needs-spike-or-split` |
| **12.3 — Engine verdict + PERF-002 re-baseline + ladder re-arm** | **THE GATE.** Publishes `_bmad-output/architecture-spike-gpu-megashader.md`. Binds the engine; re-baselines PERF-002 from measured numbers; **re-arms the Innovation #1 fallback ladder** with engine-agnostic triggers. | `fits-in-one-sprint` |
| **12.4 — Mobile detection consumer rewrite** | Conditional on 12.3. Closes the `:2750` hole. Unblocks Epics 5/6/7. | TBD at create-story |

- **Dependencies:** Epic 1 (`in-progress`) — no hard blocker; 12.1 starts after 9.15.
- **Downstream:** Epic 9 (9.9b/9.10/9.16), Epics 5/6/7.
- **Estimation note:** 12.1 and 12.2 are `needs-spike-or-split`. Story 1.1 is currently *"the only `needs-spike-or-split` story by design"* (`:684`) — this is a deliberate, citable exception per Decision #ES-9.
- Add Epic 12 to the Epic List; total epics 11 → 12.

#### Epic 9 — Charter Amendment #3 (2026-07-16)

Amendment block at the epic head, matching the 2026-05-14 (`:2620`) and 2026-05-15 (`:2622`) precedent.

| Story | From | To | Rationale |
|---|---|---|---|
| **9.15 — Pilot zone set for engine POC** *(NEW)* | — | `ready-for-dev` | Minimal population (2–3 maps + HUD + in_match) via the shipped Tool 10. Unblocks 12.1 **and** pilots 9.9b's loop on a small sample. Hours, not weeks. |
| **9.9b — Iterative Zone Population** | `ready-for-dev` | `blocked` on 12.3 | Full 8-map population. Mechanism wired to CPU `cv2.inRange`; ~1.5 wk/HUD not spent before the engine is bound. (`blocked` precedent: Story 1.9.) |
| **9.10 — PRD/Architecture Editorial Pass** | `ready-for-dev` | `blocked` on 12.3, **scope widened** | Widened to scrub pHash→shader prose and to reconcile the stale statuses below. Its own AC0 rationale applies a third time. |
| **9.16 — Re-point detection testers at bound engine** *(NEW)* | — | `backlog`, conditional on 12.3 | Re-points Tool 9 (`roi_detection_tester.py`) + Tool 13 (`video_test.py`) at the bound engine. **Non-optional** — see below. |

**Why 9.16 is not optional.** The ≥95 % map-ID floor is stated in REL-006 (`:268`) and inherited everywhere, but **every story that ever enforced it numerically is dead**: 9.2 cancelled (`:2653`), 9.3 cancelled (`:2677`), 1.1.1's measurement cancelled, 9.9b unstarted. The only live per-classifier numeric enforcement is 9.9b's AC set, measured by Tool 9 (Story 9.14). Without 9.16 the pivot has **no accuracy gate at all**.

**Housekeeping folded into this SCP** (the pivot would otherwise freeze it):
- Epic file lists 9.9c / 9.11 / 9.12 / 9.13 / 9.14 as `backlog` — **all five are `done` on main** (`:2776`, `:2781`, `:2786`, `:2791`, `:2796` vs `sprint-status.yaml:209-213`).
- 9.5 reads `done` in the epic file (`:2720`) but `review` in the yaml (`:201`).
- 9.9a is `review` + SUPERSEDED (`:2758`), dangling without its Two-PR flip.
- The Epic List entry (`:647-654`) is entirely pre-pivot — still describes *"hash generation"*, `warden_analyzer` as *"the load-bearing remaining tooling work"*, and *"4 awaiting-hash maps"*.

#### Epic 1 — amendments

**1a — Goal statement** (`:570`, `:738`):

```
OLD  "...a foundation where the OpenCV JSI binding is real
      (or the V2 deferral is decided)..."

NEW  "...a foundation where the on-device detection engine is bound
      by measured evidence (Epic 12), or its V2 deferral is decided..."
```
*Rationale:* the outcome is right; only the named mechanism is stale.

**1b — Story 1.1 / AR-SPIKE** (`done`) — add supersession note, **do NOT re-open**:

> *"Binding-viability verdict superseded by Story 12.3 for the shader engine; the rung-0 verdict remains the record for the JSI path."*

*Rationale:* per 9.10's FROZEN-block discipline, editing a completed spike destroys the audit trail. 12.3 supersedes; 1.1 records.

**1c — `cross-AUTO-SLICE-001/002` "(spike-gated)"** (`:571`) — gate re-points Story 1.1 → Story 12.3.

**1d — Story 1.13** (`backlog`) — annotate, do not restructure. **No schema change needed** (rects retained). Now transitively blocked (it bundles a config 9.9b populates). Note: create-story waits for 12.3 + 9.9b and **resolves both open forks in one pass** — the engine question and the pre-existing per-HUD-files-vs-manifest fork (`:1005`).

#### Engine-first resequencing

- **Epics 5 / 6 / 7 held behind 12.3 + 12.4.** Recorded as a sequencing note in the Epic List. **No status change** — they are already `backlog`, and `blocked` is not a defined epic status (only stories use it; Story 1.9 is the precedent). Order lives in the epics doc.
- **Epics 2 / 3 / 4 / 8 float.** Epic 4 is *web* UI and never touches the engine.
- **Stated plainly in-document:** this is a dev-focus decision, not a dependency-driven one.

### 4.2 Architecture (`_bmad-output/architecture.md`)

| # | Target | Change |
|---|---|---|
| **5a** | Pre-PRD spike `:832-868` | Scope is literally *"build a real OpenCV JSI binding using `react-native-fast-opencv`"*. Re-point: **superseded by Epic 12 for the shader path**; JSI verdict preserved as the record for the JSI path. **Highest severity — gates all Sprint 3 mobile scope** (`:862`, `:908`, `:2184`). Cascades: `:80-87`, `:2084`, `:2091`, `:2113`. |
| **5b** | Fallback ladder `:852-858` | Every rung is CPU/JSI-phrased; rung-3's trigger *"JSI binding does not ship"* (`:857`) is **unreachable** under a shader engine — the auto-slice V1 safety net is **currently un-armed**. Re-arm with engine-agnostic triggers. **`:858` FORBIDDEN cloud fallback stays verbatim.** Cascades: `:2037`, `:2161`. |
| **5c** | iOS assertion `:884` | *"No Android-only patterns introduced. iOS Phase 2 work is glue — not refactor."* → **false** once 12.2 lands. Amend to name MediaCodec + GLES 3.0 as an Android-only pattern carrying an iOS (VideoToolbox/Metal) refactor cost, deferred to V3. |
| **5d** | Brownfield Item 6 `:810-813`, `:2035` | FGS rationale rests entirely on *"the FFmpeg/OpenCV JSI bindings cannot be shared across the headless context boundary"*. EGL contexts are **thread**-bound, not JSI-context-bound. Decision likely lands the same; **rationale must be re-derived**. Note `:811` warns of a *"fundamental redesign of the processing pipeline"* — precisely what is proposed. |
| **5e** | Decision #2 framing `:383`, `:386` | Delivery mechanism survives unchanged. The **public privacy sentence** literally says *"the config that says **'this hash means horizon'**"* — restate in zone/HSV terms. It is the sentence that defends the privacy contract. |
| **5f** | REL-006 instrument `:120`, `:847`, `:2064` | `hash_validator.py` measures **Hamming distance**; it cannot measure a shader, yet it is the named gate *"before any new `map_config.json` ships"*. Re-point to Tool 9 per Story 9.16. |
| **5g** | Native modules `:2178` *(NEW decision)* | Doc enumerates **exactly four**. GLES/MediaCodec is a **fifth** — new decision entry + SEC-007 allowlist entry (`:122`). Greenfield: no GPU/GLES/shader/ModernGL mention exists anywhere in the document. |

**Explicitly NOT amended:** Brownfield Item 7 (`:487-495`) — `schema_version: 1` survives; rects retained and 9.9c defined the field as config-shape-not-detection-method.

### 4.3 PRD (`_bmad-output/prd.md`)

| Target | Change |
|---|---|
| `:105`, `:115`, `:155`, `:199` | *"The OpenCV JSI binding is the load-bearing V1 milestone"* → *"The on-device detection engine (bound by Epic 12) is the load-bearing V1 milestone."* **Innovation #3's privacy + marginal-cost claim is unaffected** — still on-device, still zero per-match infrastructure cost. |
| `mobile-AUTO-SLICE-002` (`epics-and-stories.md:103`) | *"using on-device **perceptual hashing**"* → *"using on-device map identification against `map_config`."* Mechanism was baked into FR text; already stale from the ROI/HSV pivot. |
| **PERF-002** (≤5 % / 4 min) | **Re-baseline pending 12.3's measured numbers.** Already a soft ship-and-observe target since 2026-05-09 — consistent, not a new concession. **< 10 s is recorded as the aspiration, not an AC.** |
| **PERF-010** (TBD) | Still TBD; binding gate re-points Story 1.1 → Story 12.3. **Only the 12.2 Poco X5 Pro run can bind it.** |
| **REL-006** (`:268`) | Floors unchanged (≥95 % map ID). Instrument → Tool 9. *Below-floor = graceful degradation, not blocking error* stays — and pairs naturally with the brief's **"doubt"** state, which is the same escape hatch promoted into the engine. |

**Not touched:** MVP scope, personas, journeys, entitlement state machine, business targets.

### 4.4 Sprint status (`_bmad-output/sprint-status.yaml`)

```yaml
  epic-9: in-progress
  9-9b-iterative-zone-population-for-shipping-configs:  ready-for-dev → blocked   # on 12.3
  9-10-prd-architecture-editorial-pass-roi-hsv-pivot:   ready-for-dev → blocked   # on 12.3, scope widened
  9-15-pilot-zone-set-for-engine-poc:                   ready-for-dev             # NEW
  9-16-re-point-detection-testers-at-bound-engine:      backlog                   # NEW, conditional on 12.3

  epic-12: backlog                                                                # NEW
  12-1-pc-poc-gpu-megashader-bench:                     backlog
  12-2-android-poc-gles-port:                           backlog                   # gated on 12.1
  12-3-engine-verdict-and-perf-rebaseline:              backlog                   # THE GATE
  12-4-mobile-detection-consumer-rewrite:               backlog                   # conditional on 12.3
  epic-12-retrospective: optional

  # epic-5/6/7 stay `backlog` — held behind 12.3 + 12.4 per SCP 2026-07-16 (engine-first).
```
Plus a `last_updated` header entry recording this SCP.

### 4.5 Source-brief open questions — resolved

The brief's §5 asked four questions to be settled at sprint start. All four are answered by shipped work:

| # | Question | Resolution |
|---|---|---|
| **1** | Volet B — extension of Master Config, or standalone throwaway? | **Neither — it is ~80 % already shipped as Tool 10** (Story 9.12, `done`). Residual work is three small additions: wire the already-written-but-unhooked `ColorPickerMode` (`zone_picker/modes.py:90-91` stubs it as a no-op), expose `min_ratio` in `read_band` (`zone_picker/modes.py:137` hardcodes 0.3), add a single-frame/video-frame input mode. Folded into 9.15/12.1 as needed — **no new tool.** |
| **2** | Multiple points per phase from the start, and with what JSON grouping? | **Already shipped.** `minimap_identification.maps.<slug>.zones[]` (`contracts/map-config.schema.json:71-78`, `:140-151`); `hud_version_detection` and `in_match_detection` are flat `Zone[]` (`:43-52`). Per-zone `weight` + `weight_override`; per-map score is a weighted aggregate (`roi_detection_tester.py:742-748`). |
| **3** | A flag for re-ingesting labeled frames to recompute margins later? | **Already shipped and already bypassable.** `zone_picker/variance.py:152-199` (`derive_band_for_rect`, Welford + circular hue) auto-seeds the entry boxes; `_add_zone` reads whatever the operator typed (`app.py:340`). Manual-only entry needs **zero code change**; statistical re-ingest is available when wanted. No flag needed. |
| **4** | Exact confidence threshold for the "doubt" state? | **The field exists:** `identification_threshold` (`contracts/map-config.schema.json:64-69`, default 0.6), consumed by Tool 9 (`roi_detection_tester.py:425`) and Tool 13 (`video_test.py:310-317`), both CLI-overridable. **The value stays experimental** — set from real captures during 12.1, per the brief's own instruction. |

Additionally resolved: **brief §3.5 (normalized coordinates)** — already solved by `reference_resolution` + `_resize_to_ref`; a fixed 1920×1080 denominator *is* normalization. `x_pct`/`y_pct` would be a schema break for zero gain.

**One divergence to carry into 12.1:** the picker's live preview normalizes (`fired/total`, `app.py:316-324`) while Tool 9 sums raw weighted (`roi_detection_tester.py:742-748`). The picker's ✓/✗ is therefore **not numerically identical** to Tool 9's verdict. Worth reconciling or documenting during the POC.

---

## Section 5 — Implementation Handoff

**Scope classification: MODERATE** — backlog reorganization + artifact amendments. Not Minor (it creates an epic, resequences three, and amends three planning artifacts). Not Major (**the PRD's MVP definition survives**; no fundamental replan; no PM/Architect escalation required).

### Handoff

| Recipient | Responsibility | Deliverables |
|---|---|---|
| **Developer / PO (Amelia)** | Apply §4.1 and §4.4 — Epic 12 creation, Epic 9 Amendment #3, Epic 1 amendments, resequencing note, sprint-status flips + housekeeping reconciliation. | Amended `epics-and-stories.md` + `sprint-status.yaml` |
| **Developer / PO** | Apply §4.2 and §4.3 — the 7 architecture + 5 PRD amendments. May be folded into Story 9.10's widened scope **if** the ladder re-arm (5b) and REL-006 instrument (5f) are pulled forward — those two cannot wait, since they leave live gaps. | Amended `architecture.md` + `prd.md` |
| **Developer (Amelia)** | `/bmad-create-story 9.15`, then `/bmad-create-story 12.1`. | Story files with full ACs + Dev Notes |
| **Stephane** | The 12.3 verdict decision. Supplies the reference EVA captures (real V2 captures already at monorepo-root `videos/V2`) and the Poco X5 Pro 5G for 12.2. | Bound engine decision |

### Sequencing

```
  9.15 pilot zones ──▶ 12.1 PC POC ──▶ 12.2 Android POC ──▶ 12.3 VERDICT
    (hours, Tool 10)     (Volet A)      (Poco X5 Pro)          │
                                                               ├──▶ 9.16 re-point Tool 9/13
                                                               ├──▶ 9.9b resume or re-scope
                                                               ├──▶ 9.10 unblock (retargeted)
                                                               ├──▶ 1.13 create-story
                                                               └──▶ 12.4 consumer rewrite
                                                                        └──▶ Epics 5/6/7

  Epics 2/3/4/8 — float in parallel throughout
```

### Success criteria

1. **12.1 reports measured ms/keyframe and accuracy against the CPU baseline**, on the shipped schema, using Tool 6's labeled corpus and Tool 9 as gate — feasibility proven or refuted on evidence, not intuition.
2. **12.2 reports a real Poco X5 Pro 5G number.** No PC number is ever cited as a mobile number.
3. **12.3 publishes `architecture-spike-gpu-megashader.md`**, binds the engine, re-baselines PERF-002, and **re-arms the fallback ladder** — after which the auto-slice FRs have a V1 safety net again.
4. **REL-006 never loses enforcement** — 9.16 lands with or before any engine swap.
5. **If the verdict rejects the shader**, 9.9b/9.10 unblock unchanged and ~1.5 wk/HUD was never spent. *The reversibility is the deliverable.*

### Delivery pattern

Two-PR per `[[feedback_two_pr_docs_execution]]`, local `--no-ff` merges per Epic 9 precedent (`gh` is unauthenticatable non-interactively). Per `[[project_warden_shared_doc_commit_boundary]]`, the post-merge PR may not be file-isolatable if foreign multi-story edits are co-mingled in `sprint-status.yaml` — ship the feature PR alone and defer the post-merge pass if so.

---

## Appendix — Checklist completion

| § | Item | Status |
|---|---|---|
| 1.1 | Triggering story identified | [x] — no single story; a strategic pivot surfaced against Epic 9's `ready-for-dev` 9.9b + the `:2750` gap |
| 1.2 | Core problem defined + categorized | [x] — technical limitation + failed approach + strategic pivot |
| 1.3 | Initial impact + evidence gathered | [x] — `:2748`/`:2750`, PERF-002 arithmetic, greenfield-GPU verified negative |
| 2.1 | Current epic completable as planned? | [x] — Epic 9 completable, amended (3rd re-cut) |
| 2.2 | Epic-level changes determined | [x] — 1 added (12), 1 amended (9), 1 amended (1), 3 held (5/6/7) |
| 2.3 | Remaining epics reviewed | [x] — 2/3/4/8/10/11 unaffected, verified |
| 2.4 | Epics invalidated / new needed? | [x] — none invalidated; Epic 12 added |
| 2.5 | Epic order / priority change | [x] — **engine-first resequencing; the substantive change** |
| 3.1 | PRD conflicts | [x] — 5 amendments; **MVP survives** |
| 3.2 | Architecture conflicts | [x] — 7 amendments; BF-7 verified surviving |
| 3.3 | UI/UX conflicts | [N/A] — no detection-engine surface in `ux-design.md` |
| 3.4 | Other artifacts | [x] — 2 Python dep manifests; SEC-007 allowlist; commitlint scopes verified sufficient |
| 4.1 | Option 1 Direct Adjustment | [x] **Viable — SELECTED.** Effort Medium / Risk Low |
| 4.2 | Option 2 Rollback | [x] Not viable — nothing needs reverting |
| 4.3 | Option 3 PRD MVP Review | [x] Not viable — MVP unaffected; deliberately avoided |
| 4.4 | Path selected + justified | [x] — Hybrid: Direct Adjustment + gated spike + resequencing |
| 5.1–5.5 | Proposal components | [x] — Sections 1–5 above |
| 6.1–6.3 | Review + approval | [x] — 7/7 proposals approved incrementally by Stephane, 2026-07-16 |
| 6.4 | sprint-status.yaml updated | [!] **Action-needed** — handed off (§4.4) |
| 6.5 | Next steps confirmed | [x] — §5 |

**Open [!] items:** 6.4 (sprint-status application) — assigned to Developer/PO in §5.
