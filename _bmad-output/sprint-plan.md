# Warden Monorepo — Sprint 3 Plan

**Generated:** 2026-05-09
**Sprint:** Sprint 3 (post-consolidation V1 push)
**Project:** Warden_monorepo
**Owner:** Stephane (solo dev)
**Inputs:** `epics-and-stories.md` (76 stories, 11 epics) + `implementation-readiness-report-2026-05-09.md` (READY WITH MINOR AMENDMENTS — 3 🟠 amendments applied at commit 5968ef9)

---

## 1. Sprint commit summary

- **Epics committed:** 11 (Epic 0 → Epic 10)
- **Stories committed:** 76
- **Stories that fit in one sprint:** 75 (per Decision #ES-9)
- **Spike-or-split story:** 1 — Story 1.1 AR-SPIKE (load-bearing first work item; downstream mobile scope branches on rung outcome)
- **Capacity allocation (Decision #ES-10):** 80% V1 stories / 20% maintenance backlog (incidents, deps, infra drift, CI flakes, support inbox)
- **External-blocked:** Story 10.4 (Stripe production activation — Root provides company number)
- **Parallel non-V1-blocking track:** Story 10.5 (demand-evidence capture — runs alongside the cascade per PRD §2)

---

## 2. Hard gates and ordering invariants

These are non-negotiable — violating any of them breaks the sprint.

### Gate G0 — Sprint 2.5 Closure (blocks Sprint 3 merge)

Per **Decision #ES-3**, Stories **0.1 → 0.2** must close before any Sprint 3 story merges to `main`. Sprint 3 work may be developed on feature branches in parallel, but no merge until G0 clears.

### Gate G1 — AR-SPIKE rung outcome (gates Epic 5/6 mobile scope)

**Story 1.1 (AR-SPIKE)** is the load-bearing first work item. Its outcome (pass / rung-1 / rung-2 / rung-3) determines whether:

- **Pass / Rung-1**: Card View auto-population works at Q-quality → full Epic 5 scope ships.
- **Rung-2**: Card View auto-populates at degraded quality → Epic 5 ships with QA caveat in 10.1.
- **Rung-3**: Card View degrades to manual-clip-from-timeline path only → Story 5.1's adaptive-grid AC narrows; Story 5.3 becomes the primary entry point; Cinema Mode (5.4) still ships.

Stories **5.1, 5.3, 5.4, 5.5, 6.6** all carry an explicit `Story 1.1 spike` dependency. **Do not start any of them before AR-SPIKE has a binding rung verdict.**

### Gate G2 — Epic 6 ↔ Epic 7 mandatory interleave

Per readiness amendment #2, Epic 6 must NOT ship in full before Epic 7 starts. The interleave order is:

```
6.1 → 6.3 → 7.1 → 6.4 → (6.2, 6.5, 6.6, 6.7, 6.8, 6.9) → 7.2 → 7.3
```

Reason: Story 6.4 (voice slot re-record) depends on Story 7.1 (silent auto-save underpins the resume guarantee). Shipping all of Epic 6 first leaves 6.4 dangling on a cross-epic dep.

### Gate G3 — Story 2.5 telemetry independence

Per readiness amendment #3, Story 2.5 (T1-active-player emission) depends on **Epic 0 Story 0.2** (legacy view-mode toggle UI lands as complete-as-legacy), **NOT** on Story 5.5. Story 2.5 may land before or after 5.5 — they are orthogonal. This unblocks telemetry from PERF-003 work.

---

## 3. Wave structure

Solo-dev cascade — each wave gates the next on its critical-path story. Stories listed without sub-bullets in a wave are parallelizable within that wave (ship in any order once their deps are met).

### Wave 0 — Sprint 2.5 Closure GATE (G0)

| Order | Story | Title | Deps |
|---|---|---|---|
| 1 | 0.1 | Conduct Per-Story Conflict Audit for Sprint 2.5 In-Flight Mobile Work | — |
| 2 | 0.2 | Execute Sprint 2.5 Per-Story Dispositions | 0.1 |

**Exit criteria:** 0.2 marked done. Sprint 3 stories cleared to merge.

---

### Wave 1 — AR-SPIKE FIRST WORK (G1)

| Order | Story | Title | Deps |
|---|---|---|---|
| 3 | 1.1 | Pre-PRD Performance Spike (AR-SPIKE) — Resolves Decision #ES-2 | — |

**Exit criteria:** Rung verdict written into 1.1 acceptance. Downstream mobile scope (Epic 5/6) frozen against the verdict.

---

### Wave 2 — Brownfield + Cross-Language Contracts + Tooling (parallelizable)

Once 1.1 has a binding choice on whether real JSI binding ships, the Firebase v12 RN auth chain can begin. Independent foundation stories run in parallel.

**Track A — Firebase v12 RN auth chain (sequential):**

| Order | Story | Title | Deps |
|---|---|---|---|
| 4 | 1.4 | Firebase v12 RN Auth Migration — Add Deps + Prebuild | 1.1 (binding choice) |
| 5 | 1.5 | Firebase v12 RN Auth Migration — Migrate firebaseConfig.ts | 1.4 |
| 6 | 1.6 | Firebase v12 RN Auth Migration — Migrate authService.ts | 1.5 |
| 7 | 1.7 | Firebase v12 RN Auth Migration — Migrate subscriptionService.ts | 1.6 |
| 8 | 1.8 | Firebase v12 RN Auth Migration — Migrate detectionConfigService.ts | 1.7 |
| 9 | 1.9 | Firebase v12 RN Auth Migration — End-to-End Manual Test of All 10 PRD Journeys | 1.4–1.8 |

**Track B — Independent foundation (parallel with Track A):**

| Story | Title | Deps |
|---|---|---|
| 1.2 | Foreground Service Android Config Plugin (BF-5) | — |
| 1.3 | Stripe API Pin Bump 2026-03-25.dahlia → 2026-04-22.dahlia (BF-1) | — |
| 1.10 | user-doc.schema.json Tighten + Reconcile (AR-1) | — |
| 1.11 | Wire apps/web to @warden/contracts/user-doc (AR-2) | 1.10 |
| 1.12 | customer.subscription.updated Defensive Handler (AR-3) | 1.10, 1.11 |
| 1.14 | Firestore Rules Coverage Extended (AR-6) | — |
| 1.15 | Firestore Rules Production Deploy (BF-2) | 1.14 |
| 1.17 | Webhook Idempotency Regression Coverage (AR-9) | 1.12 |
| 1.18 | Vitest Serial-Mode V1 CI Workaround (BF-4) | — |

**Track C — Tooling chain (parallel; Epic 9 + 1.13 + 1.16):**

| Story | Title | Deps |
|---|---|---|
| 9.1 | schema_version: 1 Add to map_config.json Writers (BF-6) | — |
| 9.2 | Tool 5 warden_analyzer Real-Footage AC Validation | 9.1 |
| 1.13 | Hybrid map_config.json Delivery + schema_version: 1 (AR-4 + BF-6) | 1.10, 9.1 |
| 1.16 | detection_config/latest Operator Documentation + Shared Firebase Project Documentation | 1.13 |
| 9.3 | Reference Hash Regression for 4 Awaiting-Hash Maps | 9.1, 1.13 |
| 9.4 | jsonschema Strict Validation Against contracts/map-config.schema.json | 9.1, 1.13 |

**Wave 2 exit criteria:** Track A through 1.9; Track B through 1.17; Track C through 9.4. Foundation contracts + brownfield reconciliation done.

---

### Wave 3 — Reader-App Build Gate + Activation Telemetry

| Order | Story | Title | Deps |
|---|---|---|---|
| — | 2.1 | Reader-App CI Gate Implementation | 1.4 (cross-epic) |
| — | 2.6 | EXPO_PUBLIC_AUTH_BYPASS Deny in Release Configs | 2.1 |
| — | 2.2 | Activation Telemetry Wrapper + Payload Allowlist | 2.1 |
| — | 8.1 | French i18n Bundle at apps/mobile/assets/i18n/fr.json | 2.1 |
| — | 2.3 | T0 Emission in authService.ts on Auth-State-Change → Paid | 2.2, 1.6 |
| — | 2.4 | T1-Coach Emission in exportPipeline.ts on Confirmed-Dispatch | 2.2, 2.3 |

**Note (G3):** Story 2.5 (T1-active-player) only needs 2.2, 2.3, 0.2. It can land here in Wave 3 immediately after 2.3 ships, OR be deferred to Wave 6 alongside Cinema Mode work — author's choice. Recommended: ship in Wave 3 to unblock end-to-end T0/T1 telemetry validation early.

| — | 2.5 | T1-Active-Player Emission in CinemaModeScreen.tsx on First View-Mode Toggle | 2.2, 2.3, 0.2 (NOT 5.5) |

---

### Wave 4 — Web Subscribe & Manage Funnel (parallel-friendly)

Mostly independent of mobile cascade. Slot during natural mobile-blocked moments (Track A waits, EAS prebuilds, etc.).

| Story | Title | Deps |
|---|---|---|
| 4.1 | Web Token Bump #FF6B00 + Accent-Hover #FF8533 + A11Y-001 Contrast Re-Verify | — |
| 4.3 | Footer "Get help" Link → mailto:support@warden.team | — |
| 4.4 | PasswordResetForm.tsx + sign-in ?passwordReset=1 Query Handler | — |
| 4.5 | CancelDialog.tsx — Anti-Dark-Pattern | — |
| 4.6 | EmptySubscription.tsx | — |
| 8.2 | errorReporting.ts mailto Formatter | — |
| 4.2 | OG Image Asset + Layout Meta | 4.1 |
| 4.7 | Web English Copy with FR-Verbatim Insertions Embedded Inline | 4.1 |
| 4.8 | Web Funnel Analytics Events | 1.12 |

---

### Wave 5 — Six-State Entitlement (gated by 1.7)

| Order | Story | Title | Deps |
|---|---|---|---|
| — | 3.1 | deriveEntitlementState Pure Function + 6-State Regression Tests (AR-11) | 1.7 |
| — | 3.5 | PaymentWarning.tsx Web Composition | — (parallel-able from sprint start) |
| — | 3.6 | Canceling Status Badge + Resubscribe CTA | — (parallel-able from sprint start) |
| — | 3.2 | EntitlementBanner.tsx for Payment-Failed | 3.1 |
| — | 3.3 | SubscriptionRequiredScreen.tsx for Lapsed | 3.1 |
| — | 3.4 | OfflineIndicator for Offline-Grace | 3.1 |
| — | 3.9 | 30-Day MMKV-Cached Entitlement + Day-31 Expiry | 3.1 |
| — | 3.7 | Mobile Login (mobile-AUTH-001) Entitlement Gate | 1.5/1.6, 3.3 |
| — | 3.8 | Mobile Foreground Re-Fetch After Stripe Customer Portal Round-Trip | 1.7, 3.1 |
| — | 3.10 | Session-Data Preservation Across Lapse → Resubscribe | 3.1, 3.3 |

---

### Wave 6 — Mobile Card View, Cinema Mode & View-Mode Toggle (G1-gated)

**Do not start Wave 6 until Story 1.1 has a binding rung verdict.**

| Order | Story | Title | Deps | Rung-3 note |
|---|---|---|---|---|
| — | 5.1 | CardViewScreen with Adaptive Grid + Sort Persistence | 0.2, 1.1 | AC narrows to manual-clip-only |
| — | 5.4 | Cinema Mode Immersive Review with Reveal-on-Tap Controls | 0.2, 1.1 | unchanged |
| — | 5.5 | View-Mode Toggle (Full / Minimap / Minimap+HUD) ≤100 ms | 5.4, 2.5, 1.1, 0.2 | unchanged |
| — | 5.2 | Card → Cinema Mode Tap Navigation | 5.1, 5.4 | gated by 5.1 narrowing |
| — | 5.3 | Cards/Timeline Top-Bar Toggle + Manual Clip from Timeline | 5.1, 5.4, 1.1 | becomes primary entry path |
| — | 5.6 | Default Full View for Unknown Map | 5.5 | — |
| — | 5.7 | View-Mode Preference Persistence | 5.5 | — |
| — | 5.8 | Next/Previous Explicit Buttons in Cinema Mode | 5.4, 5.5 | — |

---

### Wave 7 — Mobile Clip + Voice + Auto-save (G2 interleave)

**Hard order — do not flatten:**

| Order | Story | Title | Deps |
|---|---|---|---|
| 1 | 6.1 | 30-Second Clip Region with Bracket Handles 5–60s Bounds | 5.4, 5.5 |
| 2 | 6.3 | 3-Slot Voice Annotation (Before / During / After) | 6.1 |
| 3 | **7.1** | **Silent Auto-save in Clip Mode** | **6.1, 6.3, 1.2** |
| 4 | 6.4 | Voice Slot Re-Record | 6.3, 7.1 |
| 5 | 6.2 | Manual Clip from Any Timeline Point | 5.3, 5.4, 6.1 |
| 6 | 6.5 | Clip Preview with Assembled Voice | 6.1, 6.3 |
| 7 | 6.6 | Mobile/HD Encode Tier Selection | 6.1, 6.3, 6.5, 1.1 |
| 8 | 6.9 | clipDeletion.ts Cascade (AR-12, PRIV-003) | 6.6 |
| 9 | 6.7 | OS Share Sheet Dispatch | 6.6, 2.4 |
| 10 | 6.8 | Discord-Inline-Playable H.264/AAC Contract Verification | 6.6, 6.7, 1.9 |
| 11 | **7.2** | **Resume Cinema Mode at Exact Frame** | **7.1** |
| 12 | **7.3** | **Verify J2 Interruption + Resume E2E** | **7.1, 7.2, 1.2** |

Stories 6.2, 6.5 may shift forward (between 6.4 and 6.6) if 7.1 reveals auto-save state-machine assumptions worth validating against assembled-clip preview earlier — judgment call at the time.

---

### Wave 8 — Help / Account Bottom Sheet

| Story | Title | Deps |
|---|---|---|
| 8.3 | Account Bottom-Sheet Aide Section | 8.1 |

---

### Wave 9 — V1 Launch Readiness

| Order | Story | Title | Deps |
|---|---|---|---|
| — | 10.2 | ToS-Monitoring Tracker for EVA After-h | — (start any time after Wave 0) |
| — | 10.3 | Google Play V1 Review-Readiness Checklist | 1.9, 1.15 |
| — | 10.4 | Stripe Production Activation | 1.12, 1.15, 1.16, **EXTERNAL: Root provides company number** |
| — | 10.1 | V1 Launch Checklist Deliverable | All other stories (synthesis — last) |

**10.4 contingency:** If Root has not provided the company number by the time 10.1 begins, 10.4 carries forward to a post-Sprint-3 Stripe-activation mini-sprint. Document this carry-over in 10.1's acceptance.

---

### Parallel Track — Demand Evidence (non-V1-blocking)

Per PRD §2 + Decision #ES-9 carve-out:

| Story | Title | Deps | When |
|---|---|---|---|
| 10.5 | Demand Evidence Capture Pre-V1 | — | Runs parallel to entire cascade. Does not block V1 launch but PRD-mandated. Slot during the 20% maintenance capacity allocation. |

---

## 4. Critical path

The longest dependency chain — anything off this path is parallelizable.

```
0.1 → 0.2 → 1.1 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9
                                         → 3.1 → 3.3 → 3.7
                                         → ...
                                                     → 10.3 → 10.1
```

Practical critical path through clip/auto-save/launch:
```
1.1 → 1.4 → 1.5 → 1.6 → 1.7 → 3.1 → ... → 5.4 → 5.5 → 6.1 → 6.3 → 7.1 → 6.6 → 6.7 → 6.8 → 7.2 → 7.3 → 10.1
```

Any slip on Story **1.1 (AR-SPIKE)**, **1.7 (subscriptionService migration)**, or **5.4/5.5 (Cinema Mode)** moves the whole sprint end-date.

---

## 5. Capacity allocation (Decision #ES-10)

- **80% V1 stories** — the 75 fits-in-one-sprint stories above + the AR-SPIKE.
- **20% maintenance backlog** — incident response, dependency drift, CI/EAS infra fixes, support inbox, Story 10.5 demand-evidence work, and any Sprint 2.5 fall-out surfaced by Story 0.1's audit beyond what 0.2 absorbs.

Solo-dev guidance: do not let maintenance creep above 20% for more than one week without re-baselining. If it does, escalate scope from this plan rather than silently slipping the critical path.

---

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| AR-SPIKE returns rung-3 → Epic 5 scope narrows mid-sprint | Wave 6 stories already carry rung-3 contingency notes (5.1, 5.3); Story 10.1 captures the rung verdict in launch checklist. |
| Firebase v12 RN auth chain reveals an integration blocker mid-1.5 or 1.6 | Story 1.9 J1–J10 run on dev build catches this before web/3.x consumes migrated services; rollback path is a re-pin to v11 + revert 1.4–1.8 (single-PR-per-story makes this clean). |
| Root delays company number → 10.4 blocks 10.1 | 10.1 explicitly carries 10.4 as an external-blocked checklist item; V1 ships with Stripe in test-mode if necessary, gated by go-live activation in a follow-up sprint. |
| Maintenance backlog exceeds 20% (Sprint 2.5 audit reveals more debt than scoped) | Re-baseline at first weekly checkpoint; cut from Wave 4 (web funnel) or Wave 8 (8.3) before cutting from critical path. |
| Epic 6 ↔ 7 interleave gets flattened under deadline pressure | 6.4's hard dep on 7.1 makes this self-correcting — flattening leaves 6.4 visibly dangling. |

---

## 7. Definition of done for Sprint 3

- All 75 V1-committed stories merged to `main` with their AC checklists fully ticked.
- Story 1.1 spike report committed under `_bmad-output/` with binding rung verdict.
- Story 10.1 V1 Launch Checklist exists and lists Story 10.4 as external-blocked-or-done.
- Story 10.5 demand-evidence corpus captured (non-V1-blocking — does not gate Sprint 3 close, but PRD §2 obligation tracked).
- All 11 epic retrospectives marked done OR explicitly deferred to a Sprint 3 retrospective batch with rationale.

---

## 8. Tracking

Status tracker: [`sprint-status.yaml`](sprint-status.yaml) — auto-updated by dev-story / code-review workflows as stories transition `backlog → ready-for-dev → in-progress → review → done`.
