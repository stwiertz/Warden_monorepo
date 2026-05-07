> This section covers unified UX design surface across mobile and web. Mobile uses Tactical HUD; web uses Clean Minimal — surfaces both. Part 6 of 8 of the Warden legacy distillate.

## UX Direction Split (Two Visual Languages, One Brand)
- Mobile: "Tactical HUD" direction (revised 2026-05-01) — dark-first military-recon vocabulary; bracketed surfaces, mono tactical labels, accent-as-1px (NEVER as fill), subtle scanlines on UI surfaces; ~95% dark / 5% accent ("whisper not shout")
- Web: "Clean Minimal" direction (Direction A, chosen over B Bold Tactical/uppercase/grid and C Warm/emoji) — soft borders, rounded cards, subtle orange accents, generous whitespace; gaming-native via dark theme without heavy-handed tactical typography; aligns with Stripe Checkout's clean aesthetic for seamless handoff
- Rationale split: mobile is the product (long-form review experience, deserves immersion); web is the door (must be invisible, ship-speed); the two visual languages are intentional and not in conflict
- Both use dark mode default; both use Warden orange as accent; both target gaming audience (no SaaS-light feel)
- Unified UX agent task: produce single ux-design-specification.md that captures both surfaces while honoring their different roles

## Mobile Design Tokens (Tactical HUD)
- Color tokens (canonical hex):
  - bg `#0a0a0d`, surface `#101014`, elev `#15151a`, elev2 `#1c1c22`, line `#26262e`
  - text `#F0F0F0`, muted `#8a8a92`, dim `#52525a`
  - accent `#FF6B00` (default orange), accent-soft `rgba(255,107,0,0.18)`, accent-dim `rgba(255,107,0,0.5)`
  - team-blue `#3a8eff` / `#5b8aff`, success `#22C55E` (share-complete toast only), error `#EF4444`
- Accent themeable runtime via Zustand-backed ThemeProvider exposing `--hud-accent` CSS-var-equivalent (Orange / Cyan / Red presets + free picker)
- Typography:
  - Roboto sans (400/500/700) — body + UI labels
  - JetBrains Mono (400/500/700) — timecodes/scores/tactical labels — UPPERCASE with 1.5–2.5 letter-spacing
  - Falls back to platform mono if Google Fonts not loaded but tactical aesthetic depends on JetBrains Mono
- Type scale: display-mono 22px tracking 4 (WARDEN wordmark), heading-mono 16px tracking 1.5 (LOGIN, PREPARING CLIP), subhead-mono 12px tracking 2 (top brand strip, card map names), value-mono 11-13px (field values, stats, timecodes), body 13-14px line-height 1.5, stamp 9-11px tracking 1 (top-row labels, meta lines), score 16px with text-shadow (episode card readouts)
- Tactical decoration motifs: HUD brackets (1px L-shaped corners 10×10), scanlines (repeating-linear-gradient overlay, NEVER on video frames), corner ticks (14×14), recon-grid (32px dotted SVG), reticle (4-prong 64×64 dashed accent ring), clip handles (14×26 SVG L-bracket reticle-style), status pills (1px border + mono ALL-CAPS), glow (box-shadow 0 0 12-18px rgba(255,107,0,0.25-0.6))
- Spacing base 4px; small 4 / med 8 / large 16 / section 24; edge safe zone 16px
- Component tier strategy: tactical primitives (`HudBracket`, `Stamp`, `Field`, `CircleBtn`, `Screen`, `Reticle`, `WardenMark`, `BigMark`, Icon set in `src/shared/components/hud/`) → standard UI (custom-themed buttons/toasts/modals/sheets, never library defaults) → custom core (video player, minimap view, view-mode toggle, clip creation, voice recorder, timeline scrubber, episode card)

## Web Design Tokens (Clean Minimal)
- Theme: dark mode default (Tailwind `darkMode: "class"` + CSS vars)
- Colors: bg `#0F0F0F`, surface `#1A1A1A`, surface-elevated `#252525`, border `#333333`, text `#F0F0F0`, text-secondary `#999999`, accent (Warden orange) `#E8731A`, accent-hover `#F28A2E`, success `#22C55E`, warning `#F59E0B`, error `#EF4444`
- Contrast: text-primary on bg ~16:1 (AAA), text-secondary ~5.5:1 (AA), orange ~4.8:1 (AA large/bold)
- Typography: Inter (Google Font) — H1 800/32-48px, H2 700/24-32px, H3 600/20-24px, body 400/16px, small 500/14px, badge 600/12px; line-height 1.2 headings, 1.5 body
- Spacing base: 4px tokens (space-1 4px → space-16 64px); page padding 16px mobile / 32px desktop; max content width 1024px centered
- Border radius: buttons 6px (slightly sharp/tactical), cards 8px, badges 4px, full round only avatars/status dots
- Touch target: min 44x44px (`min-h-11 min-w-11`)
- Breakpoints: ONLY two — mobile (default, no prefix) + `md:` (768px+); no tablet-specific layout
- Layout pattern: stacked on mobile, side-by-side cards on desktop; full-width hero, single-column dashboard with wider card on desktop

## Component Coverage Strategy
- Mobile (Tactical HUD): tactical primitives in `src/shared/components/hud/` + custom core video player; library-default components NEVER used (always custom-themed)
- Web (Clean Minimal): 100% of MVP needs covered by 7 shadcn primitives (Button, Card, Dialog, Input, Badge, Alert, Skeleton); NO custom components for V1; compositions (hero, plan-selector, status-card) built directly from primitives — extract later if pattern repeats
- Mobile note: mock reference at `docs/design/warden-mocks/` static HTML/JSX (Warden.html opens 9 screens); mocks WIN on visual when this doc disagrees; this doc owns behavior + journeys + component contracts

## Mobile UX Architecture (Two-Layer)
- Card View (episode triage, Netflix-style grid with result frames as thumbnails)
- Cinema Mode (immersive review, YouTube-fullscreen-style, reveal-on-tap controls auto-hide 4s)
- Cold start: two clear paths "Resume last review" / "Import new session"; never blank state; if zero sessions → single prominent button "Import your first training session"
- Card sorting (triage-first): Temporal (default), Orange biggest win, Blue biggest win, Closest map; sort persists via `prefs.sortOrder`; sort sets next/prev order in Cinema Mode; score-based sorts gracefully degrade to temporal until OCR ships
- Cinema Mode navigation: explicit Next / Previous / Maps buttons (rejected swipe gestures because conflict with timeline scrubbing); single tap toggles controls overlay; double-tap top-left = power-user view-mode cycle Full → Minimap → Minimap+HUD
- Orientation: NO orientation lock; landscape = video 100% + reveal-on-tap controls; portrait = video top + persistent controls below
- Screen sizes: 5.5" → 1-col Card grid; 6.0-6.4" → 2-col; 6.5"+ → 2-col with more metadata
- Reference device: Poco X5 (6.67")

## Web UX Surface (Three Routes + Portal Handoff)
- Landing (`/`): SSR + cached, full-width hero, single CTA → /pricing, mobile-first, WCAG-A
- Pricing (`/pricing`): client-interactive, 2 plan cards (monthly €7.99 / yearly €79.90), savings copy, auth modal overlay (Google + Email/Password), accept Stripe coupon URL param, redirect to Stripe-hosted Checkout
- Dashboard (`/dashboard`): protected, fresh reads from Firestore (no onSnapshot), shows email + plan + status badge + next payment date + "Manage Subscription" button → Stripe Customer Portal; payment-failure warning banner; cancel-info banner with Resubscribe CTA
- Stripe Customer Portal handles: payment history (FR17), upgrade monthly→yearly with proration (FR18), cancellation (FR19), payment-method updates (FR20)
- Header: logo left + links right (Home, Pricing OR Dashboard if signed-in); sticky; "Sign in" when anonymous, "Sign out" when authenticated; active link orange
- Footer: centered Privacy / Terms / copyright; same on every page

## Mobile Defining Experience: Clip Creation
- Coach mental model: video editing tool (timeline-centric, non-destructive, export-oriented, tool-not-platform)
- Clip creation flow: tap "clip" → 30s region appears centered on current playback → drag bracket handles to refine → optional 3-slot voice → preview → confirm; <10s to define
- Voice recorder 3 slots — independent, all optional:
  - Before (tap "before" → still frame of clip first frame + blinking mic + red dot → audio over still frame plays before clip)
  - During (tap "on clip" → countdown → clip plays + recording; if coach keeps talking past clip end, last frame freezes while audio continues)
  - After (tap "after" → still frame of clip last frame + blinking mic → audio over still frame plays after during-overflow)
- Tap-to-start, tap-to-stop; no auto-stop, no silence detection; silent clips skip all voice segments
- Exported clip structure: `[before voice + still frame] → [clip video + during voice] → [frozen frame + during overflow] → [after voice + still frame]`
- The clip = the product = the viral hook; export friction (no format/quality/title pre-flight, one tap to share, OS sheet handles)

## View Mode System (Mobile)
- 3 modes (Stories 7.1-7.3+7.6):
  - Full (source video, no crop, replaces original 'pov')
  - Minimap (cropped to map ROI from detection config)
  - Minimap+HUD (minimap crop + KDA + Score overlays drawn from `map_segments` data)
- Top-level Full↔Minimap segmented control + HUD sub-toggle (only active when top-level=Minimap); double-tap top-left cycles all 3
- Persisted via `prefs.viewMode` and `prefs.minimapHud` in MMKV
- Toggle target <100ms = crop/style change on same expo-av source (NFR2) — no player swap

## Web Button & Feedback Patterns
- Button hierarchy: primary=orange-fill (one per page section, full-width-in-cards on mobile), secondary=ghost/outline gray, destructive=ghost red (in confirmation dialogs only), link=text-only orange-on-hover
- Feedback: success=transient banner/redirect green; error=red alert top-of-content; warning=amber alert with action button (persists until resolved, not dismissible); loading=skeleton matching final shape
- Modal patterns: auth modal (Google + email/password Dialog), upgrade confirmation (proration), cancel confirmation ("access until [date]"); overlay-click closes
- Reduced motion: respect `prefers-reduced-motion` (no animations for MVP anyway)
- Empty states: dashboard with no subscription → "No active subscription" + link to pricing; canceled → status + "Resubscribe" button

## Mobile Feedback & Interaction Patterns
- Success toast bottom 3s auto-dismiss; minor error toast 5s red; critical error blocking modal (e.g., incompatible format)
- Short processing inline progress; long processing (auto-slice) full-screen progress + rotating tips every 5-8s
- Processing screen rotating tips: "Double tap top left to switch to minimap"; "Drag clip handles to adjust"; "Add voice before/during/after clip"; "Sort by closest score for important rounds"; "Progress saved automatically"
- Bottom sheet rules: never covers >40% (video stays visible), drag-down dismisses, dark surface + orange separator
- Gesture rules: every gesture has button equivalent; no hidden gestures required for core
- Export UX two-phase design: MVP Option 1 = encode immediately, "Preparing clip..." progress, share sheet opens when done (Story 5.4); Goal Option 3 = queue clip for background encoding, subtle queue indicator "2 ready, 1 processing" (deferred post-MVP)

## Inspirations & Anti-Patterns
- Mobile inspirations: Discord (dark content-first, inline media, no onboarding), YouTube (scrub bar, chapter markers = episodes, double-tap skip muscle memory, fullscreen toggle), Netflix (episode grid mental model)
- Mobile anti-patterns: tiny overlay minimap (current failure mode — must be FULL-SCREEN), export friction, onboarding tutorials, in-app social features (Discord owns social), productivity UX language (no "projects/workspaces/dashboards")
- Web rejected directions: Bold Tactical (uppercase/grid — felt heavy-handed for billing context), Warm/emoji (off-brand for gaming)
- Web anti-patterns: long scrolling landing with sections / testimonials / app screenshots (app not finished, gaming audience sees through generic imagery), feature comparison tables (only 2 plans differ by billing cycle), animated illustrations / Lottie (delays ship), hamburger menu (only 2-3 nav links), tablet-specific breakpoint
- No reference exists for tactical-overhead-VR-replay-with-voice — mobile defines this format; format itself is viral hook in Discord (no watermark needed)

## Emotional Design — Mobile
- Dominant emotion: purposeful immediacy ("let's see what went wrong" not "let me set up a review session")
- Secondary: momentum (after exporting, return to exact timeline position; never celebrate completion; feed next action; review feels like scrubbing replay in competitive game — quick, almost addictive)
- Anti-chore: no mandatory fields, no "save before closing" dialogs, no quick interactions blocked
- "Review is play not work": dark game-adjacent aesthetic vs productivity software
- The voice IS the tone (Warden never frames or labels feedback; coach's recording carries authority/casualness)
- Trust via reliability: state persistence is invisible — close mid-review, come back tomorrow, everything intact

## Emotional Design — Web
- Boring is good — subscription portal should be invisible
- No dark patterns: no fake urgency, no countdown timers, no hidden cancellation flow, no guilt-trip on cancel ("coaches talk to each other on Discord — one bad experience spreads fast")
- Error = action — every error tells the user what to do next; no dead ends
- Ship working, polish later — no fake screenshots, no testimonials, no stock photos of "happy teams"
- Trust through transparency — show billing dates/plan/status; no surprises
- Stage emotions: Landing=Clarity, Pricing=Confidence, Checkout=Safety (delegated to Stripe brand), Dashboard=Control, Error=Calm
- Defining experience tagline: "Subscribe from a Discord link in under 60 seconds"

## Mobile User Journeys
- J1 Coach happy path: import 1h20 → 90s auto-slice → Card View 8 maps lobby auto-removed → tap problem round → Cinema Mode → toggle Minimap → record voice "Lucas your flank is open" → export Mobile quality → share Discord → 15min total → done
- J2 Coach interruption: mid-review, app closed; 2h later reopens → exact map + position + comments-in-progress preserved → finish in 5min
- J3 Passive Player Lucas: Discord notification → tap clip → inline playback (no app install) → minimap + coach voice plays → "Ok compris, je me cale sur toi" → corrects next session
- J4 Active Player Maxime: imports session → auto-slice → toggles Full/Minimap solo without coach commentary → discovers patterns → develops analytical capability; identical to coach UI minus export step
- J3 lives entirely in Discord/WhatsApp; Warden UX responsibility ends at share sheet
- J4 partially supported in MVP (no review-import mode for coach annotations); review-import deferred to V2

## Web User Journeys
- J1 New Subscriber via coupon: Discord link `?coupon=XXX` → Landing (5s) → Pricing (auto-applied coupon, 5s) → Auth modal Google/Email (10s) → Stripe Checkout w/ deferred billing date (15s) → /dashboard?success=1
- J2 Returning Subscriber: visits site → session cookie auto-signs in → Dashboard → "Manage billing" → Stripe Customer Portal → returns to /dashboard
- J3 Payment Failure Recovery: Stripe webhook `invoice.payment_failed` → Firestore `status=past_due` → user dashboard shows warning banner + "Update payment method" button → Stripe Customer Portal → card update → Stripe auto-retries → next visit shows Active
- J4 Cancellation: Dashboard → Cancel → confirmation dialog "access until [date]" → Stripe cancel-at-period-end → status badge "Canceling" → period end → webhook `subscription.deleted` → status "Canceled" + Resubscribe path; NO exit survey for MVP, NO guilt-trip
- J5 Passive→Active Conversion: Lucas receives clip on Discord → curious → Landing (must work for non-coaches too) → Pricing → same checkout flow as J1
- Status badge mapping: green=active, amber=past_due, red=canceled, gray=canceling

## Components Catalog (Mobile)
- Video Player (Cinema Mode), View Mode System, Timeline Scrubber, Clip Region Selector (30s default with bracket handles), Voice Recorder (3 slots), Episode Card, Sort Dropdown, Export Progress (MVP Option 1 modal vs Goal Option 3 queue indicator)

## Components Catalog (Web)
- shadcn primitives (Button, Card, Dialog, Input, Badge, Alert, Skeleton)
- Feature folders: auth/ (SignInForm, GoogleSignInButton, AuthGuard); checkout/ (PlanSelector, CouponInput, CheckoutForm); dashboard/ (SubscriptionCard, PaymentWarning); layout/ (Header, Footer, CookieBanner)
- PaymentHistory / UpgradeButton / CancelDialog removed from scope post-Sprint Change → portal-first

## Accessibility Strategy
- Mobile: target WCAG AA where applicable to mobile video review; soft white #F0F0F0 on #101014 = ~17:1 (exceeds AAA); secondary ≈ 7:1 (exceeds AA); 44x44 min touch targets; no color-only indicators (every state has shape/icon/content change as primary signal); respects system font scaling; intentionally skipped: TalkBack/VoiceOver (product inherently visual), audio descriptions (user-generated content), keyboard navigation (mobile-only); motion sensitivity: blinking mic uses icon + color, not animation alone
- Web: WCAG 2.1 Level A — color contrast AA, keyboard nav (Radix primitives default), 2px orange focus-visible outline, semantic HTML (`<nav>`/`<main>`/`<footer>`/`<h1-3>`/`<button>`), labeled inputs, status badges with text+color (not color-only), `prefers-reduced-motion`, skip-to-content link, alt text on logo
- Web testing strategy (pragmatic for MVP): Browser DevTools contrast check, manual keyboard tab-through, Chrome device mode + real phone, `npx lighthouse` accessibility in CI, VoiceOver pass before launch; full audit deferred post-MVP

## Cross-Platform Design Coherence
- Both surfaces share: dark mode default, Warden orange accent, gaming-audience tone, no SaaS-light feel, anti-fake content (no stock photos, no testimonials)
- Differences are role-driven: mobile = the product (tactical immersion); web = the door (clean handoff to Stripe)
- Coupon flow is the bridge: web converts, mobile delivers the value; UX must feel coherent across hand-off (Discord link → web checkout → install/login mobile → review)
