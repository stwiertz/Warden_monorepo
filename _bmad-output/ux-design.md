---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7]
inputDocuments:
  - _bmad-output/prd.md
  - _bmad-output/architecture.md
  - _bmad-output/product-brief.md
  - _bmad-output/product-brief-distillate.md
  - _bmad-output/legacy/distillate/06-ux-design.md
  - _bmad-output/legacy/distillate/02-mobile.md
  - _bmad-output/legacy/distillate/03-web.md
  - apps/mobile/src/shared/components/hud/ (12 atoms + tokens.ts)
  - apps/web/src/components/ui/ (7 shadcn primitives + cta-class.ts)
  - apps/web/src/components/auth/
  - apps/web/src/components/checkout/
  - apps/web/src/components/dashboard/
  - apps/web/src/components/layout/
  - docs/component-inventory-mobile.md
  - docs/component-inventory-web.md
project_name: Warden_monorepo
output_override: true
output_override_reason: User explicitly requested _bmad-output/ux-design.md (matches brief/PRD/architecture path convention) instead of planning-artifacts/ux-design-specification.md
---

# UX Design Specification — Warden_monorepo

**Author:** Stephane
**Date:** 2026-05-07
**Status:** in-progress (step 1 / 8)

---

## Document Conventions

- **Mobile UI language:** French (locked).
- **Web UI language:** English (locked) with two FR-verbatim insertions: hero "Progresser plus vite en investissant moins de temps." and deferred-billing "Vous ne serez pas débité avant le [date]".
- **Design tokens:** consumed from `apps/mobile/src/shared/components/hud/tokens.ts` (mobile) and Tailwind 4 theme + shadcn/ui defaults (web). No cross-surface component reuse — visual coherence is achieved by token alignment, not shared components.
- **Reference device (mobile):** Poco X5 (Snapdragon 695, 6 GB RAM, 6.67"). Supported screens 5.5" – 6.7"+.
- **Orientation:** No lock. Every mobile screen has portrait + landscape layouts.
- **Reader-App contract enforcement:** every mobile screen, copy string, and component tested against the CI gate banlist (€7.99, €79.90, "subscribe", "abonnement", "monthly", "yearly", "buy" + plan-picker imports).

## 1. Foundations (locked — confirmed without re-litigation)

The PRD and architecture have already bound the personas, information architecture, navigation, visual languages, and component-tier strategy. UX inherits these and refers to them rather than restating them. The remaining UX work in §§2–6 lands the 14 escalated decisions, copy decks, and the cross-surface coherence audit.

### 1.1 Personas (PRD §4 — bound)

| Persona | Age | Role | Surface(s) | UX implications carried into §§2–6 |
|---|---|---|---|---|
| **Coach Thomas** | 26 | Primary — part-time esports coach | Web (J1, J7, J8) + Mobile (J1, J2, J3, J9) | Drives the Card View → Cinema Mode → Clip Export → Voice → Share path. Anti-success: any sentence that includes "open the laptop". Dominant emotion: *purposeful immediacy*. |
| **Active Player Maxime** | 22 | Secondary — high-division amateur, doubles as assistant coach | Mobile (J4) | Solo-review, no export. T1-active-player path = Cinema Mode opened + view-mode toggled ≥1. UX: Cinema Mode must work end-to-end without ever inviting an export. |
| **Passive Player Lucas** | 17 | Tertiary — receives clips on Discord; never installs initially | Web (J5, J6 conversion) — *Discord, not Warden* | UX responsibility ends at the share-sheet dispatch in J1; J5 is Discord's surface. Lucas only encounters Warden UX in J6 (web checkout funnel). |

When Lucas converts (J6), he becomes "an Active Player like Maxime" — same archetype-by-state, different entry path. They are the same character at different stages.

### 1.2 Information Architecture (PRD §3, §7 — bound)

**Mobile** — Reader-App, login-only against Stripe-issued entitlement. No top-level screens beyond:

1. `LoginScreen` (FR mobile-AUTH-001) — French; rejects unauthenticated users with a deep-link to web for sign-up
2. `HomeScreen` / `CardViewScreen` (FR mobile-CARD-001..005) — episode triage grid with cold-start "Resume / Import"
3. `ProcessingScreen` (FR mobile-AUTO-SLICE-001..004) — long-running pipeline with rotating tips
4. `CinemaModeScreen` (FR mobile-CINEMA-001..005) — immersive review + view-mode toggle + manual-clip entry
5. `ClipModeScreen` (FR mobile-CLIP-001..005) — 30-second region + bracket handles + 3-slot voice + preview
6. `ExportShareScreen` (FR mobile-EXPORT-001..004) — quality choice + encode progress + OS share-sheet handoff
7. `EntitlementBanner` (FR mobile-AUTH-006) — payment-failed warning overlaid on Home/Cinema with deep-link to web Customer Portal
8. `SubscriptionRequiredScreen` (FR mobile-AUTH-003) — full-screen for `lapsed` / `signed-out`-with-no-cache; deep-link to web Customer Portal; no in-app pricing

UX may not introduce additional top-level screens. UX may not introduce in-app pricing, plan-picker, or "subscribe" CTAs anywhere in mobile.

**Web** — three routes plus Stripe-hosted Checkout and Customer Portal as full-page redirects:

1. `/` (Landing) — SSR + cached; FR-locked French hero; single CTA → `/pricing`
2. `/pricing` — client-interactive; 2 plan cards (€7.99/mo, €79.90/yr); auth modal overlay; redirect to Stripe Checkout
3. `/dashboard` — protected (server auth check + fresh client Firestore reads, no `onSnapshot`); status badge + plan + next-payment-date + "Manage Subscription" deep-link to Stripe Customer Portal
4. `/privacy` + `/terms` — static legal pages

Stripe-hosted Checkout (full-page redirect) and Stripe Customer Portal handle payment capture, payment history, plan switching, cancellation, and payment-method updates. UX does NOT design custom payment forms or a custom billing self-service UI.

UX may not introduce additional routes for V1.

### 1.3 Navigation Flows (bound)

**Mobile binding flow (PRD §3 MVP — bound):**

```
LoginScreen
   │
   ▼
HomeScreen (Card View) ──► (no Card or unknown map)
   │                              │
   │ tap card                     │ scrub timeline → tap "clip"
   ▼                              │
CinemaModeScreen ◄────────────────┘
   │
   │ tap "clip" (auto-sliced or manual)
   ▼
ClipModeScreen (30s region + bracket handles + 3 voice slots)
   │
   │ confirm
   ▼
ExportShareScreen (Mobile / HD tier choice)
   │
   │ encode complete → OS share sheet
   ▼
[OS Share Sheet — Discord / Messages / Drive / etc.]
```

**Cross-state navigation:**

- `payment-failed` → `EntitlementBanner` overlays Home and Cinema; deep-link to web Stripe Customer Portal
- `lapsed` / `signed-out` (no cache) → `SubscriptionRequiredScreen` replaces shell; deep-link to web Customer Portal
- `offline-grace ≤30d` → app behaves identically to `paid`; subtle offline indicator (§2.5)
- Foreground Service notification — sticky Android notification "Analyse en cours…" with progress percentage (architecture-bound copy)

**Web binding flow (PRD §4 J1 — bound):**

```
Discord coupon link  ──►  /  (Landing)  ──►  /pricing
                                                │
                                                │ click plan card
                                                ▼
                                        Auth modal overlay
                                        (Google + Email/Password)
                                                │
                                                │ auth success
                                                ▼
                                  Stripe-hosted Checkout (full-page redirect)
                                                │
                                                │ checkout complete
                                                ▼
                                       /dashboard?success=1
```

**Cross-state on web:**

- `payment-failed` → Dashboard `PaymentWarning` banner (amber) + "Update payment method" deep-link to Stripe Customer Portal
- `canceling` → Dashboard status badge gray + "Resubscribe" CTA
- `canceled` → Dashboard "Resubscribe" path; no "we'll miss you" copy; no exit survey
- No real-time updates — Dashboard reads on page load; user reloads or navigates back from portal to see fresh state

### 1.4 Visual Languages (bound — two languages, one brand)

| | Mobile — Tactical HUD | Web — Direction A "Clean Minimal" |
|---|---|---|
| **Adopted** | 2026-05-01 (revised from earlier "warm/military") | 2026-04-02 (chosen over B Bold-Tactical and C Warm) |
| **Theme** | Dark-first (~95% dark / 5% accent) | Dark mode default |
| **Accent** | Warden orange `#FF6B00` — never as fill, only 1px outlines, glows, focus | Warden orange `#E8731A` — ghost/outline buttons, primary CTAs as orange-fill |
| **Decoration** | HUD brackets, corner ticks, scanlines (NEVER on video frames), reticle, status pills | Soft borders, rounded cards, generous whitespace; no decorative motifs |
| **Typography** | Roboto (body/UI) + JetBrains Mono (timecodes/scores/tactical labels — UPPERCASE 1.5–2.5 letter-spacing) | Inter |
| **Tone** | Tactical immersion — "review is play, not work" | Boring is good — invisible portal, Stripe-handoff trust |
| **Role** | The product (long-form review experience) | The door (must be invisible, ship-speed) |

The two visual languages are intentional and not in conflict. They share dark mode + Warden orange + gaming-audience tone + anti-fake-content posture (no stock photos, no testimonials, no countdown timers). Cross-surface coherence audit — including token-level alignment of `accent`, `bg`, `text`, type-scale ramp — is in §5.2 (Decision #UX-13).

### 1.5 Design Tokens (locked)

**Mobile** — consumed from `apps/mobile/src/shared/components/hud/tokens.ts` (already shipped):

| Token group | Values |
|---|---|
| Background | `bg #0a0a0d` · `surface #101014` · `elev #15151a` · `elev2 #1c1c22` · `line #26262e` |
| Text | `text #F0F0F0` · `muted #8a8a92` · `dim #52525a` |
| Accent | `accent #FF6B00` · `accent-soft rgba(255,107,0,0.18)` · `accent-dim rgba(255,107,0,0.5)` |
| Status | `team-blue #3a8eff/#5b8aff` · `success #22C55E` (share-complete only) · `error #EF4444` |
| Spacing | base 4px · small 4 · med 8 · large 16 · section 24 · edge safe-zone 16 |
| Touch target | min 44×44 px |
| Type ramp | display-mono 22 · heading-mono 16 · subhead-mono 12 · value-mono 11–13 · body 13–14 · stamp 9–11 · score 16+text-shadow |

**Web** — consumed via Tailwind 4 theme + shadcn/ui CSS variables:

| Token group | Values |
|---|---|
| Background | `bg #0F0F0F` · `surface #1A1A1A` · `surface-elevated #252525` · `border #333333` |
| Text | `text #F0F0F0` · `text-secondary #999999` |
| Accent | `accent #FF6B00` (post-Option-B reconciliation 2026-05-07) · `accent-hover #FF8533` |
| Status | `success #22C55E` · `warning #F59E0B` · `error #EF4444` |
| Contrast (verified) | text-primary on bg ~16:1 (AAA) · text-secondary ~5.5:1 (AA) · orange ~4.8:1 (AA-large/bold) |
| Spacing | base 4px tokens · page padding 16 mobile / 32 desktop · max content 1024 centered |
| Border-radius | buttons 6 · cards 8 · badges 4 · full only avatars/status dots |
| Type ramp | H1 800/32–48 · H2 700/24–32 · H3 600/20–24 · body 400/16 · small 500/14 · badge 600/12 · LH 1.2 headings / 1.5 body |
| Breakpoints | mobile (default) + `md:` (768+); no tablet-specific |

**Cross-surface alignment** — §5.2 audit + Option-B reconciliation (locked 2026-05-07): both surfaces now anchor on `accent #FF6B00`, shared dark-mode posture, shared gaming-audience tone, shared anti-fake-content stance. No components are shared between surfaces; coherence is achieved via tokens, not code. Web token bump tracked as Sprint-3 task (§6.5).

### 1.6 Component Tier Strategy (bound)

**Mobile** — three tiers, all custom-themed; library defaults are NEVER used:

1. **Tactical primitives** — already shipped at `apps/mobile/src/shared/components/hud/`: 12 atoms (`Screen`, `HudBracket`, `CornerTick`, `Stamp`, `Marks`, `Field`, `CircleBtn`, `EngageButton`, `Icon`, `MapArt`, `Timeline`, plus `tokens.ts`). UX inherits and extends; UX does **not** replace.
2. **Standard UI** — custom-themed buttons, toasts, modals, sheets via NativeWind + React Native Reusables (shadcn/ui-for-RN, copy-paste ownership) themed dark + accent orange. Library defaults rejected.
3. **Custom core** — video player, MinimapView, ViewModeToggle, ClipModeScreen (bracket-handle region selector), AudioRecorder, EpisodeNavigator, Timeline scrubber.

**New mobile components UX introduces in §§2–4** (all enumerated in architecture's project tree):

- `EntitlementBanner.tsx` (`apps/mobile/src/features/auth/`) — payment-failed warning banner, French copy, deep-link to web Customer Portal, MUST NOT show price → §2.5 visual states + §4.1 copy
- `SubscriptionRequiredScreen.tsx` (`apps/mobile/src/features/auth/`) — full-screen for `lapsed` / `signed-out`-with-no-cache, French copy, deep-link to web, MUST NOT show price → §2.5 + §4.1
- `OfflineIndicator` — subtle iconography for `offline-grace ≤30d`; embedded as a small `Stamp`-style chip in the Home top-bar → §2.5
- `RotatingTip` — processing-screen tip rotator (5–8s cadence) → §2.3 + §4.1

**Web** — single tier. **7 shadcn primitives** cover 100% of MVP surface: `Button`, `Card`, `Dialog`, `Input`, `Badge`, `Alert`, `Skeleton`, plus `cta-class.ts` helper. NO custom components for V1; compositions (hero, plan-selector, status-card, payment-warning, cookie-banner) are built directly from primitives. Extract a custom component later only if the same composition repeats ≥3 times.

**Existing web compositions** UX confirms or refines (per `apps/web/src/components/`):

- `auth/` — `SignInForm`, `GoogleSignInButton`, `SignOutButton`, `RegistrationForm` → §3.1 auth modal
- `checkout/` — `PlanCard`, `PlanCta`, `CouponInput`, `CheckoutContext` → §3 (compositional only)
- `dashboard/` — `SubscriptionCard` (status badge + plan + next-date + Manage-Subscription CTA) → §3.2
- `layout/` — `Header`, `HeaderAuthActions`, `Footer`, `CookieBanner` → §3.4

UX confirms current compositions are sufficient and adds: `PaymentWarning` banner + cancel-confirmation dialog wireframe (both built from `Alert` + `Dialog` primitives, no new custom component) → §3.2.

### 1.7 What UX is NOT re-litigating

For traceability, the following items are PRD- or architecture-locked and out of UX scope:

- Reader-App structural contract (FR cross-READER-APP-001)
- Six-state entitlement model semantics + transitions (PRD §2 + architecture §6 state machine)
- Activation T0/T1 anchors + dual-T1 paths (FR cross-ACTIVATION-001/002)
- 14 canonical maps (`tools/frame_labeler.py:19-34` MAP_LABELS)
- Pricing positioning (€7.99 / €79.90 — web only)
- French UI lock (mobile); English UI with French hero + deferred-billing (web)
- 30-second clip + 3-slot voice structure
- Three-mode view toggle (Full/Minimap/Minimap+HUD)
- Card View → Cinema Mode → Clip Export navigation
- Component file structure (architecture step 6 binds locations)
- 12 cross-surface invariants (especially Reader-App banned imports/strings)
- HUD primitives at `src/shared/components/hud/` (UX inherits/extends, never replaces)
- 7 web shadcn primitives in use
- Stripe-hosted Checkout (full-page redirect) + Stripe Customer Portal delegation
- Auth-modal-before-checkout lazy pattern
- No real-time on web; no push notifications V1; no orientation lock mobile; no onboarding tutorials
- Anti-dark-pattern policy (no exit survey, no guilt-trip, no fake urgency, no countdown timers)
- Persona names (Coach Thomas / Active Player Maxime / Passive Player Lucas)

---

## 2. Mobile Interaction Patterns

This section lands Decisions #UX-1 (A11Y state catalog), #UX-4 (Cinema Mode interactions), #UX-5 (Card View triage), #UX-6 (loading/processing), #UX-11-mobile (empty states), #UX-14 (manual-clip-from-timeline). All visual treatments inherit the HUD design tokens from §1.5 and the HUD primitives from `apps/mobile/src/shared/components/hud/`.

### 2.1 Cinema Mode interaction model — Decision #UX-4 RESOLVED

Cinema Mode is the immersive review surface (FR mobile-CINEMA-001..005). It must work in landscape AND portrait; no orientation lock. PERF-003 binds: view-mode toggle ≤ 100 ms — implemented as crop/style change on the same `expo-av` source per architecture, no player swap.

#### 2.1.1 Reveal-on-tap controls — auto-hide cadence

| State | Trigger | Visual | Auto-hide |
|---|---|---|---|
| Controls revealed | Single tap on video surface OR cold-Cinema-start | Top bar (close, view-mode toggle, episode nav) + bottom bar (timeline, play/pause, "clip", "voice") + bracket overlays | **4 seconds** of no touch interaction → fade-out 200 ms |
| Controls hidden | After 4 s of inactivity (or single tap when revealed) | Pure video surface; no chrome | — |
| Controls re-revealed | Single tap | Same as "revealed" | — |
| User-pinned (advanced) | Long-press top bar 600 ms | Padlock icon (`Stamp` style) appears in top-right; controls stay visible until long-press again | — |

**Why 4 seconds:** legacy distillate-bound. Long enough that a coach scrubbing the timeline doesn't lose handles mid-thought; short enough that the immersion returns when the coach pauses to think. **Reduced-motion respect:** when `AccessibilityInfo.isReduceMotionEnabled() === true`, disable the fade-out and snap controls in/out.

#### 2.1.2 View-mode toggle — segmented control + double-tap gesture redundancy

The PRD requires both a segmented control AND a double-tap top-left gesture to cycle Full → Minimap → Minimap+HUD. The redundancy is deliberate: the segmented control is for first-time-user discoverability (no onboarding tutorial — discoverability must come from the visible UI); the double-tap gesture is for power-user muscle-memory (Maxime's solo-review path J4).

**Segmented control layout (top bar, revealed-controls state):**

```
┌─────────────────────────────────────────────────────────────────┐
│ [×]                                                       [⋮]   │ ← top bar; close + overflow
│                                                                 │
│      ┌─────────┬───────────┬──────────────────┐                 │
│      │  FULL   │  MINIMAP  │  MINIMAP + HUD   │  ← segmented    │
│      └─────────┴───────────┴──────────────────┘     control     │
│      (active segment: 1px orange border + accent-soft fill)     │
└─────────────────────────────────────────────────────────────────┘
```

**Active segment treatment** — 1px orange border (`accent`) + `accent-soft` background + uppercase JetBrains Mono 12 with 1.5 letter-spacing. Inactive segments are `text-muted` foreground on `surface` background, no border.

**Double-tap gesture (power-user):**

- Hit area: top-left 96×96 px from the safe-zone edge (visible during revealed-controls state as a `CornerTick` motif at `top:16, left:16`).
- Cycle: Full → Minimap → Minimap+HUD → Full…
- Feedback: 80 ms haptic light tap + 1-frame `accent` pulse on the active segment of the segmented control. This couples the gesture back to the visible UI so the muscle-memory path doesn't go invisible.

**No swipe** — explicitly rejected in legacy distillate because of timeline-scrub conflict. Use Next/Prev episode buttons or the segmented control. UX honors this rejection.

**Unknown-map handling (FR mobile-CINEMA-003):** when the round's `map_name === "unknown"`, the segmented control's "Minimap" and "Minimap+HUD" segments are rendered disabled (text in `dim`, no border, no haptic on tap-attempt) with a small `Stamp` "ROI INDISPONIBLE" beneath. View defaults to Full and stays there until the user navigates to a different round. **A11Y:** disabled segments get `accessibilityState={{ disabled: true }}` + a fragment in their accessibility label explaining "ROI minimap indisponible — carte non identifiée."

#### 2.1.3 Bracket-handle drag for clip region

The 30-second clip region (FR mobile-CLIP-001) appears as two `HudBracket` L-shaped corners on the timeline, with a fill overlay between them.

**Touch targets:**

- Each bracket handle has a logical hit area of **44×44 px** even though the visual `HudBracket` component is 14×26 px. The hit area is invisible padding around the visible glyph — required for A11Y-005 (44×44 minimum) and for thumb-friendly drag on the reference Poco X5.
- Drag updates the timeline position in real-time (no debounce — coach scrubs frequently); the bracket follows the finger 1:1.
- Snap behavior: if a bracket lands within 200 ms of a round-boundary or chapter-marker timestamp, snap to it. Visual: brief `accent-dim` glow at the snapped marker.

**Bracket interaction states:**

| State | Visual |
|---|---|
| Idle | `HudBracket` 1px orange L-corner, 14×26 visible, 44×44 hit |
| Hover (no-op on touch) | n/a — touch surface |
| Pressed (drag-start) | Glyph thickens to 2px `accent` + `accent-soft` square fill behind the L; haptic light tap |
| Dragging | Position follows finger; clip region width recomputed live; timestamp tooltip above the bracket showing `MM:SS` |
| Released | Glyph returns to idle; haptic light tap; if width > 60 s, automatically clamps to 60 s max (PRD does not bind a max — UX picks 60 s as a reasonable upper bound for V1; flag as confirmable; 30 s default per PRD remains the centered initial value) |

**Region-too-short (< 5 s)** — when bracket drag would result in a clip region < 5 s, snap-back animation to 5 s minimum + transient toast: "Clip minimum 5 secondes". UX picks 5 s as the lower bound based on Discord's inline-preview minimum-meaningful-clip; reasonable to confirm.

#### 2.1.4 Voice recorder UI states

3-slot voice recorder (FR mobile-CLIP-003) — before / during / after — independent and optional. Each slot has 4 visual states. Single source-of-truth: the `Stamp` motif from HUD primitives + the existing `AudioRecorder.tsx` composition.

**Slot row layout (bottom-sheet ≤ 40% screen):**

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  AVANT          ┌──────────┐    [▶ preview] [✕ supprimer] │   │
│  │  (still frame:  │  [●] 0:03 │                              │   │
│  │   first frame   └──────────┘                              │   │
│  │   of clip)                                                │   │
│  └───────────────────────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  PENDANT         [Tap pour enregistrer]                   │   │
│  └───────────────────────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  APRÈS           [Tap pour enregistrer]                   │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

**Per-slot states:**

| State | Visual | Non-color signal (A11Y-006) |
|---|---|---|
| **Idle / Empty** | `Field` row with slot label uppercase mono ("AVANT" / "PENDANT" / "APRÈS"); right-side ghost-button "Tap pour enregistrer" with mic icon outline | Mic icon outline + uppercase label; no recording dot |
| **Recording — Before/After** | Still frame thumbnail (first / last frame of clip) fills slot row left half; right half: red filled circle (`error #EF4444`) + blinking-mic icon (icon + visibility-toggle, NOT animation alone) + duration counter `MM:SS` in mono | Red filled circle + blinking-mic icon (icon visibility toggles 750 ms on / 750 ms off — not pure opacity ramp; works for users with reduced-motion AND with motion sensitivity) + ascending duration counter |
| **Recording — During** | Live video plays in main player overlay; bottom-sheet's PENDANT row turns into a live-recording bar with red filled circle + duration counter; if coach keeps talking past clip end, last frame freezes in the player while the duration counter keeps advancing | Red filled circle + duration counter; "OVERFLOW" `Stamp` badge appears when recording extends past clip end |
| **Filled (recorded)** | Mono duration `0:03`; play-icon button + delete-icon button; row background `elev2` (slightly elevated to signal "data here") | Filled `accent` border on the mono duration chip + tactile-icon controls visible |

**Tap-to-start, tap-to-stop** — no auto-stop, no silence detection (legacy distillate). Coach explicitly controls each slot.

**Re-record (FR mobile-CLIP-004):** tap a "Filled" slot's mic icon → confirmation toast "Réenregistrer ? L'enregistrement précédent sera remplacé." with [Annuler] [Réenregistrer] actions. UX picks confirmation-rather-than-destructive because voice annotations carry coaching intent and accidental overwrite is high-cost.

**Silent clips skip all voice slots** — leaving all three slots in "Idle / Empty" produces a clip with zero voice segments. The exporter handles this without UX intervention.

#### 2.1.5 Episode navigation (Next / Previous / Maps)

PRD: explicit Next / Previous / Maps buttons; swipe gestures rejected for Cinema Mode. UX places these at the top bar (revealed-controls state):

```
[×]  [◀ PRÉCÉDENT]  [SILVA · M3]  [SUIVANT ▶]  [⋮]
```

- Center label is `subhead-mono` 12 with 2 letter-spacing; reads "MAP_NAME · Mn" where `n` is the round index in the session.
- "Maps" overflow (`⋮`) opens a bottom-sheet (≤ 40% screen) with the full Card grid — a quick-jump for sessions with > 8 rounds.

### 2.2 Card View triage UX — Decision #UX-5 RESOLVED

`CardViewScreen` is the episode triage grid (FR mobile-CARD-001..005). Two-layer architecture: Card View (this) + Cinema Mode (§2.1).

#### 2.2.1 Cold-start two-path layout

When the user has zero in-progress sessions, the screen renders the two-path layout (NEVER blank):

```
┌──────────────────────────────────────────────────────────────────┐
│  ╔═════════╗                                          [⚙]        │
│  ║ WARDEN  ║                                                     │ ← top brand strip
│  ╚═════════╝                                                     │
│                                                                  │
│                                                                  │
│         ┌───────────────────────────────────────────┐            │
│         │                                           │            │
│         │   [▶]  REPRENDRE LA DERNIÈRE              │            │ ← Resume CTA
│         │        SESSION                            │            │   (only when prefs.lastSessionId exists)
│         │                                           │            │
│         └───────────────────────────────────────────┘            │
│                                                                  │
│         ┌───────────────────────────────────────────┐            │
│         │                                           │            │
│         │   [+]  IMPORTER UNE NOUVELLE SESSION      │            │ ← Import CTA (always)
│         │                                           │            │
│         └───────────────────────────────────────────┘            │
│                                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Variants:**

- If **zero sessions ever imported** → show only the Import CTA, full-width, with a single `body` line above: "Importez votre première session d'entraînement."
- If **one in-progress session exists** → show both CTAs; Resume is the primary (filled `EngageButton`), Import is secondary (outline `EngageButton`).
- If **multiple sessions exist** → skip the cold-start layout entirely and render the grid (§2.2.2) with the top bar's `[+]` button as the import affordance.

#### 2.2.2 Grid layout (adaptive columns)

| Screen size | Columns | Card aspect | Margins |
|---|---|---|---|
| 5.5" | **1** | 16:9 thumbnail + 64-px label strip below | Edge 16; gap 12 |
| 6.0–6.4" | **2** | 16:9 thumbnail + 56-px label strip | Edge 16; gap 8 |
| 6.5"+ (incl. Poco X5 6.67") | **2 with more metadata** | 16:9 thumbnail + 72-px label strip showing extra `Stamp` row (round number, duration) | Edge 16; gap 8 |

Grid scrolls vertically; pull-to-refresh re-runs the auto-slice index check (does NOT re-process the video — only refreshes the SQLite read).

#### 2.2.3 Per-card composition

```
┌───────────────────────────────────────┐
│  ┌─────────────────────────────────┐  │
│  │                                 │  │ ← 16:9 result-frame thumbnail
│  │   [scoreboard frame as image]   │  │   (from map_segments.result_frame_path)
│  │                                 │  │
│  │  ┌──────────┐                   │  │
│  │  │ M3       │ ← `Stamp` round   │  │   round index overlay (top-left)
│  │  └──────────┘   index           │  │
│  │                                 │  │
│  │                                 │  │
│  │                       ┌───────┐ │  │
│  │                       │ 11-13 │ │  │   score V2-degrades-gracefully
│  │                       └───────┘ │  │   (rendered only when score_orange/score_blue NOT NULL)
│  │                                 │  │
│  └─────────────────────────────────┘  │
│  ┌─────────────────────────────────┐  │
│  │  SILVA          0:42 → 4:18     │  │ ← label strip:
│  │                                 │  │   subhead-mono map name + mono time-range
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

**Score rendering rules (mobile-CARD-002 V2-graceful-degradation):**

- **V1 (no OCR)** → score chip is hidden; sort dropdown's score-based options gracefully degrade to temporal sort (no error, no warning — silently temporal). The card label strip shows only map name + time range.
- **V2 (when OCR ships)** → score chip appears bottom-right of thumbnail; `value-mono 13` with `accent` digits when card is sorted-by-score, `text` otherwise.

#### 2.2.4 "Unknown map" card visual treatment — Decision #UX-11 (mobile)

When a round's `map_name === "unknown"` (FR mobile-AUTO-SLICE-003), the card renders distinctly so the coach knows graceful degradation kicked in but navigation still works:

```
┌───────────────────────────────────────┐
│  ┌─────────────────────────────────┐  │
│  │                                 │  │
│  │   [scoreboard frame OR last     │  │
│  │    extracted frame as image,    │  │
│  │    desaturated 60%]             │  │
│  │                                 │  │
│  │  ┌──────────┐                   │  │
│  │  │ M? · ?   │ ← `Stamp` with    │  │   "?" instead of round index when ambiguous
│  │  └──────────┘   "?" markers     │  │
│  │                                 │  │
│  │  ┌─────────────────────────┐    │  │
│  │  │  CARTE NON IDENTIFIÉE   │    │  │ ← `Stamp` overlay center-bottom
│  │  └─────────────────────────┘    │  │   (1px `dim` border, no fill, mono uppercase)
│  └─────────────────────────────────┘  │
│  ┌─────────────────────────────────┐  │
│  │  CARTE INCONNUE     0:42 → 4:18 │  │ ← `text-muted` instead of `text` for label
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

**A11Y-006 non-color signal:** the "CARTE NON IDENTIFIÉE" stamp + the desaturated thumbnail + the "?" round-index marker + the muted label-strip color combine to make the unknown-state visible across grayscale, color-blind, and reduced-saturation rendering. Card remains tappable; opens Cinema Mode in `Full` view (Minimap/Minimap+HUD segments disabled per §2.1.2).

#### 2.2.5 Sort dropdown surface

Four sort options (FR mobile-CARD-002): Temporal (default) · Plus gros écart Orange · Plus gros écart Bleu · Carte la plus proche.

Surface: top-bar trailing icon `[⋮ TRIER]` opens a bottom-sheet (≤ 40% screen) with radio-button list:

```
┌──────────────────────────────────────────────┐
│                                              │
│  ◉ TEMPOREL (PLUS RÉCENT)        ← default   │
│  ○ PLUS GROS ÉCART · ORANGE  [V2]            │
│  ○ PLUS GROS ÉCART · BLEU    [V2]            │
│  ○ CARTE LA PLUS PROCHE      [V2]            │
│                                              │
│              [APPLIQUER]                     │
│                                              │
└──────────────────────────────────────────────┘
```

**`[V2]` chip** appears next to the three score-based options in V1 — visible signal that the option exists conceptually but defaults to temporal until OCR ships in V2. Tapping a `[V2]` option in V1 sorts temporally and shows a transient toast: "Tri par score disponible avec V2 (OCR)." UX-1 A11Y compliance: chip is `Stamp`-styled (text + box, not color-only).

Sort persists via `prefs.sortOrder` (MMKV); the chosen sort sets next/prev order in Cinema Mode (legacy distillate).

#### 2.2.6 Top bar in grid mode

```
[+ IMPORTER]   [WARDEN wordmark]   [⋮ TRIER]   [⚙ COMPTE]
```

`COMPTE` opens a bottom-sheet with: account email · entitlement state chip · "Gérer mon abonnement" deep-link to web Customer Portal · "Se déconnecter" button. **No price displayed anywhere.**

### 2.3 Loading / processing UX — Decision #UX-6 RESOLVED

Processing UX has two regimes — short (synchronous, inline) and long (asynchronous, full-screen) — already specified in legacy distillate.

#### 2.3.1 Short processing (< 3 s expected)

Inline overlay over the action that triggered it. Examples: clip preview generation, sort re-application, view-mode switch (PERF-003 ≤ 100 ms is so fast it doesn't trigger this UI; only kept as fallback for slower hardware).

```
┌────────────────────────────────────┐
│        [○ rotating reticle]        │ ← `Reticle` spin (mocks reduce to "PROCESSING…" stamp when reduced-motion)
│                                    │
│      PRÉPARATION DU CLIP…          │
└────────────────────────────────────┘
```

Auto-dismisses on completion. No retry CTA — too short to be worth it. Failure surfaces via toast (§2.6).

#### 2.3.2 Long processing (≥ 3 s — auto-slice path)

Full-screen `ProcessingScreen` with progress + rotating tips. Architecture-bound: Foreground Service notification "Analyse en cours…" with progress percentage shows simultaneously in Android system tray, sourced from MMKV `processing.<sessionId>.stage`.

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ╔════════════════════════════════════════════╗                  │
│  ║ ANALYSE EN COURS                          ║ ← heading-mono 16 │
│  ╚════════════════════════════════════════════╝                  │
│                                                                  │
│         ┌──────────────────────────────────────────┐             │
│         │ ████████████████░░░░░░░░░░░░░░░░░░░ 47% │             │ ← progress
│         └──────────────────────────────────────────┘             │
│                                                                  │
│         IDENTIFICATION DES CARTES · 12 / 24 ROUNDS               │ ← stage label
│                                                                  │
│                                                                  │
│         ┌──────────────────────────────────────────┐             │
│         │  ASTUCE                                  │             │
│         │                                          │             │ ← rotating tip
│         │  Double-tap en haut à gauche pour        │             │   (5–8 s cadence;
│         │  basculer en vue minimap.                │             │    fade-out 200 ms,
│         │                                          │             │    fade-in 200 ms)
│         └──────────────────────────────────────────┘             │
│                                                                  │
│                                                                  │
│              [METTRE EN PAUSE]   [ANNULER]                       │ ← controls
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Tip rotation cadence:** 6 s (mid-point of legacy 5–8 s window). Fixed cadence is more predictable than randomized for users with attention-pattern sensitivity. UX picks 6 s; flag as confirmable.

**V1 tip set (5 strings — Decision #UX-2 maps):**

1. `Double-tap en haut à gauche pour basculer en vue minimap.`
2. `Faites glisser les poignées du clip pour ajuster la durée.`
3. `Ajoutez votre voix avant, pendant ou après le clip.`
4. `Triez par "carte la plus proche" pour les rounds importants.`
5. `Votre progression est sauvegardée automatiquement.`

Tips loop in this order. **A11Y-006:** the "ASTUCE" header `Stamp` provides a non-color signal that the bottom region's content is informational, not actionable.

**Process control buttons:**

- `[METTRE EN PAUSE]` — pauses processing; preserves state in MMKV; the user can leave the app and resume later. Foreground Service notification updates to "Analyse en pause."
- `[ANNULER]` — modal confirmation: "Annuler l'analyse ? Les segments déjà identifiés seront conservés en l'état." with [Continuer l'analyse] [Annuler l'analyse]. Cancellation preserves whatever segments completed (graceful degradation per FR mobile-CARD-005); the unanalyzed remainder of the source video stays accessible via Cinema Mode timeline → manual-clip flow (§2.4).

#### 2.3.3 Pipeline-error retry CTA

When the auto-slice pipeline errors mid-run (FFmpeg failure, OpenCV JSI exception, MMKV write failure):

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│         ┌──────────────────┐                                     │
│         │  [⚠] (icon)      │                                     │
│         └──────────────────┘                                     │
│                                                                  │
│         L'ANALYSE A ÉCHOUÉ                                       │
│                                                                  │
│         Une erreur est survenue à l'étape :                      │
│         IDENTIFICATION DES CARTES                                │
│                                                                  │
│         Vous pouvez réessayer ou continuer en mode               │
│         manuel — les rounds déjà identifiés sont                 │
│         conservés.                                               │
│                                                                  │
│                                                                  │
│            [RÉESSAYER]   [CONTINUER EN MANUEL]                   │
│                                                                  │
│                                                                  │
│         (Détails techniques)                                     │ ← collapsed by default
│         ─────────────────────────                                │
│         Code: OPENCV_JSI_FAIL                                    │
│         Stage: map_identification                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Two paths:**

- `[RÉESSAYER]` — re-runs from the last MMKV checkpoint (architecture's 4-stage MMKV checkpointing in `processingPipeline.ts`). Returns to ProcessingScreen.
- `[CONTINUER EN MANUEL]` — closes ProcessingScreen, opens Card View with whatever segments completed; the unanalyzed remainder is accessible via the timeline manual-clip flow (§2.4).

**A11Y-006 non-color signal:** triangle warning icon (`⚠`) is the primary non-color signal; the `dim`-bordered "Détails techniques" disclosure accordion provides a non-color "this section is a footnote" cue.

The error screen uses `error #EF4444` for the warning icon and a thin 1px `accent-dim` border around the action buttons — but the screen does NOT rely on the red color to convey error state; the icon shape + heading text + paragraph copy carry the meaning.

### 2.4 Manual-clip-from-timeline flow — Decision #UX-14 RESOLVED

**This flow is FIRST-CLASS V1 navigation, not graceful degradation**, per Innovation #1 fallback ladder rung 3. If the architecture's pre-PRD performance spike returns rung 3 (auto-slice deferred to V2), the manual-clip path is the only clip-creation path V1 ships with. Therefore UX designs it as a permitted V1 path on equal footing with the auto-sliced Card → Cinema → Clip flow.

#### 2.4.1 Two equal entry points to Cinema Mode

**Entry 1 (auto-sliced path):** `CardViewScreen` → tap card → `CinemaModeScreen` opens at the card's start timestamp with view-mode + segmented control fully active.

**Entry 2 (manual / unknown path):** `CardViewScreen` → tap "TIMELINE" mode toggle in the top bar → `CinemaModeScreen` opens at `00:00` with the full session timeline visible end-to-end (no per-round segments, no Card-bound start/end). The user scrubs to the moment of interest.

**Card View ↔ Timeline toggle in the top bar:**

```
[+ IMPORTER]   [⊞ CARDS │ ☰ TIMELINE]   [⋮ TRIER]   [⚙ COMPTE]
                  ▲              ▲
                  default        manual flow (Decision #UX-14)
```

- `⊞ CARDS` — auto-sliced grid (default).
- `☰ TIMELINE` — full-session timeline (no Cards). Available in V1 always, even when auto-slice ran cleanly. **In rung-3 fallback (no auto-slice in V1), the toggle defaults to TIMELINE and the CARDS option is hidden.** The same `CinemaModeScreen` component handles both paths.

**Why a toggle and not a separate screen:** keeps the Card View → Cinema → Clip → Export flow compositionally identical regardless of whether segments are auto-sliced or manually scrubbed. The timeline mode is a different entry into the same `CinemaModeScreen`, not a different screen.

#### 2.4.2 Manual-clip flow inside Cinema Mode

Identical to §2.1.3 bracket-handle drag, with two adaptations:

1. **No round-boundary snap markers** — the timeline has no `map_segments`, so bracket drag operates over raw video time.
2. **Top-bar centerlabel reads "MANUEL · 00:42"** instead of "SILVA · M3" — the user is operating on raw video time, not a round.

The user taps "clip" anywhere on the timeline → 30-second region appears centered on the playhead → drag to refine → 3-slot voice → Export. The export pipeline does not differentiate manual-clip from auto-clip; the artifact is identical.

#### 2.4.3 Unknown-map round → manual-clip handoff

When the user opens an "unknown" Card (§2.2.4), Cinema Mode loads in `Full` view with the bracket-handle clip flow fully active. The user scrubs and clips manually within the round. This is the same manual-clip flow with a known time-range constraint (the round's start/end timestamps from `map_segments`).

### 2.5 Six-state entitlement visual states — Decision #UX-1 RESOLVED (per state)

The six states are PRD-bound; UX designs the visual treatment for each. Architecture default `paymentFailedGracePeriodMs: 7d` carried forward.

#### 2.5.1 `paid` — fully usable, no banner

No visual chrome. The Home / Cinema / Clip / Export screens render as documented in §§2.1–2.4 with no state indicator. The only signal that entitlement is `paid` is the absence of the other states' chrome.

#### 2.5.2 `offline-grace ≤30d` — fully usable, subtle indicator

Subtle iconography in the top brand strip area:

```
[+ IMPORTER]   [WARDEN]  [⊘ HORS LIGNE]   [⋮ TRIER]   [⚙ COMPTE]
                            ▲
                            offline indicator
```

`[⊘ HORS LIGNE]` is a `Stamp`-styled chip with 1px `dim` border, `text-muted` foreground, no fill, mono `subhead-mono` 12 size, leading icon `⊘` (offline-disconnected). Tap the chip → bottom-sheet (≤ 40%) with: "Mode hors ligne. Dernière synchronisation: il y a 3 jours. Vos clips et annotations sont enregistrés localement et seront synchronisés au prochain démarrage en ligne."

**Day-29 / day-30 escalation:** when `cachedAt` age is within 24 h of the 30-day expiry, the chip's border thickens to 2px and color shifts to `accent` (orange) to signal "your offline cache is about to expire." Bottom-sheet copy adapts: "Mode hors ligne. Cache d'authentification expire bientôt — merci de vous reconnecter dès que possible pour ne pas être déconnecté."

**A11Y-006 non-color signal:** `⊘` icon shape is the primary signal (offline = disconnected glyph); the chip's mono text "HORS LIGNE" is the secondary; color is tertiary.

#### 2.5.3 `payment-failed` — usable with warning banner

`EntitlementBanner.tsx` (NEW per architecture) overlays Home and Cinema. Persistent until state transitions back to `paid` or out to `lapsed`:

```
┌──────────────────────────────────────────────────────────────────┐
│ [⚠] MISE À JOUR DU MOYEN DE PAIEMENT NÉCESSAIRE                  │
│     Votre dernier paiement a échoué. Mettez à jour votre carte   │
│     pour conserver l'accès à Warden.                             │
│                                          [METTRE À JOUR] [×]     │
└──────────────────────────────────────────────────────────────────┘
```

**Colors:** `warning #F59E0B` 1px border + `warning`-with-15%-alpha fill. Background does not use red — `payment-failed` is a soft state, not a hard error. The amber color signals "attention, but not blocked."

**`[METTRE À JOUR]`** — primary CTA, orange-fill `EngageButton`, deep-links to web Stripe Customer Portal via universal-link / Custom Tabs. **MUST NOT show the price** — the banner copy uses no euro signs, no plan names, no pricing language. Reader-App CI gate enforces.

**`[×]`** — dismisses the banner for the current foreground session (re-appears on next foreground if state still `payment-failed`). Architecture's `paymentFailedGracePeriodMs: 7d` means the user has 7 days from `past_due` to resolve before transitioning to `lapsed`; the banner's dismissibility is a UX concession to "I know, I'm working on it" without forcing repeated impressions in the same session.

**A11Y-005:** banner height ≥ 88 px (covers two lines + two action buttons + icon at 44×44 each) → all touch targets pass A11Y-005. Icon `⚠` is the non-color primary signal.

**Foreground re-fetch (architecture-bound):** banner appears immediately on foreground when entitlement re-fetch returns `past_due`; banner disappears immediately when re-fetch returns `active`.

#### 2.5.4 `lapsed` — unusable, full-screen "subscription required"

`SubscriptionRequiredScreen.tsx` replaces the entire app shell:

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                                                                  │
│           ╔═════════╗                                            │
│           ║ WARDEN  ║                                            │ ← brand
│           ╚═════════╝                                            │
│                                                                  │
│                                                                  │
│         ┌──────────────────┐                                     │
│         │  [⊗] (icon)      │                                     │ ← lapsed icon
│         └──────────────────┘                                     │
│                                                                  │
│                                                                  │
│         ABONNEMENT REQUIS                                        │
│                                                                  │
│         Votre abonnement est expiré ou annulé.                   │
│         Renouvelez-le pour reprendre vos analyses.               │
│                                                                  │
│         Vos sessions, clips et annotations restent               │
│         conservés et seront restaurés automatique-               │
│         ment.                                                    │
│                                                                  │
│                                                                  │
│              [GÉRER MON ABONNEMENT]                              │ ← deep-link to web
│                                                                  │
│                                                                  │
│              [SE DÉCONNECTER]                                    │ ← secondary
│                                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**MUST NOT show price** — the screen does not include "€7.99", "monthly", "yearly", "subscribe" or any banned string. Reader-App CI gate enforces. The `[GÉRER MON ABONNEMENT]` CTA deep-links to web Customer Portal where pricing IS shown (web is not Reader-App-gated).

**Reassurance copy** — "Vos sessions, clips et annotations restent conservés et seront restaurés automatiquement" addresses FR mobile-AUTH-005 (preserve session data across lapse → resubscribe). Reduces the cancel-then-fear cycle.

**A11Y-005/006:** `⊗` icon shape is the non-color primary signal; the heading "ABONNEMENT REQUIS" is uppercase mono with `text` color (not colored); CTAs are 88-px tall (well over 44×44).

#### 2.5.5 `multi-device` — fully usable, no special state

Per PRD: entitlement is per-user, not per-device. UX has no chrome for this state — same as `paid`. Multi-device installations show the same Cinema Mode, same Card View, same export tier — each device just reads `users/{uid}.status === "active"` independently.

#### 2.5.6 `signed-out` — login screen only

When the MMKV cache is empty / expired (day-31 architecture-bound force re-auth):

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                                                                  │
│           ╔═════════╗                                            │
│           ║ WARDEN  ║                                            │ ← brand wordmark, display-mono
│           ╚═════════╝                                            │
│                                                                  │
│                                                                  │
│         CONNEXION                                                │ ← heading-mono
│                                                                  │
│                                                                  │
│         ┌──────────────────────────────────────────┐             │
│         │  [G]  Continuer avec Google              │             │ ← Google sign-in
│         └──────────────────────────────────────────┘             │
│                                                                  │
│                       — OU —                                     │
│                                                                  │
│         ┌──────────────────────────────────────────┐             │
│         │  Adresse email                           │             │
│         └──────────────────────────────────────────┘             │
│         ┌──────────────────────────────────────────┐             │
│         │  Mot de passe                       [👁]  │             │ ← password field with show/hide
│         └──────────────────────────────────────────┘             │
│                                                                  │
│                                                                  │
│              [SE CONNECTER]                                      │
│                                                                  │
│                                                                  │
│         Pas encore d'abonnement ?                                │
│         Créez un compte sur warden.team →                        │ ← deep-link to web
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**MUST NOT show price.** The "Pas encore d'abonnement ?" line directs users to web for sign-up — Reader-App-compliant.

**Google button** — uses `GoogleSignInButton` patterns from `@react-native-google-signin` (Web client ID flow per architecture). Visual: 1px `border` on `surface-elevated` background; left-side Google "G" icon at 18×18; right-side label "Continuer avec Google" in `body` text. Must follow Google brand guidelines (Google policy is a legal constraint, not a design preference).

**Day-31 force re-auth path** — when the user lands here from cache expiry, prepend a transient toast: "Pour des raisons de sécurité, merci de vous reconnecter."

### 2.6 Mobile state pattern catalog — Decision #UX-1 RESOLVED (A11Y-005/006)

PRD locks: every state has shape/icon/content change as primary signal — never color alone. UX produces the explicit pattern catalog. All icons are filled or outline glyphs from the existing `Icon.tsx` HUD primitive set; if a glyph isn't yet in the set, it gets added (no library icons used in mobile).

| State | Primary non-color signal (icon) | Secondary signal | Color | Touch target audit |
|---|---|---|---|---|
| Recording (voice slot) | Filled circle `●` + blinking-mic icon (visibility-toggle 750 ms on / off, NOT animation alone) | "REC" mono `Stamp` chip | `error #EF4444` filled circle | Mic-button 88×88 (4-edge padded around 44×44 visible) |
| Recording overflow (during slot extends past clip end) | "OVERFLOW" `Stamp` chip + frozen-frame thumbnail | Duration counter keeps advancing | `accent #FF6B00` for the overflow chip | Stop-button 88×88 |
| Payment-failed banner | `⚠` triangle outline icon | "MISE À JOUR…" heading + amber border | `warning #F59E0B` | "METTRE À JOUR" button 56×144 (well over 44×44) |
| Offline-grace (ambient) | `⊘` offline-disconnected glyph in `Stamp` chip | "HORS LIGNE" mono label + chip border | `dim` (low-key) → `accent` (escalation) | Chip 44×88; tap opens bottom-sheet (44×120 hit) |
| Lapsed / signed-out (full-screen) | `⊗` lapsed glyph at 64×64 center-stage | "ABONNEMENT REQUIS" heading | `dim` icon (no red, no orange) | Primary CTA 56×220 |
| Processing (long) | `Reticle` 4-prong dashed ring rotating | "ANALYSE EN COURS" heading + progress bar + percentage label | `accent` for ring + bar | Pause/Cancel buttons 56×144 |
| Processing (short / inline) | Spinning `Reticle` (or static "PROCESSING…" `Stamp` when reduced-motion) | Action label "PRÉPARATION DU CLIP…" | `accent` | n/a — read-only state |
| Pipeline error | `⚠` triangle filled icon at 56×56 | "L'ANALYSE A ÉCHOUÉ" heading + stage label | `error` for icon | Retry/Continue buttons 56×144 each |
| Codec unsupported | `⊗` denied glyph 48×48 | "FORMAT NON COMPATIBLE" heading + format details | `error` icon, `text` heading | OK button 56×144 |
| Resume-session toast | `↶` resume-arrow glyph | "REPRISE: M3 SILVA · 00:42" mono | `accent` glyph + `text` body | Toast non-interactive (read-only) |
| Share-complete toast | `✓` check-mark glyph | "CLIP PARTAGÉ" mono | `success #22C55E` glyph | Toast non-interactive |
| Unknown map (Card) | "?" round-marker `Stamp` + desaturated thumbnail + "CARTE NON IDENTIFIÉE" `Stamp` overlay | `text-muted` label-strip | `dim` border | Card 200×356 (full Card hit) |
| ROI unavailable (Cinema unknown map) | Disabled segmented-control segments + "ROI INDISPONIBLE" `Stamp` | Mono `dim` text on segments | `dim` | Segments remain 44 tall, tap is no-op + label-only signal |
| Foreground Service notification (Android tray) | App icon + persistent notification surface | "Analyse en cours…" heading + progress percentage | System tray colors | OS-handled |
| Foreground Service paused | App icon + "Analyse en pause" copy | — | System tray colors | OS-handled |

**Touch-target audit summary:** every interactive element on every mobile screen passes A11Y-005 (≥ 44×44 px). HUD primitives `HudBracket`, `CornerTick`, `Stamp` use invisible padding around their visible glyph to meet 44×44 hit-area while keeping the 1-px tactical-line aesthetic.

**A11Y-006 compliance summary:** every state in the catalog has an icon-shape primary signal that survives grayscale, color-blind, and reduced-saturation rendering. No state relies on color alone. Reduced-motion respect is built into the recording-blink (visibility-toggle, not opacity ramp) and the long-processing reticle (falls back to static `Stamp` when reduced-motion is enabled).

### 2.7 Mobile feedback patterns (consolidated)

Inherited from legacy distillate, restated here as the binding pattern:

| Feedback type | Cadence | Surface | A11Y signal |
|---|---|---|---|
| Success toast (e.g., "CLIP PARTAGÉ") | 3 s auto-dismiss | Bottom toast | `✓` icon + mono uppercase + `success` color; no color-only |
| Minor error toast (e.g., "Tri par score disponible avec V2") | 5 s auto-dismiss | Bottom toast | `⚠` icon + mono uppercase + `error` color; no color-only |
| Critical error blocking modal (e.g., codec unsupported) | Until user tap | Center modal | `⊗` icon + heading + body + acknowledgement CTA |
| Warning banner (e.g., payment-failed, offline-cache-near-expiry) | Persistent until state changes | Top inline banner | `⚠` or `⊘` icon + mono heading + action CTA |
| Bottom-sheet | User-dismissed (drag-down or backdrop tap) | ≤ 40% screen height; never covers video | Border on top edge in `accent` 1px to mark sheet boundary |

**Gesture rules (legacy distillate, binding):** every gesture has a button equivalent. No hidden gestures required for core flows. Double-tap top-left view-mode cycle (§2.1.2) is an additive power-user gesture, not a required path.

---

## 3. Web Interaction Patterns

This section lands Decisions #UX-7 (web payment-failure / cancellation), #UX-8 (web auth modal), #UX-9 (Discord OG card), #UX-10 (cookie banner), #UX-11-web (empty state). All visual treatments inherit Direction A "Clean Minimal" tokens from §1.5 and the 7 shadcn primitives from §1.6.

Three routes — `/`, `/pricing`, `/dashboard` — plus `/privacy` + `/terms`. Stripe-hosted Checkout and Stripe Customer Portal are full-page redirects, not embedded.

### 3.1 Web auth modal pattern — Decision #UX-8 RESOLVED

PRD-bound: lazy auth (don't ask sign-in until user picks plan). UX picks **modal overlay** (not page-navigation):

- The user lands on `/pricing`, picks a plan card → modal Dialog overlays without navigation. Reason: page-navigation away from `/pricing` would lose the plan-selection state and re-fetch the route; the auth modal preserves the selected plan via `CheckoutContext`.
- The auth modal is built directly from shadcn `Dialog` + `Input` + `Button` primitives (no new component for V1 per §1.6).

#### 3.1.1 Modal layout

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────────┐      │
│  │                                                    [×] │      │
│  │  Sign in to subscribe                                  │      │ ← H2 24/700
│  │                                                        │      │
│  │  Selected plan: Yearly · €79.90 (économisez 2 mois)    │      │ ← small 14/500
│  │                                                        │      │
│  │  ┌──────────────────────────────────────────────────┐  │      │
│  │  │  [G]  Continue with Google                       │  │      │ ← orange-fill button
│  │  └──────────────────────────────────────────────────┘  │      │
│  │                                                        │      │
│  │                       — or —                           │      │ ← divider with text-secondary
│  │                                                        │      │
│  │  Email address                                         │      │
│  │  ┌──────────────────────────────────────────────────┐  │      │
│  │  │  you@example.com                                 │  │      │
│  │  └──────────────────────────────────────────────────┘  │      │
│  │                                                        │      │
│  │  Password                                              │      │
│  │  ┌──────────────────────────────────────────────────┐  │      │
│  │  │  ••••••••••••                              [👁]   │  │      │
│  │  └──────────────────────────────────────────────────┘  │      │
│  │                                                        │      │
│  │  ☐ Create new account (8+ characters)                  │      │ ← inline mode toggle
│  │                                                        │      │
│  │  ┌──────────────────────────────────────────────────┐  │      │
│  │  │              Continue to checkout                │  │      │ ← primary CTA
│  │  └──────────────────────────────────────────────────┘  │      │
│  │                                                        │      │
│  │  By continuing, you agree to our Terms and Privacy.    │      │ ← legal link copy
│  │                                                        │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                  │
│  (backdrop: bg with 70% opacity overlay)                         │
└──────────────────────────────────────────────────────────────────┘
```

**Modal width:** 480 px on desktop, full-width with 16 px page padding on mobile. Centered vertically on desktop, anchored 80 px from top on mobile to avoid keyboard occlusion.

#### 3.1.2 Transition — minimal motion (no animation)

Direction A "Clean Minimal" rejects animated illustrations and Lottie. UX matches: the modal appears with **no enter/exit animation** beyond the standard Radix `Dialog` 100 ms opacity fade (which Radix respects `prefers-reduced-motion` automatically). No transform, no scale, no slide — just opacity.

#### 3.1.3 Google Sign-In button

Per Google brand guidelines:

- **Background**: orange-fill (Warden primary CTA) — Google permits non-white backgrounds for OAuth buttons as long as the "G" logo is the official multicolored mark and the button label is unambiguous.
- **"G" logo**: official Google "G" multicolored SVG, 18×18 px, left-aligned, 16 px from left edge.
- **Label**: "Continue with Google" (English; this is web), Inter 16/500.
- **States**: hover → `accent-hover` background; focus → 2 px orange focus-visible outline (matches A11Y-002).

#### 3.1.4 Sign-in vs sign-up mode

Single modal handles both. Default mode is **sign-in**. The "☐ Create new account" checkbox toggles to sign-up mode:

- Unchecked → "Continue to checkout" attempts `signInWithEmailAndPassword`. If user doesn't exist → inline error: "No account found. Tick 'Create new account' to register."
- Checked → "Continue to checkout" attempts `createUserWithEmailAndPassword`. Validates 8+ characters; rejects emails already-in-use with: "An account with this email already exists. Sign in instead."

Rationale: a single composable modal means one component path, one set of shadcn `Dialog` + `Input` + `Button` primitives, no separate "/sign-up" route. Matches the "no custom components for V1" §1.6 constraint.

#### 3.1.5 Error message presentation

Per A11Y-003 (text + color, never color-only): inline error appears directly under the field that triggered it, prefixed with an `error #EF4444` filled circle icon (8×8 px, 4 px right-margin) + `error` color text. Examples:

| Trigger | Inline error text |
|---|---|
| Email format invalid | `● Please enter a valid email address.` |
| Password too short (sign-up mode) | `● Password must be 8 characters or more.` |
| Wrong password (sign-in mode) | `● Incorrect password. Try again or reset.` (with "reset" as a link to TODO V1.1 — V1 has no password-reset; the link routes to "contact support" per Decision #UX-12) |
| Account locked (Firebase rate-limit) | `● Too many attempts. Try again in a few minutes.` |
| Network error | `● Connection error. Check your internet and retry.` |

**Reset password — V1 LOCKED 2026-05-07:** V1 ships with password reset via Firebase `sendPasswordResetEmail`. The auth modal includes a `Forgot password?` link directly under the password field; clicking opens a small inline state inside the same modal:

```
┌────────────────────────────────────────────────────────┐
│  Reset password                                    [×] │
│                                                        │
│  Enter your account email. We'll send a password       │
│  reset link.                                           │
│                                                        │
│  Email address                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  you@example.com                                 │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Send reset link                     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ← Back to sign in                                     │
└────────────────────────────────────────────────────────┘
```

On submit → Firebase sends the hosted reset email → success state inside the modal: `Check your email for a reset link.` Below it: `← Back to sign in`. The user clicks the link in the email → Firebase-hosted reset page → completes reset → user lands on `/auth/sign-in?passwordReset=1` → auth modal opens with success banner: `Password updated. Sign in.` pre-filled with the email address used. Implementation surface: `apps/web/src/components/auth/PasswordResetForm.tsx` — composition from `Dialog` content slot + `Input` + `Button` (no new primitive component). Tracked at §6.5.

### 3.2 Web payment-failure / cancellation UX — Decision #UX-7 RESOLVED

#### 3.2.1 Status badge color mapping

PRD + legacy distillate-bound:

| Entitlement state | Badge color | Badge label | Icon (A11Y-003) |
|---|---|---|---|
| `paid` (active) | `success #22C55E` | `Active` | `●` filled circle |
| `payment-failed` (`past_due`) | `warning #F59E0B` | `Past due` | `⚠` triangle outline |
| `canceling` (`cancel_at_period_end: true`) | `text-secondary` (gray) | `Canceling` | `⊘` slash glyph |
| `lapsed` (`canceled`) | `error #EF4444` | `Canceled` | `⊗` denied glyph |

Badges use shadcn `Badge` primitive with text + icon — never color alone. The icon shape is the primary non-color signal.

#### 3.2.2 Payment-failure warning banner

`PaymentWarning` composition built from shadcn `Alert` + `Button` primitives (no new custom component). Renders directly above the `SubscriptionCard` on `/dashboard`:

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  [⚠]  Your last payment failed.                            │  │
│  │       Update your payment method to keep using Warden.     │  │
│  │                                  [Update payment method]   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**Visual:**

- Border: 1 px `warning #F59E0B`.
- Fill: `warning` at 8% opacity over `surface`.
- Heading: "Your last payment failed." Inter 16/600, `text` color.
- Body: 14/400, `text-secondary`.
- CTA: shadcn `Button` variant `default` (orange-fill); deep-links to Stripe Customer Portal session via `POST /api/subscription/portal` → portal URL.
- Persistent (non-dismissible) until state transitions to `paid` or `canceled`. **Why not dismissible:** legacy distillate binds — warning banners with action button persist until resolved. Web persistence is fine because (unlike mobile) the user is in a one-shot session per page-load; no perpetual-impressions concern.

**A11Y-003:** `⚠` icon shape primary signal; "Past due" badge text secondary; amber color tertiary.

#### 3.2.3 Cancel-confirmation dialog

`CancelDialog` built from shadcn `Dialog` + `Button` primitives. Triggered from the `[Cancel subscription]` link inside the `SubscriptionCard`'s overflow menu (legacy distillate binds: cancellation flow stays on web Dashboard with confirmation dialog handoff to portal):

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────────┐      │
│  │                                                    [×] │      │
│  │  Cancel subscription?                                  │      │ ← H2
│  │                                                        │      │
│  │  You'll keep access until 12 August 2026.              │      │ ← static date,
│  │                                                        │      │   resolved from
│  │                                                        │      │   current_period_end
│  │                                                        │      │
│  │              [Keep subscription]   [Cancel]            │      │
│  │                                                        │      │
│  │                                                        │      │
│  │  After cancellation, you can resubscribe at any time   │      │ ← reassurance copy
│  │  on /pricing.                                          │      │
│  │                                                        │      │
│  └────────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
```

**Anti-dark-pattern compliance (J8 — explicit):**

- ❌ NO exit survey ("Why are you cancelling? [reason dropdown]")
- ❌ NO guilt-trip ("We'll miss you" / "Are you sure?")
- ❌ NO double-confirm ("Type CANCEL to confirm")
- ❌ NO countdown timer ("Cancel within 24 hours to lock in this price")
- ❌ NO retention offer modal ("Stay for 50% off")
- ✅ Single dialog with two equal-weight CTAs
- ✅ Static end-of-period date (factual, not emotional)
- ✅ Resubscribe reassurance (factual, not manipulative)

**CTA weight:** "Keep subscription" is the **default visual focus** (shadcn `Button` variant `default` orange-fill, on the right per Western reading order); "Cancel" is the **destructive variant** (ghost red text-only) on the left. Reason: defaulting visual focus to the no-op preserves accidental-click safety without imposing emotional friction. The dialog is symmetric in semantic weight — both options are equally accessible — but the visual default on "Keep" prevents unintended cancellations from misclick.

**On confirm:** `POST /api/subscription/portal` → Stripe Customer Portal opens in same tab → user explicitly confirms cancellation in Stripe's UI → Stripe sets `cancel_at_period_end: true` → webhook fires → user returns to `/dashboard` → status badge flips to `Canceling` (gray).

#### 3.2.4 "Resubscribe" CTA placement post-period-end

When status transitions to `canceled` (period-end webhook fires), the `SubscriptionCard` content rewrites:

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Your subscription                                               │
│                                                                  │
│  Status:  ⊗  Canceled                                            │
│                                                                  │
│  Your subscription ended on 12 August 2026.                      │
│  Your account is preserved — resubscribe anytime to              │
│  restore access to your sessions, clips, and annotations.        │
│                                                                  │
│              [Resubscribe]                                       │ ← primary
│                                                                  │
│  ────────────────────────────────────────────                    │
│                                                                  │
│  [Manage billing] (Stripe Customer Portal — payment history)     │ ← secondary link
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**`[Resubscribe]`** routes to `/pricing`. Mirror copy from §2.5.4 (mobile lapsed screen) reinforces the data-preservation guarantee — coaches who cancel because they're "taking a break" feel safe knowing the data restores.

**`[Manage billing]`** is the shadow link to Stripe Customer Portal for users who want their invoice history post-cancellation.

### 3.3 Discord-card-preview Open Graph spec — Decision #UX-9 RESOLVED

The J5 → J6 conversion funnel relies on Discord rendering an inline-playable preview when a clip MP4 is shared, AND on the landing page rendering a high-quality Open Graph card preview when a Warden coupon link is shared. Decision #UX-9 covers the **landing page OG card** specifically.

#### 3.3.1 Open Graph metadata

Set in `apps/web/src/app/layout.tsx` (root) and overridden per-route as needed.

**Landing (`/`):**

```html
<meta property="og:type" content="website">
<meta property="og:title" content="Warden — Le clip est le produit. Le téléphone suffit.">
<meta property="og:description" content="L'app de coaching mobile pour joueurs FPS compétitifs. Auto-slicing, minimap, voix, partage Discord — tout sur le téléphone.">
<meta property="og:url" content="https://warden.team/">
<meta property="og:image" content="https://warden.team/og/landing.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Warden">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Warden — Progresser plus vite en investissant moins de temps.">
<meta name="twitter:description" content="L'app de coaching mobile pour joueurs FPS compétitifs.">
<meta name="twitter:image" content="https://warden.team/og/landing.jpg">
```

**Pricing (`/pricing`):**

Same as Landing except `og:url` and a slight title variant: "Warden — €7.99/mois ou €79.90/an. Coaching FPS sur mobile." (Note: Discord OG preview shows pricing strings, but this is **web** — Reader-App banlist applies to **mobile** only, per cross-READER-APP-001.)

**Dashboard:** `<meta name="robots" content="noindex">` — protected user data, no OG preview surface.

#### 3.3.2 OG image design (`/og/landing.jpg`, 1200×630)

The OG image is the **load-bearing** asset for the J5 → J6 funnel — it's what Lucas sees when Thomas pins the coupon link in the Discord channel. It is the visual moment of "Warden looks legit, I'll click."

**Composition:**

```
┌────────────────────────────────────────────────────────────────────┐
│  bg #0F0F0F (Web "Clean Minimal" background)                       │
│                                                                    │
│   ┌─────┐                                                          │
│   │ W   │  WARDEN                                                  │ ← brand top-left
│   └─────┘  Inter 700 / 32                                          │   accent #E8731A "W" mark
│                                                                    │
│                                                                    │
│   PROGRESSER PLUS VITE                                             │ ← FR-locked hero
│   EN INVESTISSANT MOINS DE TEMPS.                                  │   Inter 800 / 56
│                                                                    │   text #F0F0F0
│                                                                    │
│                                                                    │
│   Coaching FPS sur mobile · Auto-slicing · Voix · Discord-ready    │ ← subtitle
│                                                                    │   Inter 400 / 22
│                                                                    │   text-secondary
│                                                                    │
│                                                  ┌──────────────┐  │
│                                                  │ warden.team  │  │ ← URL chip
│                                                  └──────────────┘  │   bottom-right
└────────────────────────────────────────────────────────────────────┘
```

**Why this composition:**

- **No app screenshots** — legacy distillate explicitly rejects app screenshots when the app isn't finished. Coaches recognize generic UI mockups as marketing-padding.
- **No testimonials** — same reason. Empty social proof reads as desperation.
- **No fake "users coached" counter** — anti-fake-content. Direction A "Clean Minimal" is the visual stance.
- **The hero IS the moment** — the FR-locked tagline does the conversion lift; making it the visual centerpiece compresses the message into a single glance.
- **The orange accent ties to the in-app accent** (Decision #UX-13 cross-surface coherence — same Warden orange in OG card → web → mobile).

**Format:** 1200×630 JPEG (smaller than PNG; Discord re-encodes anyway), under 200 KB, sRGB color profile.

**Production:** designed once in a vector tool (Figma / Affinity Designer) and exported. Does NOT need to be runtime-generated for V1. Static asset under `apps/web/public/og/landing.jpg`.

#### 3.3.3 Twitter Card

`summary_large_image` (same dimensions; Twitter renders in card format). Title/description identical to OG; Twitter and Discord both consume the same `og:` meta tags as fallback if `twitter:` tags are missing — keeping both ensures redundancy.

### 3.4 Cookie banner UX — Decision #UX-10 RESOLVED

PRD-bound: cookie banner required (Firebase Analytics uses cookies); accept/reject choice persisted in localStorage; banner does not reappear; Analytics loads ONLY after acceptance.

#### 3.4.1 Banner layout

Bottom-anchored fixed banner, full-width on mobile, max 1024 px centered on desktop:

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ╔══════════════════════════════════════════════════════════╗   │
│   ║                                                          ║   │
│   ║  We use cookies to understand how you use Warden.        ║   │
│   ║  See our [Privacy policy].                               ║   │
│   ║                                                          ║   │
│   ║                       [Reject]   [Accept]                ║   │
│   ║                                                          ║   │
│   ╚══════════════════════════════════════════════════════════╝   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Visual:**

- Container: shadcn `Card` with 1 px `border #333333` + `surface-elevated` background.
- Padding: 16 px page-edge / 24 px on desktop.
- Anchored 16 px from bottom; not overlapping CTAs (the landing CTA is hero-area, far from bottom).
- Heading: not rendered (banner is body-only — short enough).
- Body: Inter 14/400 `text-secondary`. "[Privacy policy]" is an inline `<a>` with `accent` color and underline.
- CTAs:
  - **Reject** — shadcn `Button` variant `outline`, gray border, `text` foreground.
  - **Accept** — shadcn `Button` variant `default`, orange-fill, `text` foreground.

**Equal-weight CTAs:** GDPR-compliant — Reject and Accept are visually equivalent in size and prominence (no Reject-as-tiny-link dark pattern).

#### 3.4.2 Persistence behavior

| User action | Persisted in `localStorage` | Firebase Analytics state |
|---|---|---|
| Tap **Accept** | `cookie_consent: "accepted"` + `cookie_consent_at: <ISO 8601>` | Conditionally loaded immediately (FR web-FR29; architecture loads only post-consent) |
| Tap **Reject** | `cookie_consent: "rejected"` + `cookie_consent_at: <ISO 8601>` | NOT loaded; analytics calls become no-ops |
| Banner dismissed (no action) | NOT persisted | NOT loaded; banner re-appears on next visit |

**No "Remind me later"** — that's a dark pattern (delays consent without recording it; lets the site keep tracking). Two options only.

**No "Cookie preferences" detail page** for V1 — Warden uses one analytics service (Firebase Analytics). Once V2 adds a marketing analytics service or a CMP-required granular toggle, a "Cookie preferences" sub-page can be added on `/privacy`.

#### 3.4.3 Banner re-display logic

- First-ever visit → banner shown
- Post-Accept → never shown again (persisted)
- Post-Reject → never shown again (persisted)
- Persisted-then-cleared (e.g., user clears localStorage manually) → re-shown

**No automatic re-prompt cadence** — once the user has answered, Warden does not re-ask. If V2 needs to revoke and re-prompt (e.g., privacy policy update), that's a deliberate re-prompt with explicit notice, not a cadence-based nag.

### 3.5 Web empty state — Decision #UX-11 (web) RESOLVED

**`/dashboard` "No active subscription" empty state** (FR web-DASHBOARD-005). Shown when an authenticated user has no `users/{uid}` doc OR `users/{uid}.status` is undefined / never-paid:

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Welcome to Warden.                                              │ ← H1 32/800
│                                                                  │
│  You don't have an active subscription yet.                      │ ← body 16/400
│                                                                  │
│              [See pricing]                                       │ ← primary CTA → /pricing
│                                                                  │
│                                                                  │
│  ────────────────────────────────────────────                    │
│                                                                  │
│  Already paying with another account?                            │ ← small 14/400
│  [Sign out] and sign in with the right account.                  │   text-secondary
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Why two paths:** the secondary "Already paying with another account?" addresses the realistic case where a coach signs in with the wrong Google account on web (e.g., personal vs gaming account). Without this path, they'd hit the "No active subscription" state with no obvious recovery besides reading their own email — adding the explicit Sign-out path closes the loop.

**Visual:** single `Card` primitive, centered vertically, max-width 640 px. No illustrations, no Lottie, no "empty-box" graphic — Direction A "Clean Minimal" rejects illustrative empty-state graphics.

### 3.6 Web header / footer — confirmation, not redesign

Per legacy distillate + existing `apps/web/src/components/layout/`:

**Header (sticky):**

```
[W WARDEN]                                   [Pricing]  [Sign in / Dashboard]
```

- Logo left (clickable → `/`).
- Nav right: "Pricing" link always visible; "Sign in" when anonymous → opens auth modal at `/pricing`; "Dashboard" when authenticated → routes to `/dashboard`.
- Active link: `accent` color + 2 px underline.
- No hamburger menu (legacy distillate rejected; only 2–3 links so always-visible).

**Footer (centered):**

```
                  [Privacy] · [Terms] · © 2026 Warden
```

- All pages share. No social media icons (Direction A "Clean Minimal").
- No "Made with ♥" — no sentiment copy.

### 3.7 Web feedback patterns (consolidated)

Inherited from legacy distillate, restated as binding pattern:

| Feedback type | Surface | A11Y signal |
|---|---|---|
| Success transient banner / redirect | Top-of-content green banner (`success #22C55E` 1 px border + 8% fill) for 5 s, OR redirect with `?success=1` URL param triggering banner on next page | `✓` filled circle + heading + color |
| Error alert | shadcn `Alert` variant `destructive`, top-of-content, persistent | `⚠` triangle + heading + color |
| Warning alert with action | shadcn `Alert` variant `default` with amber border (custom variant via `cn()`), persistent | `⚠` triangle + heading + action button + amber color |
| Loading | shadcn `Skeleton` matching final shape (Card-shaped Skeleton for SubscriptionCard; Table-shaped Skeleton for any list) | Skeleton shape signals "content loading here" |
| Modal patterns | shadcn `Dialog`; backdrop click closes; ESC closes; focus-trap default via Radix | Focus-visible 2 px orange outline |

**Reduced motion:** `prefers-reduced-motion` is respected automatically by Radix primitives and Tailwind's `motion-safe:` / `motion-reduce:` utilities. Web has minimal animation in V1 anyway (legacy distillate), so the impact is small.

---

## 4. Copy Decks

This section lands Decisions #UX-2 (mobile French copy deck) and #UX-3 (web English copy deck with FR-verbatim insertions). All strings are organized by screen / component for direct handoff to implementation. **Reader-App banlist enforcement applies to §4.1 (mobile) only — §4.2 (web) is exempt and DOES include pricing strings on the Pricing page.**

### 4.1 Mobile — French copy deck — Decision #UX-2 RESOLVED

#### 4.1.1 Login flow (`LoginScreen` + auth-related toasts)

| Key | French copy | Notes |
|---|---|---|
| `LOGIN.brand` | `WARDEN` | display-mono 22 letter-spacing 4 |
| `LOGIN.heading` | `CONNEXION` | heading-mono 16 letter-spacing 1.5 |
| `LOGIN.google_cta` | `Continuer avec Google` | Google sign-in button label |
| `LOGIN.divider` | `— OU —` | Mono uppercase divider |
| `LOGIN.email_label` | `Adresse email` | Field label |
| `LOGIN.email_placeholder` | `vous@exemple.com` | Placeholder |
| `LOGIN.password_label` | `Mot de passe` | Field label |
| `LOGIN.signin_cta` | `SE CONNECTER` | Primary CTA mono uppercase |
| `LOGIN.no_account_heading` | `Pas encore d'abonnement ?` | small 14 |
| `LOGIN.no_account_link` | `Créez un compte sur warden.team →` | Deep-link to web (Reader-App-compliant — no in-app sign-up) |
| `LOGIN.error_email_format` | `● Veuillez saisir une adresse email valide.` | Inline error |
| `LOGIN.error_password_short` | `● Le mot de passe doit contenir au moins 8 caractères.` | Inline error |
| `LOGIN.error_invalid` | `● Email ou mot de passe incorrect.` | Inline error |
| `LOGIN.error_network` | `● Connexion impossible. Vérifiez votre réseau.` | Inline error |
| `LOGIN.toast_day31_reauth` | `Pour des raisons de sécurité, merci de vous reconnecter.` | Day-31 cache-expiry toast |
| `LOGIN.toast_signed_out` | `Vous avez été déconnecté.` | Sign-out confirmation |

#### 4.1.2 Card View (cold-start + grid)

| Key | French copy | Notes |
|---|---|---|
| `CARDS.brand_top_strip` | `WARDEN` | Top strip wordmark |
| `CARDS.coldstart_heading_zero` | `Aucune session importée pour l'instant.` | When zero sessions ever imported |
| `CARDS.coldstart_subhead_zero` | `Importez votre première session d'entraînement.` | When zero sessions ever imported |
| `CARDS.coldstart_resume_cta` | `[▶] REPRENDRE LA DERNIÈRE SESSION` | Primary CTA when in-progress session exists |
| `CARDS.coldstart_import_cta` | `[+] IMPORTER UNE NOUVELLE SESSION` | Always-present import CTA |
| `CARDS.topbar_import_short` | `IMPORTER` | Top-bar leading button |
| `CARDS.topbar_sort_short` | `TRIER` | Top-bar trailing button |
| `CARDS.topbar_account_short` | `COMPTE` | Top-bar trailing button |
| `CARDS.topbar_view_cards` | `CARDS` | View toggle (default) |
| `CARDS.topbar_view_timeline` | `TIMELINE` | View toggle (manual-clip mode, Decision #UX-14) |
| `CARDS.unknown_map_label` | `CARTE INCONNUE` | Card label-strip when map_name = "unknown" |
| `CARDS.unknown_map_overlay` | `CARTE NON IDENTIFIÉE` | Card overlay stamp |
| `CARDS.score_v2_chip` | `[V2]` | Chip on score-based sort options |
| `CARDS.score_v2_toast` | `Tri par score disponible avec V2 (OCR).` | Toast on tap of [V2] sort option |
| `CARDS.codec_unsupported_heading` | `FORMAT NON COMPATIBLE` | Modal heading on codec rejection |
| `CARDS.codec_unsupported_body` | `Cette vidéo utilise un codec non pris en charge. Warden lit les fichiers MP4 (H.264 / AAC).` | Modal body |
| `CARDS.codec_unsupported_cta` | `OK` | Acknowledge CTA |
| `CARDS.resume_session_toast` | `REPRISE: {map} · {timestamp}` | e.g., "REPRISE: M3 SILVA · 00:42" |

#### 4.1.3 Sort dropdown

| Key | French copy | Notes |
|---|---|---|
| `SORT.option_temporal` | `TEMPOREL (PLUS RÉCENT)` | Default; mono uppercase |
| `SORT.option_orange_lead` | `PLUS GROS ÉCART · ORANGE` | + `[V2]` chip in V1 |
| `SORT.option_blue_lead` | `PLUS GROS ÉCART · BLEU` | + `[V2]` chip in V1 |
| `SORT.option_closest` | `CARTE LA PLUS PROCHE` | + `[V2]` chip in V1 |
| `SORT.apply_cta` | `APPLIQUER` | Confirm CTA |

#### 4.1.4 Account bottom-sheet

| Key | French copy | Notes |
|---|---|---|
| `ACCOUNT.heading` | `MON COMPTE` | Bottom-sheet heading |
| `ACCOUNT.email_label` | `Email` | Static label |
| `ACCOUNT.entitlement_paid` | `ABONNEMENT ACTIF` | Status chip when paid |
| `ACCOUNT.entitlement_offline` | `MODE HORS LIGNE` | Status chip when offline-grace |
| `ACCOUNT.entitlement_payment_failed` | `PAIEMENT EN ÉCHEC` | Status chip when payment-failed |
| `ACCOUNT.manage_subscription_cta` | `GÉRER MON ABONNEMENT` | Deep-link to web Customer Portal |
| `ACCOUNT.help_heading` | `AIDE` | Help section header in account bottom-sheet |
| `ACCOUNT.help_email_cta` | `NOUS CONTACTER` | Opens mailto:support@warden.team |
| `ACCOUNT.help_discord_cta` | `REJOINDRE LE DISCORD` | Opens https://discord.gg/DpDEyBZw |
| `ACCOUNT.signout_cta` | `SE DÉCONNECTER` | Sign-out (returns to LoginScreen) |

#### 4.1.5 Processing screen + tips

| Key | French copy | Notes |
|---|---|---|
| `PROC.heading` | `ANALYSE EN COURS` | Long-processing screen heading |
| `PROC.stage_extraction` | `EXTRACTION DES IMAGES CLÉS` | Stage 1 label |
| `PROC.stage_round_detection` | `DÉTECTION DES ROUNDS` | Stage 2 label |
| `PROC.stage_map_identification` | `IDENTIFICATION DES CARTES · {x} / {y} ROUNDS` | Stage 3 label with progress |
| `PROC.stage_persistence` | `ENREGISTREMENT DES SEGMENTS` | Stage 4 label |
| `PROC.tip_header` | `ASTUCE` | Tip section header (Stamp) |
| `PROC.tip_1` | `Double-tap en haut à gauche pour basculer en vue minimap.` | Rotating tip 1 |
| `PROC.tip_2` | `Faites glisser les poignées du clip pour ajuster la durée.` | Rotating tip 2 |
| `PROC.tip_3` | `Ajoutez votre voix avant, pendant ou après le clip.` | Rotating tip 3 |
| `PROC.tip_4` | `Triez par "carte la plus proche" pour les rounds importants.` | Rotating tip 4 |
| `PROC.tip_5` | `Votre progression est sauvegardée automatiquement.` | Rotating tip 5 |
| `PROC.pause_cta` | `METTRE EN PAUSE` | Process control |
| `PROC.cancel_cta` | `ANNULER` | Process control |
| `PROC.cancel_modal_heading` | `Annuler l'analyse ?` | Confirmation modal heading |
| `PROC.cancel_modal_body` | `Les segments déjà identifiés seront conservés en l'état.` | Confirmation modal body |
| `PROC.cancel_modal_keep` | `Continuer l'analyse` | Modal cancel-cancel |
| `PROC.cancel_modal_confirm` | `Annuler l'analyse` | Modal confirm-cancel |
| `PROC.short_processing_label` | `PRÉPARATION DU CLIP…` | Short inline processing |
| `PROC.short_export_label` | `ENCODAGE EN COURS…` | Export processing |
| `PROC.error_heading` | `L'ANALYSE A ÉCHOUÉ` | Pipeline-error screen heading |
| `PROC.error_stage_label` | `Une erreur est survenue à l'étape : {stage}` | Stage-specific error body |
| `PROC.error_recovery_body` | `Vous pouvez réessayer ou continuer en mode manuel — les rounds déjà identifiés sont conservés.` | Recovery body copy |
| `PROC.error_retry_cta` | `RÉESSAYER` | Retry primary |
| `PROC.error_manual_cta` | `CONTINUER EN MANUEL` | Continue with whatever segmented |
| `PROC.error_details_disclosure` | `Détails techniques` | Collapsible disclosure label |

#### 4.1.6 Foreground Service Android notification

Architecture-bound — copy is locked at `Analyse en cours…`:

| Key | French copy | Notes |
|---|---|---|
| `NOTIF.heading` | `Analyse en cours…` | Architecture-bound; sticky notification title |
| `NOTIF.progress_text` | `{percent}% — {stage}` | Sticky notification subtitle |
| `NOTIF.paused_heading` | `Analyse en pause` | When user paused processing |
| `NOTIF.completed_heading` | `Analyse terminée` | Brief notification on completion (auto-dismiss) |

#### 4.1.7 Cinema Mode controls

| Key | French copy | Notes |
|---|---|---|
| `CINEMA.viewmode_full` | `FULL` | Segment label |
| `CINEMA.viewmode_minimap` | `MINIMAP` | Segment label |
| `CINEMA.viewmode_minimap_hud` | `MINIMAP + HUD` | Segment label |
| `CINEMA.unknown_map_roi_unavailable` | `ROI INDISPONIBLE` | Stamp under disabled segment when map = unknown |
| `CINEMA.episode_prev` | `◀ PRÉCÉDENT` | Previous episode button |
| `CINEMA.episode_next` | `SUIVANT ▶` | Next episode button |
| `CINEMA.center_label` | `{map} · M{n}` | e.g., "SILVA · M3" |
| `CINEMA.center_label_manual` | `MANUEL · {timestamp}` | When in TIMELINE mode (Decision #UX-14) |
| `CINEMA.maps_overflow_heading` | `TOUTES LES CARTES` | Bottom-sheet heading on overflow tap |
| `CINEMA.clip_button` | `CLIP` | Bottom-bar action |
| `CINEMA.clip_min_duration_toast` | `Clip minimum 5 secondes.` | When bracket-drag would result in < 5s |
| `CINEMA.clip_max_duration_toast` | `Clip maximum 60 secondes.` | When bracket-drag would result in > 60s |

#### 4.1.8 Clip Mode + voice recorder

| Key | French copy | Notes |
|---|---|---|
| `CLIP.heading` | `NOUVEAU CLIP` | Screen heading |
| `CLIP.duration_label` | `{seconds}s` | Live duration display |
| `CLIP.voice_section_heading` | `VOIX (OPTIONNEL)` | Section heading above the 3 slots |
| `CLIP.slot_before` | `AVANT` | Slot label |
| `CLIP.slot_during` | `PENDANT` | Slot label |
| `CLIP.slot_after` | `APRÈS` | Slot label |
| `CLIP.slot_record_cta` | `Tap pour enregistrer` | Empty slot CTA |
| `CLIP.slot_recording_label` | `REC` | Stamp during recording |
| `CLIP.slot_overflow_label` | `OVERFLOW` | Stamp when during-slot extends past clip end |
| `CLIP.slot_preview_cta` | `[▶ ÉCOUTER]` | Filled-slot preview button |
| `CLIP.slot_delete_cta` | `[✕ SUPPRIMER]` | Filled-slot delete button |
| `CLIP.slot_rerecord_modal_heading` | `Réenregistrer ?` | Confirmation modal |
| `CLIP.slot_rerecord_modal_body` | `L'enregistrement précédent sera remplacé.` | Confirmation body |
| `CLIP.slot_rerecord_modal_cancel` | `Annuler` | Cancel button |
| `CLIP.slot_rerecord_modal_confirm` | `Réenregistrer` | Confirm button |
| `CLIP.preview_cta` | `APERÇU` | Clip preview before export |
| `CLIP.export_cta` | `EXPORTER` | Export entry |

#### 4.1.9 Export & Share screen

| Key | French copy | Notes |
|---|---|---|
| `EXPORT.heading` | `EXPORTER LE CLIP` | Screen heading |
| `EXPORT.quality_label` | `QUALITÉ` | Section label |
| `EXPORT.quality_mobile_title` | `MOBILE` | Mobile-quality tier title |
| `EXPORT.quality_mobile_body` | `720p — partage rapide sur Discord` | Mobile-quality tier body |
| `EXPORT.quality_hd_title` | `HD` | HD-quality tier title |
| `EXPORT.quality_hd_body` | `Résolution source — fichier plus volumineux` | HD-quality tier body |
| `EXPORT.export_cta` | `EXPORTER ET PARTAGER` | Primary CTA |
| `EXPORT.encoding_label` | `ENCODAGE EN COURS…` | During encode |
| `EXPORT.encoding_progress` | `{percent}%` | Progress percentage |
| `EXPORT.share_sheet_subject` | `Clip Warden — {map}` | OS share-sheet subject (passed via expo-sharing) |
| `EXPORT.share_complete_toast` | `CLIP PARTAGÉ` | Share-confirmed toast |
| `EXPORT.share_cancelled_toast` | `Partage annulé.` | Share-sheet cancelled toast |
| `EXPORT.share_error_toast` | `Échec du partage. Le clip est enregistré localement.` | Share error |

#### 4.1.10 Entitlement banner / lapsed screen / payment-failed CTA

**MUST NOT include any banned strings (€7.99, €79.90, "subscribe", "abonnement", "monthly", "yearly", "buy" or locale equivalents).** All copy below is checked against the Reader-App CI gate banlist.

| Key | French copy | Notes |
|---|---|---|
| `BANNER.payment_failed_heading` | `MISE À JOUR DU MOYEN DE PAIEMENT NÉCESSAIRE` | Banner heading |
| `BANNER.payment_failed_body` | `Votre dernier paiement a échoué. Mettez à jour votre carte pour conserver l'accès à Warden.` | Banner body — NO price string |
| `BANNER.payment_failed_cta` | `METTRE À JOUR` | Deep-link CTA to web Customer Portal |
| `BANNER.offline_chip` | `HORS LIGNE` | Offline-grace chip |
| `BANNER.offline_sheet_heading` | `MODE HORS LIGNE` | Bottom-sheet heading |
| `BANNER.offline_sheet_body` | `Dernière synchronisation : il y a {days} jour(s). Vos clips et annotations sont enregistrés localement et seront synchronisés au prochain démarrage en ligne.` | Body |
| `BANNER.offline_expiry_warning` | `Cache d'authentification expire bientôt — merci de vous reconnecter dès que possible pour ne pas être déconnecté.` | Day-29/30 escalation copy |
| `LAPSED.heading` | `ABONNEMENT REQUIS` | Full-screen heading — **NO PRICE** |
| `LAPSED.body_line1` | `Votre abonnement est expiré ou annulé.` | Body line 1 — NO PRICE |
| `LAPSED.body_line2` | `Renouvelez-le pour reprendre vos analyses.` | Body line 2 — NO PRICE (uses "Renouvelez-le", not "subscribe") |
| `LAPSED.body_line3` | `Vos sessions, clips et annotations restent conservés et seront restaurés automatiquement.` | Reassurance copy |
| `LAPSED.cta_primary` | `GÉRER MON ABONNEMENT` | Deep-link to web Customer Portal — NO PRICE |
| `LAPSED.cta_signout` | `SE DÉCONNECTER` | Secondary CTA |

**Reader-App banlist verification (LOCKED 2026-05-07 — regex narrowed):**

Architecture's banlist regex narrows from the original `\b(subscribe|s'?abonner|abonnement|monthly|yearly|mensuel|annuel|buy|acheter)\b` to verb forms only: `\b(subscribe|s'?abonner|abonnez-vous|monthly|yearly|mensuel|annuel|buy|acheter)\b`. The noun `abonnement` is permitted in entitlement-state UI labels.

**Why narrowing is safe:**

1. Both `Gérer mon abonnement` and `Abonnement requis` are entitlement-state UI labels, not monetization surfaces — they describe the user's relationship with their existing subscription, not pitch a new one.
2. The Reader-App policy intent is "no in-app pricing or purchase flow" — labels that route the user OUT of mobile to web for billing self-service are aligned with the policy, not violations of it.
3. Apple's Reader-App guidelines (App Store Review 3.1.3) explicitly permit references to the existence of an external subscription; they prohibit in-app purchase mechanisms and pricing display.

**Locked mobile copy (post-narrowing):**

| Label key | French copy |
|---|---|
| `LAPSED.heading` | `ABONNEMENT REQUIS` |
| `ACCOUNT.manage_subscription_cta` | `GÉRER MON ABONNEMENT` |
| `LAPSED.cta_primary` | `GÉRER MON ABONNEMENT` |

**Architecture handoff:** Sprint-3 architecture-doc amendment narrows the banlist regex; the `apps/mobile/scripts/reader-app-gate.sh` script and `.github/workflows/ci.yml` workflow update accordingly. Tracked at §6.5.

#### 4.1.11 Permissions prompts (Android-system-rendered, but Warden controls the rationale text)

| Key | French copy | Notes |
|---|---|---|
| `PERM.storage_rationale` | `Warden a besoin d'accéder à vos vidéos pour analyser vos sessions.` | READ_EXTERNAL_STORAGE rationale |
| `PERM.microphone_rationale` | `Warden a besoin d'accéder au microphone pour enregistrer vos commentaires audio.` | RECORD_AUDIO rationale |
| `PERM.foreground_service_rationale` | `Warden a besoin de continuer l'analyse en arrière-plan via une notification persistante.` | FOREGROUND_SERVICE rationale (system-managed display) |
| `PERM.denied_storage_message` | `Sans accès aux vidéos, vous ne pouvez pas importer de session. Activez la permission dans les Paramètres.` | Permission-denied recovery copy |
| `PERM.denied_microphone_message` | `Sans accès au microphone, l'enregistrement de commentaires est désactivé.` | Permission-denied (graceful — clip flow still works without voice) |

### 4.2 Web — English copy deck with FR-verbatim insertions — Decision #UX-3 RESOLVED

#### 4.2.1 Landing page (`/`)

| Key | English copy (with French insertions noted) | Notes |
|---|---|---|
| `LANDING.brand` | `WARDEN` | top-left |
| `LANDING.hero_headline_FR` | **`Progresser plus vite en investissant moins de temps.`** | **FR-LOCKED — preserved verbatim per PRD I18N-002** |
| `LANDING.hero_subhead` | `The phone-native coaching companion for competitive amateur and semi-pro players.` | English |
| `LANDING.hero_cta` | `See pricing` | Primary CTA → /pricing |
| `LANDING.diff_1_heading` | `On-device. Always.` | Differentiator 1 heading |
| `LANDING.diff_1_body` | `Your footage never leaves your phone. No upload, no cloud, no waiting.` | Body |
| `LANDING.diff_2_heading` | `Auto-slice in 90 seconds.` | Differentiator 2 |
| `LANDING.diff_2_body` | `Round detection runs locally. Open Card View, tap a round, review.` | Body |
| `LANDING.diff_3_heading` | `Built for the Discord workflow.` | Differentiator 3 |
| `LANDING.diff_3_body` | `Export a 30-second clip with your voice annotation. Share to Discord. Done.` | Body |
| `LANDING.footer_cta` | `Start coaching better tonight.` | Footer-area secondary CTA |

#### 4.2.2 Pricing page (`/pricing`)

| Key | English copy (with French insertions noted) | Notes |
|---|---|---|
| `PRICING.heading` | `Subscribe to Warden` | H1 |
| `PRICING.subhead` | `Two plans. Cancel anytime. No fine print.` | H2 |
| `PRICING.plan_monthly_label` | `Monthly` | Plan card label |
| `PRICING.plan_monthly_price` | `€7.99 / month` | Plan price |
| `PRICING.plan_monthly_cta` | `Choose monthly` | Plan card CTA |
| `PRICING.plan_yearly_label` | `Yearly` | Plan card label |
| `PRICING.plan_yearly_price` | `€79.90 / year` | Plan price |
| `PRICING.plan_yearly_savings_FR` | **`économisez 2 mois`** | **FR-locked savings copy** |
| `PRICING.plan_yearly_cta` | `Choose yearly` | Plan card CTA |
| `PRICING.coupon_label` | `Coupon` | Coupon input label (when URL param present) |
| `PRICING.coupon_applied_chip` | `Coupon applied` | Static chip when coupon param valid |
| `PRICING.coupon_invalid_chip` | `Coupon invalid` | Static chip when coupon param invalid |
| `PRICING.deferred_billing_FR` | **`Vous ne serez pas débité avant le {date}`** | **FR-locked — preserved verbatim per PRD I18N-002** |
| `PRICING.legal_footer` | `By subscribing, you agree to our Terms and Privacy Policy.` | Below plan cards |

#### 4.2.3 Auth modal (overlay on `/pricing`)

| Key | English copy | Notes |
|---|---|---|
| `AUTH.heading` | `Sign in to subscribe` | Modal H2 |
| `AUTH.selected_plan_label` | `Selected plan: {plan} · {price}` | small 14 |
| `AUTH.selected_plan_savings_FR` | `({FR-locked: économisez 2 mois})` | Inline FR-savings on yearly |
| `AUTH.google_cta` | `Continue with Google` | Google sign-in button |
| `AUTH.divider` | `— or —` | Divider |
| `AUTH.email_label` | `Email address` | Field label |
| `AUTH.password_label` | `Password` | Field label |
| `AUTH.password_show` | `Show / hide password` | Visibility toggle ARIA label |
| `AUTH.create_account_toggle` | `Create new account (8+ characters)` | Sign-up mode toggle |
| `AUTH.continue_cta` | `Continue to checkout` | Primary CTA |
| `AUTH.legal_footer` | `By continuing, you agree to our Terms and Privacy.` | Below CTA |
| `AUTH.error_email_format` | `● Please enter a valid email address.` | Inline error |
| `AUTH.error_password_short` | `● Password must be 8 characters or more.` | Inline error sign-up |
| `AUTH.error_signin_invalid` | `● Incorrect email or password.` | Inline error sign-in |
| `AUTH.error_account_exists` | `● An account with this email already exists. Sign in instead.` | Inline error sign-up |
| `AUTH.error_no_account` | `● No account found. Tick "Create new account" to register.` | Inline error sign-in |
| `AUTH.error_rate_limit` | `● Too many attempts. Try again in a few minutes.` | Inline error |
| `AUTH.error_network` | `● Connection error. Check your internet and retry.` | Inline error |
| `AUTH.password_reset_link` | `Forgot password?` | Below password field (V1 LOCKED) — opens inline reset form |
| `AUTH.password_reset_heading` | `Reset password` | Inline reset-form heading |
| `AUTH.password_reset_body` | `Enter your account email. We'll send a password reset link.` | Reset-form body |
| `AUTH.password_reset_send_cta` | `Send reset link` | Reset-form primary CTA |
| `AUTH.password_reset_success` | `Check your email for a reset link.` | Post-submit success state |
| `AUTH.password_reset_back` | `← Back to sign in` | Return-to-signin link |
| `AUTH.password_reset_complete_banner` | `Password updated. Sign in.` | Banner on /auth/sign-in?passwordReset=1 |

#### 4.2.4 Stripe checkout redirect button + post-checkout

| Key | English copy | Notes |
|---|---|---|
| `CHECKOUT.redirecting_label` | `Redirecting to secure checkout…` | Skeleton-replacement during redirect prep |
| `CHECKOUT.success_banner_heading` | `Welcome to Warden.` | Top banner on /dashboard?success=1 |
| `CHECKOUT.success_banner_body` | `Your subscription is active.` | Body |

#### 4.2.5 Dashboard (`/dashboard`)

| Key | English copy (with French insertions noted) | Notes |
|---|---|---|
| `DASHBOARD.heading` | `Your subscription` | H1 |
| `DASHBOARD.email_label` | `Email` | Static |
| `DASHBOARD.plan_label` | `Plan` | Static |
| `DASHBOARD.plan_monthly` | `Monthly · €7.99 / month` | Plan display |
| `DASHBOARD.plan_yearly` | `Yearly · €79.90 / year` | Plan display |
| `DASHBOARD.status_label` | `Status` | Static |
| `DASHBOARD.status_active` | `Active` | Status badge text |
| `DASHBOARD.status_past_due` | `Past due` | Status badge text |
| `DASHBOARD.status_canceling` | `Canceling` | Status badge text |
| `DASHBOARD.status_canceled` | `Canceled` | Status badge text |
| `DASHBOARD.next_payment_label` | `Next payment` | Static |
| `DASHBOARD.next_payment_value` | `{date}` | e.g., "12 August 2026" |
| `DASHBOARD.access_until_label` | `Access until` | Static (replaces "Next payment" when canceling) |
| `DASHBOARD.manage_cta` | `Manage subscription` | Deep-link to Stripe Customer Portal |
| `DASHBOARD.cancel_link` | `Cancel subscription` | Inside overflow menu inside SubscriptionCard |
| `DASHBOARD.resubscribe_cta` | `Resubscribe` | Primary CTA when canceled |
| `DASHBOARD.payment_warning_heading` | `Your last payment failed.` | Warning banner heading |
| `DASHBOARD.payment_warning_body` | `Update your payment method to keep using Warden.` | Body |
| `DASHBOARD.payment_warning_cta` | `Update payment method` | Deep-link to portal |
| `DASHBOARD.empty_heading` | `Welcome to Warden.` | Empty-state H1 |
| `DASHBOARD.empty_body` | `You don't have an active subscription yet.` | Empty-state body |
| `DASHBOARD.empty_cta` | `See pricing` | Empty-state CTA → /pricing |
| `DASHBOARD.wrong_account_label` | `Already paying with another account?` | Empty-state secondary path |
| `DASHBOARD.wrong_account_link` | `Sign out and sign in with the right account.` | Inline link |

#### 4.2.6 Cancel-confirmation dialog

| Key | English copy | Notes |
|---|---|---|
| `CANCEL.heading` | `Cancel subscription?` | Modal H2 |
| `CANCEL.body` | `You'll keep access until {date}.` | Body — static date from current_period_end |
| `CANCEL.reassurance` | `After cancellation, you can resubscribe at any time on /pricing.` | Reassurance — anti-dark-pattern compliance |
| `CANCEL.keep_cta` | `Keep subscription` | Default-focus CTA — primary visual weight |
| `CANCEL.confirm_cta` | `Cancel` | Destructive CTA — ghost red |

**Anti-dark-pattern audit (J8 explicit):** dialog includes ZERO of the following:

- ❌ "Why are you cancelling?" — no exit survey
- ❌ "We'll miss you" / "Are you sure?" — no guilt-trip
- ❌ "Type CANCEL to confirm" — no double-confirm friction
- ❌ "Cancel within 24 hours to lock in this price" — no countdown timer
- ❌ "Stay for 50% off" — no retention modal

#### 4.2.7 Cookie banner

| Key | English copy | Notes |
|---|---|---|
| `COOKIE.body` | `We use cookies to understand how you use Warden. See our [Privacy policy].` | Banner body |
| `COOKIE.privacy_link` | `Privacy policy` | Inline link → /privacy |
| `COOKIE.reject_cta` | `Reject` | Equal-weight ghost button |
| `COOKIE.accept_cta` | `Accept` | Equal-weight orange-fill button |

#### 4.2.8 Header / footer / legal

| Key | English copy | Notes |
|---|---|---|
| `HEADER.brand` | `WARDEN` | left logo |
| `HEADER.nav_pricing` | `Pricing` | always visible |
| `HEADER.nav_signin` | `Sign in` | when anonymous |
| `HEADER.nav_dashboard` | `Dashboard` | when authenticated |
| `HEADER.nav_signout` | `Sign out` | when authenticated, in account dropdown |
| `FOOTER.privacy_link` | `Privacy` | static link |
| `FOOTER.terms_link` | `Terms` | static link |
| `FOOTER.copyright` | `© 2026 Warden` | dynamically formatted |

#### 4.2.9 Open Graph metadata (Decision #UX-9)

| Key | Copy | Notes |
|---|---|---|
| `OG.landing_title` | `Warden — Le clip est le produit. Le téléphone suffit.` | Discord card title |
| `OG.landing_description` | `L'app de coaching mobile pour joueurs FPS compétitifs. Auto-slicing, minimap, voix, partage Discord — tout sur le téléphone.` | Discord card description |
| `OG.landing_image` | `/og/landing.jpg` | 1200×630 |
| `OG.pricing_title` | `Warden — €7.99/mois ou €79.90/an. Coaching FPS sur mobile.` | Discord card title for /pricing |
| `OG.twitter_title` | `Warden — Progresser plus vite en investissant moins de temps.` | Twitter Card title |
| `OG.locale` | `fr_FR` | Both routes — French audience primary |

**Note:** OG metadata is in **French** even though the web UI body is English — the audience consuming these previews is French/Belgian Discord channels (including the Warden community at `https://discord.gg/DpDEyBZw`), and the FR-locked hero is the load-bearing conversion phrase. This is consistent with PRD I18N-002 (FR-locked hero on web) and reinforces the WoM Discord funnel.

#### 4.2.10 Email subjects (Stripe-generated, but Warden controls Stripe Dashboard config)

Stripe emails (receipts, payment-failed notices, subscription updates) are sent from Stripe with Warden branding. UX recommends Stripe Dashboard email templates use these subjects (English to match the web UI):

| Email type | Subject |
|---|---|
| Receipt | `Your Warden receipt — {date}` |
| Payment failed | `Action needed: update your payment method on Warden` |
| Subscription canceled | `Your Warden subscription is canceled` |
| Subscription resumed | `Welcome back to Warden` |

These are **operator-configured in Stripe Dashboard**, not application-rendered. Architecture's Stripe integration spec covers the implementation; UX provides the copy.

---

## 5. Recovery Pathways & Cross-Surface Coherence

### 5.1 V1 manual error-reporting path — Decision #UX-12 RESOLVED (with input pending)

V1 ships with **no crash reporting SDK** (architecture decision — OBS-003 + Sprint 3 deferral). UX must surface a manual error-reporting path so users hitting a critical error have a way to reach Stephane.

#### 5.1.1 Recommended pattern

UX recommends **both paths**, anchored at predictable error states:

1. **Mailto: link** — primary path. Embedded in critical-error blocking modals (codec-unsupported, pipeline-error fall-through, lapsed-after-retry, sign-in-after-3-failures). Opens the user's mail client with a pre-filled subject + a body template containing the error code and stage. The user adds context and sends. Architecture surface: a small helper at `apps/mobile/src/shared/services/errorReporting.ts` formats the mailto: URI with prefilled `subject` + `body` (URL-encoded).

2. **Discord invite link** — secondary path. Embedded in non-blocking error states and in the account bottom-sheet's "Aide" / "Help" entry. Routes to a Warden community Discord channel where Stephane (or future support) can respond. Discord invite is also the social-proof hook (legacy distillate moat).

**Critical-error modal layout (mobile + web equivalent):**

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  [⊗]                                                             │
│                                                                  │
│  L'ANALYSE A ÉCHOUÉ                                              │
│                                                                  │
│  Une erreur est survenue à l'étape : IDENTIFICATION DES CARTES   │
│                                                                  │
│  Vous pouvez réessayer, continuer en mode manuel, ou nous        │
│  signaler le problème.                                           │
│                                                                  │
│            [RÉESSAYER]   [CONTINUER EN MANUEL]                   │
│                                                                  │
│            [SIGNALER LE PROBLÈME]                                │ ← NEW (Decision #UX-12)
│                                                                  │
│  (Détails techniques)                                            │
│  ─────────────────────────                                       │
│  Code: OPENCV_JSI_FAIL                                           │
│  Stage: map_identification                                       │
│  App version: 1.0.0 (build 42)                                   │
│  Device: Poco X5 — Android 14                                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**`[SIGNALER LE PROBLÈME]` action:**

- **Primary (mailto):** opens mail client with `to=support@warden.team`, subject = `[Warden v{version}] {error_code} — {stage}`, and body template:
  ```
  Bonjour,

  J'ai rencontré une erreur en utilisant Warden.

  Code : OPENCV_JSI_FAIL
  Étape : Identification des cartes
  Version : 1.0.0 (build 42)
  Appareil : Poco X5 — Android 14
  Date : 2026-05-07 23:42 UTC+2

  (Décrivez ici ce que vous étiez en train de faire quand l'erreur est survenue.)


  Merci,
  ```
- **Fallback link below CTA:** `Ou rejoignez le Discord de Warden →` linking to `https://discord.gg/DpDEyBZw`.

#### 5.1.2 Content-decision needed (input required)

All inputs locked 2026-05-07.

| Locked content | Resolved value |
|---|---|
| Support email address | **`support@warden.team`** — matches the OG-card domain; one inbox; one responder (Stephane) for V1. |
| Warden Discord invite URL | **`https://discord.gg/DpDEyBZw`** — persistent invite to the Warden community Discord. |
| FR vs EN response language commitment | French — the audience is FR/BE; web users requesting help in English get a French reply with English translation. Sets honest expectations. |

#### 5.1.3 Mobile vs web placement rules

| Surface | Where the "Report a problem" / mailto + Discord links appear |
|---|---|
| **Mobile** | (a) Critical-error modals (codec-unsupported, pipeline-error fall-through). (b) Account bottom-sheet's "Aide" entry. (c) NOT on Login screen (privacy concern — surfacing a mailto on a screen the user hasn't authenticated through could be exploited for spam-mail-spoofing). |
| **Web** | (a) Dashboard's `SubscriptionCard` overflow menu → "Get help" → opens a small `Dialog` with mailto + Discord links. (b) Footer (small `Get help` link, fixed in `Footer` composition). (c) NOT on `/pricing` (preserves Stripe-handoff trust — channelling support inquiries into Stripe-Checkout context creates noise). |

#### 5.1.4 What counts as "critical" enough to surface the path

Critical = unrecoverable in-context. Examples:

- **Critical:** OpenCV JSI binding throws; FFmpeg subprocess returns nonzero on encode; Firebase Auth unrecoverable error after 3 retries; session-data save corruption detected at startup.
- **Not critical:** codec-unsupported (handled with explicit message; user knows what to do); permission denied (system handles); offline-grace expired (user knows the path — re-auth). These show the message, not the report-path.

**Why:** every "Report a problem" CTA spawns a support ticket if the user takes it seriously. Reserving it for genuinely-unrecoverable errors keeps signal-to-noise high for solo-dev support volume.

### 5.2 Cross-surface visual coherence audit — Decision #UX-13 RESOLVED

The user's brief locks two visual languages that share a brand. UX confirms the cross-surface alignment so the Discord-link → web → install → mobile journey feels like one product, even though no components are shared.

#### 5.2.1 Token-level alignment audit

| Token | Mobile (HUD) | Web (Clean Minimal) | Coherent? | Reconciliation |
|---|---|---|---|---|
| **Background** | `#0a0a0d` | `#0F0F0F` | Within 2 LAB-distance points (visually identical) | Accept divergence. Mobile is slightly darker for OLED-burn-in friendliness; web is the conventional dark-mode background. |
| **Surface** | `#101014` | `#1A1A1A` | Different by ~5 LAB points | Accept divergence — mobile's tactical aesthetic relies on the very-dark surface; web's softer surface fits Direction A. |
| **Surface elevated** | `#15151a` / `#1c1c22` | `#252525` | Different | Accept — semantic role same, value tuned per surface. |
| **Border** | `#26262e` | `#333333` | Different | Accept — both function as 1-px line separators. |
| **Text primary** | `#F0F0F0` | `#F0F0F0` | **EXACT MATCH** | ✅ |
| **Text secondary** | `#8a8a92` (muted) | `#999999` | Within 2 LAB points | Accept — visually identical. |
| **Accent (Warden orange)** | `#FF6B00` | `#E8731A` | **DIVERGENT — RECONCILE** | See §5.2.2 |
| **Accent semantics** | "1 px outline only — never as fill" | "Primary CTA fill + ghost outline" | Different by design | Accept — different surface roles permit different uses. |
| **Success** | `#22C55E` | `#22C55E` | **EXACT MATCH** | ✅ |
| **Error** | `#EF4444` | `#EF4444` | **EXACT MATCH** | ✅ |
| **Warning (web only — mobile uses `accent` for warning emphasis)** | n/a | `#F59E0B` | Mobile lacks; web has | Accept — mobile uses `accent` for payment-failed banner since mobile's tactical palette doesn't include amber. Cross-surface meaning is preserved (orange = "attention"). |

#### 5.2.2 Accent orange — divergent shade audit (the only finding requiring action)

Mobile `accent #FF6B00` vs web `accent #E8731A`:

- LAB color-distance: ~4.2 — visible to a human comparing both surfaces side-by-side.
- Saturation: mobile is 100%, web is ~84%.
- Lightness: mobile L*≈63, web L*≈58.
- Both meet WCAG AA contrast on their respective backgrounds (mobile orange on `#0a0a0d` ~5.0:1; web orange on `#0F0F0F` ~4.8:1).

**The divergence is small but discoverable.** A coach who clicks the OG-card preview, lands on the web `/pricing` page, completes Checkout, then opens the mobile app for the first time will see two slightly different oranges — within 30 seconds of each other. The audit reaches: this is a low-impact but easy-to-fix coherence break.

**UX recommendation: align both surfaces on a single accent value.**

Two reconciliation options:

| Option | Mobile change | Web change | Rationale |
|---|---|---|---|
| **A. Adopt web's `#E8731A`** | Mobile retunes from `#FF6B00` to `#E8731A` in `tokens.ts` | None | Web's value was chosen for AA-large/bold contrast on its specific background; the slight desaturation reads "premium" rather than "alert" — fits Warden's tactical-tool tone. |
| **B. Adopt mobile's `#FF6B00`** | None | Web retunes from `#E8731A` to `#FF6B00` in `globals.css` + `tailwind.config.ts` | Mobile's value is the tactical-HUD-direction-adopted-2026-05-01 baseline; mobile is the product, web is the door — let the product anchor the brand. |
| **C. Keep both (status quo)** | None | None | Acknowledge divergence as acceptable; flag as V1.1 follow-up. |

**LOCKED 2026-05-07: Option B (`#FF6B00` for both surfaces) — mobile-as-anchor:**

- The mobile HUD direction was adopted later (2026-05-01) and is more recent product thinking than the web Direction A (2026-04-02).
- Mobile is the product the user spends most time in; web is a 60-second portal.
- The brighter orange reads better on Discord's preview-pane backgrounds (where the OG card lives).
- Web's contrast on `#FF6B00` is ~5.0:1 against `#0F0F0F` background — meets AA-large/bold (≥3.0:1) and is close to AA-normal (≥4.5:1). All web orange uses are CTA buttons (large/bold), so AA-large/bold is the relevant bar.

**Implementation impact:** web retunes from `#E8731A` to `#FF6B00` and `accent-hover` from `#F28A2E` to `#FF8533` (proportional 9% lightness lift). Sprint-3 task tracked at §6.5: `feat(layout): bump web accent token to #FF6B00`. Mobile `tokens.ts` is unchanged.

#### 5.2.3 Type-scale alignment

| Element | Mobile | Web | Coherent? |
|---|---|---|---|
| **Largest brand mark** | display-mono 22 (JetBrains Mono UPPERCASE) | H1 32–48 (Inter) | Different by design — different fonts, different sizes, but both anchor brand presence on entry surface. |
| **Section headings** | heading-mono 16 + 1.5 letter-spacing (UPPERCASE) | H2 24–32 (Inter) | Different by design |
| **Body text** | body 13–14 / line-height 1.5 (Roboto) | body 16 / line-height 1.5 (Inter) | Mobile is slightly smaller (mobile body baseline) but line-height matches |
| **Mono / numeric** | JetBrains Mono everywhere (timecodes, scores, tactical labels) | n/a — web has no tactical-mono surface | Different by design — web is a billing portal, no mono surface needed |

Type-scale divergence is intentional and accepted — the surfaces serve different roles. No reconciliation needed.

#### 5.2.4 Spacing-scale alignment

Both surfaces use a **4-px base unit**. Mobile: 4 / 8 / 16 / 24 (small / med / large / section). Web: Tailwind's 4-px scale (`space-1` 4 → `space-16` 64). **Coherent.**

Edge safe-zone: both surfaces use 16 px page-edge padding on mobile-class viewports. **Coherent.**

#### 5.2.5 Anti-fake-content posture (cross-surface invariant)

Both surfaces share the anti-fake-content stance:

- ✅ No stock photos
- ✅ No fake testimonials
- ✅ No "users coached" counter
- ✅ No countdown timers
- ✅ No animated illustrations (Lottie etc.)
- ✅ No exit surveys / guilt-trips / dark patterns

This is the brand's emotional-design moat (legacy distillate). UX confirms both surfaces hold it.

#### 5.2.6 Cross-journey continuity test

The Discord-link → web → install → mobile journey (J1) crosses surfaces 4 times. UX validates the coherence at each handoff:

| Handoff | Coherence signal |
|---|---|
| Discord link → web Landing | OG card uses `#FF6B00` (post-reconciliation) + same hero `Progresser plus vite…` → web hero match |
| Web Landing → web /pricing | Same Inter typography, same `#0F0F0F` bg, same accent CTAs |
| Web /dashboard?success=1 → mobile Login | Both surfaces show "WARDEN" wordmark + dark theme + orange accent. Mobile uses display-mono (different font), but the brand name + accent + dark-mode triad makes the brand recognition work. |
| Mobile Login → Cinema Mode | Same accent across screens; HUD primitives carry brand language consistently inside mobile |

**Verdict:** post-Option-B accent reconciliation, the cross-surface coherence holds. Pre-reconciliation, the only break is the orange-shade flicker.

---

## 6. Handoff

### 6.1 Accessibility compliance matrix

#### 6.1.1 Mobile A11Y-005 (touch ≥ 44×44 px) — full audit

| Component / state | Visible glyph | Logical hit area | Pass? |
|---|---|---|---|
| `HudBracket` (clip handle) | 14×26 | 44×44 (invisible padding) | ✅ |
| `CornerTick` (top-left view-mode gesture target) | 14×14 visible | 96×96 hit (gesture-area) | ✅ |
| Card (CardViewScreen tap target) | 200×356 (5.5") / 168×280 (6.0–6.4") | Full Card | ✅ |
| `EngageButton` (primary CTA) | 56×var | ≥56 tall × ≥120 wide | ✅ |
| `CircleBtn` (icon button) | 44×44 | 44×44 | ✅ |
| Segmented-control segment (view-mode toggle) | 44×120 | 44×120 | ✅ |
| Bottom-bar action buttons | 56×72 | 56×72 | ✅ |
| Top-bar buttons (close, sort, account) | 44×44 | 44×44 | ✅ |
| Voice-recorder mic button | 88×88 | 88×88 | ✅ |
| Voice-recorder filled-slot play/delete | 44×44 each | 44×44 | ✅ |
| Sort bottom-sheet radio rows | 44×var (full row width) | 44 tall × full | ✅ |
| Account bottom-sheet rows | 44 tall × full | 44 tall × full | ✅ |
| `EntitlementBanner` "Mettre à jour" CTA | 56×144 | 56×144 | ✅ |
| `SubscriptionRequiredScreen` primary CTA | 56×220 | 56×220 | ✅ |
| Login email / password inputs | 56 tall | 56 tall | ✅ |
| Login "Show password" toggle | 44×44 | 44×44 | ✅ |
| `RotatingTip` content area | n/a — display only | n/a | ✅ (non-interactive) |
| Pause / Cancel processing buttons | 56×144 | 56×144 | ✅ |

**Result:** all interactive elements pass A11Y-005. No touch-target deficiencies.

#### 6.1.2 Mobile A11Y-006 (no color-only state indicators) — full audit

See §2.6 Mobile state pattern catalog. **Result:** every state has a primary non-color signal (icon shape, content change, or position). No state relies on color alone.

#### 6.1.3 Web WCAG 2.1 Level A — full audit

| WCAG criterion | Where addressed | Pass? |
|---|---|---|
| 1.1.1 Non-text content (alt text) | Logo `<img alt="Warden">` on Header; OG image has `alt` set | ✅ |
| 1.3.1 Info and relationships (semantic HTML) | `<nav>`, `<main>`, `<footer>`, `<h1-3>`, `<button>` per legacy distillate | ✅ |
| 1.3.2 Meaningful sequence | Reading order in DOM matches visual; modal content is in DOM order | ✅ |
| 1.4.1 Use of color | All status badges + alerts use icon + text + color (not color-only); §3.2.1 status mapping | ✅ |
| 2.1.1 Keyboard | All Radix primitives keyboard-accessible by default (Dialog, Alert, Badge); custom forms via `<button>` and `<input>` semantics | ✅ |
| 2.1.2 No keyboard trap | Radix `Dialog` traps focus inside but ESC closes; closing returns focus to trigger | ✅ |
| 2.4.1 Bypass blocks | Skip-to-content link in Header; routes `<main>` for jump target | ✅ |
| 2.4.2 Page titled | Per-route `<title>` set in Next.js metadata API | ✅ |
| 2.4.4 Link purpose (in context) | All link copy is descriptive ("See pricing", "Manage subscription"); no "click here" | ✅ |
| 3.1.1 Language of page | `<html lang="en">` on root layout; FR-locked hero is inline `lang="fr"` span | ✅ |
| 3.2.1 On focus | Focus does not trigger navigation or unexpected change | ✅ |
| 3.3.1 Error identification | Inline errors (§3.1.5) include color, icon, and text | ✅ |
| 3.3.2 Labels or instructions | All form inputs have `<label>` with `htmlFor` matching `id` | ✅ |
| 4.1.1 Parsing | Next.js + React produce valid HTML | ✅ |
| 4.1.2 Name, role, value | All custom components use Radix primitives which set ARIA attributes correctly | ✅ |

**WCAG AA contrast (legacy distillate):** text-primary `#F0F0F0` on bg `#0F0F0F` ~16:1 (AAA); text-secondary `#999999` on bg ~5.5:1 (AA); orange `#FF6B00` on bg ~5.0:1 (AA-large/bold) post-Option-B reconciliation.

**Reduced motion:** Radix primitives respect `prefers-reduced-motion` automatically. Tailwind `motion-safe:` and `motion-reduce:` utilities used where animation is added (which is rare per Direction A).

**Result:** WCAG 2.1 Level A passes. AA contrast also passes. **Testing strategy** (per legacy distillate): Browser DevTools contrast check, manual keyboard tab-through, Chrome device mode + real Android phone, `npx lighthouse` accessibility in CI, VoiceOver pass before launch. Full audit deferred post-MVP.

### 6.2 FR-to-UX traceability

Every FR in the PRD that has a UX surface is accounted for here. FRs that are pure backend / pipeline / tooling are correctly absent from UX scope and noted as "Not UX."

#### 6.2.1 Mobile FRs (33)

| FR ID | UX Section | UX Coverage |
|---|---|---|
| `mobile-AUTH-001` | §2.5.6, §4.1.1 | LoginScreen + Google + Email/Password |
| `mobile-AUTH-002` | §2.5 | Entitlement validation (state visual treatments) |
| `mobile-AUTH-003` | §2.5.4, §4.1.10 | SubscriptionRequiredScreen |
| `mobile-AUTH-004` | §2.5.2 | offline-grace ≤30d visual + day-31 force re-auth |
| `mobile-AUTH-005` | §2.5.4 (reassurance copy), §4.1.10 | Session-data preservation reassurance |
| `mobile-AUTH-006` | §2.5.3, §4.1.10 | EntitlementBanner payment-failed |
| `mobile-IMPORT-001` | §2.2.1 | Cold-start Import CTA |
| `mobile-IMPORT-002` | §4.1.2 (`CARDS.codec_unsupported_*`) | Codec rejection modal |
| `mobile-AUTO-SLICE-001` | §2.3.2 | Long-processing screen + tips |
| `mobile-AUTO-SLICE-002` | §2.3.2 (stage labels in §4.1.5) | Map identification stage |
| `mobile-AUTO-SLICE-003` | §2.2.4, §2.1.2 | Unknown-map Card + Cinema view-mode disabled |
| `mobile-AUTO-SLICE-004` | (transparent — no UX) | Lobby auto-removal happens before Card View renders |
| `mobile-CARD-001` | §2.2.2, §2.2.3 | Adaptive grid + per-card composition |
| `mobile-CARD-002` | §2.2.5, §4.1.3 | Sort dropdown + V2 graceful degradation |
| `mobile-CARD-003` | §2.2 (tap → Cinema) | Card tap navigation |
| `mobile-CARD-004` | §2.2.1 | Cold-start two-path |
| `mobile-CARD-005` | §2.4 | Manual-clip-from-timeline (Decision #UX-14) |
| `mobile-CINEMA-001` | §2.1, §4.1.7 | Cinema Mode + reveal-on-tap |
| `mobile-CINEMA-002` | §2.1.2 | Segmented control + double-tap gesture |
| `mobile-CINEMA-003` | §2.1.2 | Default to Full when map_name unknown |
| `mobile-CINEMA-004` | (transparent — preference persisted) | View-mode persistence; no UX surface beyond initial state |
| `mobile-CINEMA-005` | §2.1.5 | Next/Prev episode buttons |
| `mobile-CLIP-001` | §2.1.3, §4.1.8 | Bracket-handle 30s region |
| `mobile-CLIP-002` | §2.4 | Manual clip from any timeline point |
| `mobile-CLIP-003` | §2.1.4, §4.1.8 | 3-slot voice recorder UI states |
| `mobile-CLIP-004` | §2.1.4 (re-record confirmation), §4.1.8 | Re-record overwrite |
| `mobile-CLIP-005` | §4.1.8 (`CLIP.preview_cta`) | Preview before export |
| `mobile-EXPORT-001` | §4.1.9 | ExportShareScreen — local encode, no cloud |
| `mobile-EXPORT-002` | §4.1.9 | Mobile / HD quality tiers |
| `mobile-EXPORT-003` | §4.1.9 (share-sheet handoff) | OS share sheet |
| `mobile-EXPORT-004` | (transparent — encoder-side) | H.264/AAC compatibility — no UX surface |
| `mobile-AUTOSAVE-001` | §2.7 (silent saves), §4.1.5 (`PROC.tip_5`) | Tip surfaces auto-save reassurance |
| `mobile-AUTOSAVE-002` | §4.1.2 (`CARDS.resume_session_toast`) | Resume toast |

#### 6.2.2 Web FRs (FR clusters from PRD §9 Web section + legacy distillate)

| FR cluster | UX Section |
|---|---|
| `web-LANDING-001/002` | §3, §4.2.1, §3.3 (OG metadata) |
| `web-PRICING-001/002` | §3, §3.1, §4.2.2 |
| `web-AUTH-001` | §3.1, §4.2.3 |
| `web-CHECKOUT-001` | §4.2.2 (FR-locked deferred-billing copy) |
| `web-CHECKOUT-002` | §4.2.4 |
| `web-DASHBOARD-001` | §3, §4.2.5 |
| `web-DASHBOARD-002` | §3.2.2, §4.2.5 |
| `web-DASHBOARD-003` | §3.2.4, §4.2.5 |
| `web-DASHBOARD-004` | §3.2.3, §4.2.6 |
| `web-DASHBOARD-005` | §3.5, §4.2.5 |
| `web-WEBHOOK-001/002/003` | (Not UX) |
| `web-ANALYTICS-001` | §3.4 (cookie banner gates analytics load) |
| `web-FR26..29` (Privacy / Terms / cookies / conditional Analytics) | §3.4, §4.2.7, §4.2.8 |

#### 6.2.3 Cross-surface FRs

| FR ID | UX Section |
|---|---|
| `cross-ENTITLEMENT-001` | §2.5 (six-state visual treatments) |
| `cross-ENTITLEMENT-002` | (Not UX — architecture-owned) |
| `cross-ACTIVATION-001/002` | (Architecture telemetry contract — UX confirms T1-coach + T1-active-player UI moments are present in §2.1.2 and §4.1.9) |
| `cross-SCHEMA-001/002` | (Not UX) |
| `cross-READER-APP-001` | §4.1.10 (verifies banlist compliance + flags follow-up #UX-2-followup) |
| `cross-MAP-CONFIG-DELIVERY-001` | (Not UX) |

#### 6.2.4 NFRs UX is responsible for

| NFR ID | UX Section |
|---|---|
| `PERF-003` (toggle ≤ 100 ms) | §2.1.2 (no-player-swap pattern via crop/style) |
| `A11Y-001..004` (web WCAG 2.1 A + AA contrast + keyboard + reduced-motion) | §6.1.3 audit |
| `A11Y-005` (mobile 44×44) | §6.1.1 audit |
| `A11Y-006` (mobile shape/icon non-color) | §6.1.2 + §2.6 catalog |
| `I18N-001..003` (FR mobile, EN web with FR insertions) | §4.1, §4.2 |
| `OBS-003` (no user content in crash reports) | (Not UX — but UX surfaces the no-crash-reporting-V1 manual report path in §5.1) |

### 6.3 Things explicitly NOT in scope (handoff back to architecture / sprint planning)

The following items appeared in the brief or surfaced during UX work but are **NOT** UX-owned. They route to the named owner.

| Item | Owner | Notes |
|---|---|---|
| Reader-App banlist regex relaxation for "abonnement" noun | Architecture | UX flagged `Decision #UX-2-followup`; needs architecture confirmation before §4.1.10 final mobile copy commits. |
| Concrete support email + Discord URL | User content decision | UX flagged `Decision #UX-12 input`; see §6.4. |
| Accent orange reconciliation (Option B `#FF6B00` for both surfaces) | UX recommends; user confirms | UX flagged `Decision #UX-13 confirm`; see §6.4. |
| Password-reset flow inclusion in V1 | PRD/Architecture | UX recommends V1 ships with reset; architecture decides. |
| Bracket-drag max clip duration upper bound (60s recommendation) | Architecture / PRD | UX picks 60s; flag confirmable. |
| Bracket-drag min clip duration lower bound (5s recommendation) | Architecture / PRD | UX picks 5s; flag confirmable. |
| Tip rotation cadence (6s recommendation in 5–8s window) | UX picks; product confirmable | Mid-point of legacy 5–8s. |
| Performance spike pre-PRD result | Architecture spike | If spike returns rung 3 (no auto-slice), §2.4 manual-clip flow becomes the only V1 clip-creation path; CardView toggle defaults to TIMELINE. UX is shipped-ready for either outcome. |
| Sentry / Crashlytics adoption decision | Architecture | If adopted post-V1, replaces §5.1 manual-error path. |
| Onboarding tutorial reintroduction in V2+ | Product | V1 explicitly rejected onboarding (legacy distillate). UX has no surface for this in V1. |
| Push notification design | Product (V2+) | V1 has no push. UX has no surface. |

### 6.4 Follow-up resolutions (LOCKED 2026-05-07)

All eight follow-ups resolved by user input on 2026-05-07. Implementation surface tracked at §6.5.

| # | Question | Resolution |
|---|---|---|
| FU-1 | Support email address | **`support@warden.team`** — used in §5.1 mailto, §4.1.4 mobile account sheet, web Footer "Get help" |
| FU-2 | Warden Discord invite URL | **`https://discord.gg/DpDEyBZw`** — used in §5.1 secondary, §3.3 OG card audience target, §4.1.4 mobile account sheet |
| FU-3 | Accent orange reconciliation | **Option B locked** — `#FF6B00` for both surfaces; web retunes from `#E8731A`; `accent-hover` becomes `#FF8533` |
| FU-4 | Reader-App banlist regex | **Narrowed** — verb forms only (`s'abonner`, `abonnez-vous`); noun `abonnement` permitted in entitlement-state UI labels (`Gérer mon abonnement`, `Abonnement requis` lock) |
| FU-5 | Password-reset flow in V1 | **Ship V1** — Firebase `sendPasswordResetEmail` via inline form inside auth modal; copy + flow in §3.1.5 + §4.2.3 |
| FU-6 | Bracket-drag bounds | **Min 5s, max 60s** locked |
| FU-7 | Tip rotation cadence | **6s** locked |
| FU-8 | Token-change cascade | **Web side** — `apps/web/src/app/globals.css` + `apps/web/tailwind.config.ts` accent var bumps; mobile `tokens.ts` unchanged |

### 6.5 Sprint-3 implementation surface (handoff to bmad-create-epics-and-stories)

UX produces the surface; the next phase (epics + stories) routes implementation. The following NEW components, NEW copy bundles, and TOKEN/REGEX changes emerged from this UX spec and need Sprint-3 stories:

| Surface | New file / change | FR coverage | Story prefix recommendation |
|---|---|---|---|
| Mobile | `apps/mobile/src/features/auth/EntitlementBanner.tsx` | mobile-AUTH-006 | `feat(mobile):` |
| Mobile | `apps/mobile/src/features/auth/SubscriptionRequiredScreen.tsx` | mobile-AUTH-003 | `feat(mobile):` |
| Mobile | `apps/mobile/src/features/auth/OfflineIndicator.tsx` (small composition; can live inside HomeScreen if not extracted) | mobile-AUTH-004 visual | `feat(mobile):` |
| Mobile | French i18n bundle (assuming `apps/mobile/assets/i18n/fr.json`) — strings from §4.1 | I18N-001/003 | `feat(mobile):` |
| Mobile | `apps/mobile/src/shared/services/errorReporting.ts` — mailto formatter targeting `support@warden.team` (FU-1) | OBS-003 manual fallback | `feat(mobile):` |
| Mobile | Account bottom-sheet `Aide` section linking `support@warden.team` (FU-1) + `https://discord.gg/DpDEyBZw` (FU-2) | OBS-003 + community channel | `feat(mobile):` |
| Mobile | Top-bar Cards/Timeline view-mode toggle in CardViewScreen (manual-clip path Decision #UX-14) | mobile-CARD-005 | `feat(mobile):` |
| Web | `apps/web/src/components/dashboard/PaymentWarning.tsx` (composition from `Alert` + `Button`) | web-DASHBOARD-002 | `feat(dashboard):` |
| Web | `apps/web/src/components/dashboard/CancelDialog.tsx` (composition from `Dialog` + `Button`) | web-DASHBOARD-004 | `feat(dashboard):` |
| Web | `apps/web/src/components/dashboard/EmptySubscription.tsx` (or inline in `/dashboard/page.tsx`) | web-DASHBOARD-005 | `feat(dashboard):` |
| Web | `apps/web/src/components/auth/PasswordResetForm.tsx` (FU-5) — composition inside auth modal | web-AUTH-001 | `feat(auth):` |
| Web | `apps/web/src/app/auth/sign-in/page.tsx` — handle `?passwordReset=1` query param success banner (FU-5) | web-AUTH-001 | `feat(auth):` |
| Web | `apps/web/public/og/landing.jpg` static asset (1200×630, 200 KB cap) — uses `#FF6B00` accent (FU-3) | web-LANDING-002 | `feat(landing):` |
| Web | `apps/web/src/app/layout.tsx` Open Graph + Twitter Card metadata additions (and route-specific overrides) | web-LANDING-002 | `feat(landing):` |
| Web | English copy strings (§4.2) embedded inline (no i18n bundle for V1) | I18N-002 | bundled per-component |
| Web | Cookie banner already exists in `apps/web/src/components/layout/CookieBanner.tsx` — UX confirms / refines copy per §4.2.7 | FR web-FR27..29 | `feat(layout):` |
| Web | Footer "Get help" link → `mailto:support@warden.team` (FU-1) | OBS-003 web-side | `feat(layout):` |
| **Web tokens** | **`apps/web/src/app/globals.css` + `apps/web/tailwind.config.ts`** — bump `accent` from `#E8731A` to `#FF6B00` and `accent-hover` from `#F28A2E` to `#FF8533` (FU-3) | A11Y-001 contrast verification re-run | `feat(layout):` |
| **Architecture amendment** | **`.github/workflows/ci.yml` + `apps/mobile/scripts/reader-app-gate.sh`** — narrow banned-string regex from `\babonnement\b` to verb forms `\b(s'?abonner|abonnez-vous)\b` (FU-4) | cross-READER-APP-001 | `feat(infra):` |

### 6.6 What this UX spec does NOT replace

To prevent re-derivation: the existing legacy mock at `docs/design/warden-mocks/Warden.html` continues to be the visual source-of-truth where this doc disagrees on visual rendering (per legacy distillate "mocks WIN on visual"). This UX spec owns:

- Behavior (interaction patterns, gesture rules, state transitions)
- Journeys (flows across screens)
- Copy decks (FR mobile + EN web with FR insertions)
- Component contracts (what each component must do)
- Decisions #UX-1..#UX-14 resolutions

This UX spec does NOT own:

- Pixel-precise layout positioning of HUD glyphs (mocks own this)
- Exact `.html` markup of the warden-mocks reference (mocks own this)
- The HUD primitive implementations under `apps/mobile/src/shared/components/hud/` (codebase owns this; UX inherits)
- The 7 shadcn primitives under `apps/web/src/components/ui/` (codebase owns this; UX inherits)
- The `tokens.ts` exact hex values pre-Option-B reconciliation (codebase owns; UX recommends a value change)

### 6.7 Sign-off checklist

- [x] All 14 escalated UX decisions resolved (§§2–5)
- [x] All 8 follow-up inputs (FU-1..FU-8) locked by user 2026-05-07 (§6.4)
- [x] Mobile + web copy decks complete (§4.1, §4.2) — including locked support email + Discord URL
- [x] FR-locked French insertions preserved verbatim (hero + deferred-billing + savings copy)
- [x] Reader-App banlist regex narrowed (FU-4); mobile copy `Gérer mon abonnement` / `Abonnement requis` LOCKED
- [x] Cross-surface accent reconciled (FU-3): both surfaces anchor on `#FF6B00`; web token bump tracked at §6.5
- [x] Password-reset flow shipping in V1 (FU-5) — copy + flow specified in §3.1.5 + §4.2.3
- [x] All six entitlement states have a visual treatment (§2.5)
- [x] Activation T0/T1 dual-path UI moments confirmed present (§2.1.2 view-mode toggle for active-player T1; §4.1.9 share-sheet for coach T1)
- [x] Manual-clip-from-timeline first-class V1 path designed (§2.4 — Decision #UX-14)
- [x] A11Y-005 touch-target audit passes (§6.1.1)
- [x] A11Y-006 non-color signal catalog complete (§2.6)
- [x] Cross-surface coherence audit complete + reconciliation locked (§5.2)
- [x] V1 manual error-reporting path designed with concrete contacts (§5.1)
- [x] Sprint-3 new-component + token + regex surface enumerated (§6.5)
- [x] FR-to-UX traceability matrix complete (§6.2)

### 6.8 Document status

| Field | Value |
|---|---|
| Status | **complete — locked for handoff to `bmad-create-epics-and-stories`** |
| Locked at | 2026-05-07 |
| Steps completed | step-01-init, step-02-foundations (compressed), step-03-mobile-interactions (compressed), step-04-web-interactions (compressed), step-05-copy-decks (compressed), step-06-recovery-coherence (compressed), step-07-handoff |
| Next phase | `bmad-create-epics-and-stories` (Phase 6 step 5) |
| Path | `_bmad-output/ux-design.md` (per user override) |
| Authors | Stephane (decisions) + UX facilitator (synthesis) |
| Date completed | 2026-05-07 |






