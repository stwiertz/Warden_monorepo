> This section covers unified product strategy across the three Warden apps. Part 1 of 8 of the Warden legacy distillate.

## Unified Product Concept
- Warden = mobile match-review app for EVA After-h (competitive VR FPS); transforms paid game sessions into accelerated learning ("Double XP" metaphor — progress faster while investing less time)
- Three-app product surface: (1) `apps/mobile` Warden = the product (review experience + clip artifact); (2) `apps/web` WardenWeb = the door (subscription portal, Reader App model bypasses 30% store fees); (3) `apps/tooling` desktop Python suite = R&D + reference impl + `map_config.json` producer
- Tagline (French, on web hero, mobile is French throughout): "Progresser plus vite en investissant moins de temps"
- Killer differentiator: 100% on-device processing on mobile; no upload, no cloud cost, no tokens, no waiting; offline-first
- Core loop: import session → auto-slice → navigate to round → minimap review with voice → export standalone clip → share via Discord/WhatsApp where recipient watches inline without installing app
- Defining experience tagline (web): "Subscribe from a Discord link in under 60 seconds"
- Defining experience tagline (mobile): "Clip the play, say what happened, send it to the team"
- Reader App compliance: 100% external monetization (web Stripe) → 0% store commission; mobile contains login screen only — no IAP, no pricing, no plan names; Netflix-style precedent

## Problem Space
- Paid EVA sessions yield slow learning curve because teams "play" without "training"; same mistakes repeat match after match
- Impacts: financial (poor ROI on paid sessions), progression (flat curve), emotional (player + coach frustration), engagement (abandonment risk)
- Existing tools fail: video editors complex/not EVA-configured/slow; YouTube lacks minimap mode + integrated review workflow; EVA Battle Plan = cloud upload latency + token costs + unused stats
- Identified gap: no tool specifically built for mobile EVA review with workflow optimized for non-professional coaches
- Web-side problem: monetization needs to bypass 30% store fees while respecting App Store/Play Store "Reader App" rules

## Differentiators
- EVA-specialized: pre-configured ROI templates and map detection (14 EVA maps)
- Minimap mode: full-screen tactical overhead view; no competitor offers this on mobile
- 100% on-device: fixed cost, offline, no upload latency
- Voice-first: 3-slot (before/during/after) recording, minimal friction for tired coach
- Standalone clips: recipient does not need the app; viral loop via Discord/WhatsApp inline playback; clip = product = viral hook (Discord-native, no watermark needed)
- No reference exists for tactical-overhead-VR-replay-with-voice — Warden defines this format

## Target Users (canonical personas — used by both mobile and web docs)
- Primary — Coach Thomas, 26: sports/physio coach, FPS 10y, EVA 2y, ex-COD coach; reviews evenings on PC at home in 30-60min sessions; pain = juggling video player + notes + editor, uses 5% of generic-tool features, irregular reviews; wants unified EVA workflow + minimap mode + fast voice-clip export; visits WardenWeb only for billing (rare, after Discord coupon link)
- Secondary — Passive Player Lucas, 17 lycéen, competitive: excellent reflexes/aim, follows instructions, lacks game-vision; thinks progress = play more; needs to be SHOWN; receives clips via Discord, never installs app; web: visits WardenWeb only out of curiosity — landing copy must work for non-coaches too (conversion path passive→active→subscriber)
- Secondary — Active Player Lucas/Maxime, 22 (web doc names "Lucas, 22"; mobile doc names "Maxime, 22" — same archetype, name discrepancy noted): high-division + assistant coach; proactive analyst; pipeline passive→active→coach; imports coach reviews + watches solo to develop analytical capability; uses app; subscribes individually (no team billing in V1)
- Discovery channels: word-of-mouth in EVA Discord community, FR/BE coach network, free-month coupons to monthly local-league winners ("dealer of comfort" strategy); no paid ads at MVP

## Business Targets & KPIs
- 3-month: 20 paying coaches; 140€ MRR (mobile-side metric); MVP validation
- 12-month: 100 subscribers; 700€ MRR
- Churn: <15% (3mo) → <10% (12mo); web tracks monthly churn <15%
- Coupon→Retained ≥10% after trial
- Per-coach reviews/week ≥1; clips per review 3-5 (3mo) → 5+ (12mo)
- Activation (mobile-side): first clip exported <5min
- Conversion funnel (web): Awareness (landing) → Interest (pricing) → Intent (checkout) → Drop-off → Conversion (Coupon→Paid) → Expansion (Monthly→Yearly upgrade)
- Tracked ratios: Visit→CheckoutStart, CheckoutStart→Complete, Coupon→Retained
- Critical UX moment (web): "I won't be charged yet" (Stripe deferred billing display when coupon applied) reduces checkout anxiety

## Pricing & Plans
- Monthly: €7.99/mo (web doc — note pricing 7€/mo also appears in mobile product brief; €7.99 is the live web value)
- Yearly: €79.90/yr (~17% savings vs 12×monthly = €95.88; positioned "économisez 2 mois")
- Coupons: Stripe promotion codes; passed to Checkout Session via URL param; auto-shown on pricing page when present
- Trial model: card capture upfront + coupon-based free period; "Vous ne serez pas débité avant le [date]"
- Coupon admin V1: Stripe dashboard only (no in-app admin UI)
- Pricing NEVER shown inside the mobile app (Reader App constraint, FR33)

## Scope Tiers Across All Apps
- IN MVP (mobile): auto-slicing, Card View + sorting, Cinema Mode, 3-mode view toggle, 30s clip + 3-slot voice, Mobile/HD export + standalone MP4, OS share, auto-save + crash recovery, Firebase auth + isPaid validation + 30d offline cache
- IN MVP (web): Landing, Pricing+Checkout, Account Dashboard (email/next-payment-date/portal-handover), Privacy/Terms, Cookie Banner; revised Epic 5 portal-first (history/upgrade/cancel via Stripe Customer Portal — NOT custom UI)
- IN MVP (tooling): existing Python CLI suite supports R&D iteration; produces `map_config.json` consumed by mobile; ROI tuning + accuracy validation tools shipped
- OUT V1 (mobile): OCR scores/kills (V2), advanced ROI composition (V2), vertical export (V2+), custom ROI templates (Desktop), review import mode (V2), Pick & Ban tool (V2+), iOS (Phase 2), multi-view clip export (V2), export queue background encoding (architecture supports), Discord stream group review (Desktop/Phase 3), advanced Desktop analysis (Phase 3)
- OUT V1 (web): Discord OAuth (Google/Email sufficient), Coupon Admin UI (Stripe dashboard suffices), Custom Analytics Dashboard (Firebase Analytics suffices), Team/Group Billing, Localization (English UI + French tagline), self-serve account deletion, churn survey, in-dashboard coupon redemption (only at checkout)
- V2 Growth (web): Discord OAuth, Coupon Admin UI, account deletion button, advanced analytics dashboard
- V3 Vision (web): referral system (free months for inviters), team subscriptions, full French localization

## Marketing & Distribution
- Channel: Discord word-of-mouth + coupon links among EVA After-h coaches; niche; FR/BE focus
- No paid ads at MVP
- Free-month coupons to monthly local-league winners as growth lever ("dealer of comfort")
- Clip artifact itself is viral hook — recipients watch inline without installing, no watermark needed
- Discord owns social — Warden has NO in-app social features (anti-pattern)

## Three-App Coherence Principles
- Mobile = the product, Web = the door, Tooling = the lab
- Mobile UI French (coach audience); web UI English with French tagline; unified PRD English (downstream BMad agent input)
- Same Firebase project across mobile + web (Auth + Firestore region `europe-west` GDPR-locked)
- Tooling produces `map_config.json` artifact that flows through Firestore (or bundled — open question) to mobile; tooling is also reference impl for mobile detector port (Python → TypeScript/Kotlin)
- WardenWeb's "Reader App" architectural constraint propagates to mobile (login screen only, no IAP UI, isPaid boolean entitlement)
