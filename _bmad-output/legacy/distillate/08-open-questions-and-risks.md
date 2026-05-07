> This section consolidates open questions, risks, conflicts, and rejected alternatives carried forward to unified planning. Part 8 of 8 of the Warden legacy distillate.

## CONFLICTS (Must Be Resolved in Unified Architecture)
- **`users/{uid}` Firestore document schema split**: mobile reads `isPaid: boolean`; web writes rich snake_case schema (`status`, `plan`, `current_period_end`, `stripe_subscription_id`, `stripe_customer_id`, `redeemed_batches`). Unified architecture must pick one model. Mobile architecture lists `contracts/user-doc.schema.json` as target. Possible paths: mobile reads `status === "active"`; web writes denormalized `isPaid` field; Cloud Function syncs derived field. See `05-architecture-cross-cutting.md`
- **Map count discrepancy**: project-sprint.md says 14, map-config-generator spec says 15, `frame_labeler.py:19-34` `MAP_LABELS` lists 14 (canonical). Unresolved.
- **Active player persona name**: mobile doc names "Maxime, 22"; web doc names "Lucas, 22" — same archetype, different names. Unified persona doc must pick one (or distinguish them).
- **Pricing**: mobile product brief mentions "7€/month or 70€/year"; web doc states "€7.99/mo and €79.90/yr". Web values are live (Stripe-configured); mobile brief is older.
- **Tooling project-sprint vs reality**: project-sprint.md says Tool 1, Tool 3, Tool 4 are "Not Started" but working implementations exist. Sprint tracker not updated to reflect actual implementation path (hashing-based map-id approach replaced original "Pixel Finder" plan).

## OPEN QUESTIONS — Cross-Cutting
- `map_config.json` runtime delivery to mobile: Firestore-fetched (legacy mobile preference, allows config tuning without app release) vs bundled-as-Metro-asset (simpler, no online dep) vs hybrid. DECISION REQUIRED in unified architecture.
- `map_config.json` schema-version field strategy: sidecar `<video>.matches.json` uses `schema_version: 1` but main `map_config.json` has no version field.
- `minimap_identification.configs[]` and `hud_versions[]` runtime delivery: currently in `config.yaml`, not in `map_config.json` — should they be merged into the unified config artifact, or stay separate?
- Should `users/{uid}` Firestore writes also include `email` field, or is Auth-derived sufficient (FR13 displays account email)?
- Firebase project config (apiKey/authDomain/projectId): mobile artifacts don't specify — must come from monorepo shared config or env. Where does this live in the monorepo (packages/contracts? apps/{mobile,web}/.env.example?)?
- Tooling mobile port: when does `apps/tooling` Python code get ported to TypeScript/Kotlin for mobile? Story 7.5 lands JS detector logic; tooling stays as R&D tool.

## OPEN QUESTIONS — Mobile
- Lib versions not pinned (Expo manages compatibility, fixed at init)
- Foreground Service Android: Expo config plugin vs `expo-task-manager` — to evaluate
- iOS Phase 2: validate FFmpeg fork config plugin works on iOS build
- Optional follow-up: ultra-review rewritten Epic 7 in epics.md once Story 7.5 lands (any AC tweaks)
- `firebase/auth` `getReactNativePersistence` removed in v12 — must adapt mobile auth persistence approach (brownfield)

## OPEN QUESTIONS — Web
- Coupon Admin UI: Stripe dashboard for V1; self-serve admin UI deferred to V2
- Account deletion self-serve button deferred (V1 = manual via support email)
- Custom analytics dashboard deferred (V1 = Firebase Analytics)
- Discord OAuth deferred V2 (Google/Email sufficient V1)
- Full French localization deferred V3 (V1 = English UI + French tagline)
- Team subscriptions deferred V3
- Referral system deferred V3
- Monitoring/alerting beyond Vercel Analytics deferred post-MVP
- Advanced caching strategies deferred post-MVP
- Formal accessibility audit deferred post-MVP

## OPEN QUESTIONS — Tooling
- When does `bsd_roi_debugger.py` adopt the per-video output subfolder convention?
- Future "new source" extension for non-video Tool 2/Tool 3 inputs in TUI launcher
- Auto-detection vs manual map selection in minimap-view-mode (currently manual; auto deferred to match-preview)
- match-preview Step 3-4 deferred items: representative-frame sampling offset within segment, confidence threshold (Hamming cutoff) location in config, unpaired start/end handling rules, progress-dialog cancel semantics, sidecar schema version + field list, `detect_transitions()` return shape (dataclass vs dict-list), how `run()` composes the two
- Persisting generation resolution into `map_config.json` (silent mismatch risk if Tool 3 re-run at non-default resolution)
- Multi-method hash ensemble; multi-ROI fingerprint (combining HUD + score-screen) if no single ROI achieves zero collisions
- `map_config_generator.py` (legacy) eventual deprecation in favour of `hash_comparator.py`
- `--fail-on-incorrect` flag for `hash_validator.py` (CI gating)
- Pre-normalize anchor crop width more aggressively if shift variance exceeds tolerance

## RISKS — Cross-Cutting
- HIGH: Stripe webhook sync data integrity (web) — mitigated by idempotent handlers + signature verification + retry; resolved via Epic 4 dual-strategy idempotency
- HIGH: ffmpeg-kit-react-native deprecated Jan 2025 / archived June 2025 — community fork `jdarshan5` actively monitored, Plan B = custom native module via Expo Modules API
- MEDIUM: `users/{uid}` schema split — must resolve before unified mobile↔web release; risk of subscription state desync
- MEDIUM: `map_config.json` schema drift — without unified contract validation, tooling output and mobile consumer can drift
- MEDIUM: Process killed by Android OS in background — foreground service notification, save state, resumable from checkpoint
- MEDIUM: Foreground Service Android config — additional Expo config plugin or `expo-task-manager` evaluation
- MARKET: niche size — validate 20 early-adopter coupons in 3mo
- RESOURCE: solo dev — ultra-lean MVP, Firebase simplifies backend
- TECHNICAL: React Native bridge perf — native modules if overhead too high
- TECHNICAL: FFmpeg/OpenCV mobile perf — PC prototype first (validated via R&D 2026-04 on KDA/HSV + pHash methodology)

## RISKS — Mobile
- LOW: Keyframe spacing variable — long-GOP black-screen detector fallback
- LOW: Map not identified by pHash — mark `map_name='unknown'`, navigation still works
- LOW: Detection config Firestore unreachable — MMKV cache, then bundled default config
- LOW: Codec unsupported at import — strict validation + clear error

## RISKS — Web
- Data security ("vibe coding risk"): Firestore rules + server-side validation + no client-side secrets — Epic 7.1 deploys rules to production (carried debt)
- Auth token leakage: Firebase Auth best practices + secure HttpOnly cookie handling
- PlanCta hydration mismatch (`disabled={null}` vs `disabled={true}`) — known issue, scheduled in Story 7.2

## RISKS — Tooling
- questionary TTY requirement on Windows — silent failure if launched via pipe/redirect; needs proper terminal
- `cv2.VideoCapture` may fail on H.265 / unusual containers; user must transcode
- VFR seek via `CAP_PROP_POS_MSEC` is approximate; exact-frame seek out of scope
- Non-16:9 source aspect ratio: ROIs at 1920×1080 may not correspond to sensible HUD layout; warn + continue
- Map-name ROI dimensions may need tuning per-map; `--preview` flag exists for visual catch
- Hash collision risk: adjust ROI to capture more discriminating text OR increase canvas_size
- `score_offset` (14.5s) past `last_in_game_timestamp` can exceed clipped video duration — handled by exception catch
- Rendering compositing in Python/NumPy fine at 720p but inadequate at 4K (out of scope)
- No automated test framework — all tools manually validated
- Imagehash hex_to_hash failure → wrapped in try/except with clear error pointing to map_config corruption
- showinfo regex `pts_time:(\S+)` is stable across FFmpeg versions but is brittle external contract
- Frame/timestamp sync risk in raw-pipe approach with B-frame reordering; mitigated via `-vsync 0`
- Reference-frame choice in consensus hash: first sample as alignment reference; if outlier, skews result — mitigation is consistent alphabetical ordering
- `imagehash.ImageHash(bool_array)` constructor varies across versions
- HUD-brightness threshold (`hud_brightness_max`) is global; future map with bright HUD background near KDA could trigger false-end detections
- KDA ROI vulnerable to prolonged occlusion (extended killcam, victory cinematics) → could bump `end_confirm_frames` if observed
- Threshold-hash binarization left in codebase as opt-in despite negative empirical result
- pHash cross-video inconsistency (same map dist=0 vs dist=90 across recordings) is the root reason for `--force-method dhash` operational default
- Known-failure videos used as regression cases: frozen.mp4 (~9min cascade gaps), lvlaste.mkv (70min, GOP ~8.3s, missed end at ~17:19s)

## BROWNFIELD ISSUES PARKED FOR PHASE 6 TRIAGE
### Web
- Stripe API version pin mismatch: code pins `"2026-03-25.dahlia"` while installed `@stripe/stripe-js` types are `"2026-04-22.dahlia"`
- Test-file type errors (unspecified location)
- PlanCta hydration mismatch (Story 7.2)
- Carried retro debt: Firestore security rules not yet deployed to production (Story 7.1), Firebase auth E2E not fully verified (Story 7.2)
- Vitest parallelism flake (action item from Epic 4 retro)

### Mobile
- `firebase/auth` `getReactNativePersistence` removed in v12

### Tooling
- `map_config.json` does not persist generation resolution
- Schema-version field absent on `map_config.json`

## REJECTED ALTERNATIVES (Preserved for Decision Audit Trail)
### Mobile
- Obytes / ExpoStarter / custom init templates: overhead, opinionated, paid → chose `npx create-expo-app@latest --template blank-typescript`
- Material Design styling: productivity-app look → chose NativeWind + React Native Reusables
- Original detection methodology (luminosity black-screen detector + OpenCV template matching against bundled `assets/images/map-templates/`): less accurate, less maintainable (must redeploy app to update templates), brittle to luminosity/resolution/encoding variation → SUPERSEDED by KDA/HSV + pHash post-pivot 2026-04-20
- Swipe gestures for Cinema Mode navigation: conflict with timeline scrubbing → chose explicit Next/Previous/Maps buttons
- Orientation lock: couch usage = unpredictable grip → chose no lock with adaptive layouts
- Onboarding tutorials: anti-pattern for power users → chose progressive disclosure via processing tips
- In-app social features: Discord owns social → chose share-out-only model
- Productivity UX language ("projects/workspaces/dashboards"): wrong mental model for video review → chose "sessions/episodes/clips"

### Web
- SaaS boilerplates (Divjoy/Makerkit/supastarter): paid $100-400+, excessive features (team billing/admin/email), opinionated non-standard patterns harder for AI agents → chose `create-next-app` minimal
- Custom payment forms: Stripe Checkout more trusted, handles edge cases → chose full-page redirect to Stripe-hosted
- Custom payment-history/upgrade/cancel UI (originally Stories 5.2/5.3/5.4): duplicates Stripe Customer Portal → delegated to portal per Sprint Change Proposal
- WebSocket / `onSnapshot` real-time listeners: webhook-driven async sufficient; DB is source of truth refreshed on dashboard load
- Light/corporate SaaS aesthetic: feels out of place for gaming audience, kills trust → chose dark theme
- Long scrolling landing page with sections / testimonials / app screenshots: app not finished, no real testimonials, gaming audience sees through generic imagery → chose minimal hero + single CTA
- Feature comparison tables: only 2 plans differ by billing cycle not features → single price card each
- Animated illustrations / Lottie: adds complexity, delays ship date → chose CSS-only static
- Hamburger menu: only 2-3 nav links, always visible even on mobile
- Tablet-specific breakpoint: mobile layout works fine on tablet → only `md:` (768px+) breakpoint
- Custom components abstractions for V1: 7 shadcn primitives cover all needs → extract later only if pattern repeats
- Global state library (Zustand/React Query): minimal client state → React Context for auth only
- Visual direction B (Bold Tactical/uppercase/grid): heavy-handed for billing context → chose A (Clean Minimal)
- Visual direction C (Warm/emoji): off-brand for gaming audience → chose A (Clean Minimal)

### Tooling
- PyQt: overkill 75-150MB GPL → chose tkinter (stdlib, zero-install)
- OpenCV highgui: no toolbar/text inputs → chose tkinter
- Dear PyGui: no built-in image viewer + GPU req → chose tkinter
- Own platform-specific GUI: → chose tkinter for portability
- Background-threaded detection in match-preview: → chose modal block (locked decision Step 1)
- `game_detector.py` as match-preview transition source: BSD chosen for cleaner start/end semantics + recovery windows
- Temp-dir hack or lean reimplement for BSD reuse in match-preview: chose proper refactor (split `run()` into `detect_transitions()` + `export_frames()`)
- Relative-position preservation across match switches in match-preview: meaningless for differing-length segments
- Per-match thumbnail previews in match-preview combobox: deferred
- Earlier two-state BSD design (using only `minimap` ROI to assume initial state): misclassified lobbies with black sky → chose three-state with `undetermined` initial
- Pixel-by-pixel map identification approach: too sensitive to background variation behind HUD transparency → chose hash-based
- Otsu threshold-hash binarization: harmful for perceptual hashing (dhash/phash rely on pixel gradients, Otsu destroys them); 34×15px crop too small for reliable bimodal split — flag kept opt-in but default `false`
- pHash auto-selection by max-min-pairwise-distance metric: cross-video inconsistent → chose `--force-method dhash` operational default
- Normalized 0.0-1.0 ROI coords: → chose fixed reference resolution 1920×1080 for consistency with rest of codebase

## DEFERRED / OUT OF SCOPE
### Mobile
- OCR scores/kills (V2; populates `score_orange`/`score_blue`; enables score-based Card View sorts)
- Stats per map (V2, depends on OCR)
- Advanced ROI composition (minimap + killfeed + life) — V2
- Vertical export (stories/TikTok format) — V2+
- Custom ROI templates — Desktop feature
- Review import mode (active player imports coach reviews with annotations) — V2
- Pick & Ban tool — V2+
- iOS — Phase 2 after Apple license
- Multi-view clip export (POV→minimap switch within single exported clip) — V2 via multi-segment FFmpeg encoding
- Export queue background encoding (Option 3 UX) — architecture supports
- Stream Discord for group review — Desktop / Phase 3
- Advanced Desktop analysis — Phase 3

### Web
- Discord OAuth (V2)
- Coupon Admin UI (V2)
- Custom Analytics Dashboard (V2)
- Account deletion self-serve button (V2)
- Team/Group Billing (V3)
- Full French localization (V3)
- Referral system (V3)

### Tooling
- Out of scope across specs: any GUI extensions beyond current Tk apps, batch/directory processing, automated test harness/CI, memory profiling, OCR/score reading
- Replacing BSD with `points_state_detector` (parallel only) — superseded by `game_detector.py`
- Team colors beyond orange/blue
- match-preview deferred items (Step 3-4)
- minimap-view-mode: timeline match splitting (match_preview's domain), `roi_zones` migration (kept disjoint), video file export, OCR on scores/timer/health, HSV zone defs (stay in `minimap_identification.configs[]`), keyboard shortcuts beyond Space + Esc, automatic ROI detection, undo/redo
- minimap-zone-selector: runtime map identifier (only config gen), automatic CV zone discovery, player-dot masking, multi-image averaging, multi-frame averaging across all frames per zone, sampling from non-displayed frames; `min_ratio` still hardcoded at 0.3
- image_inspector: non-rect ROI shapes, multi-image batch, direct piping to other tools, image editing
- TUI launcher: `--no-tui` headless flag mirroring underlying tool args for scripting
- Future enhancements: parallelize batch full-res extraction with `ThreadPoolExecutor`; add `--mode iframe|interval|auto` CLI flag for debugger; recovery/miss logic for `points_state_detector`

## OPPORTUNITIES (Carry Forward)
- Tooling reference impl ports cleanly to mobile (TypeScript/Kotlin); Python is the lab, mobile is production
- Discord-native virality: clips don't need watermarks because the format itself is novel
- Coupon→Retained ≥10% target leaves room for "dealer of comfort" growth via local-league winners
- Passive→Active player conversion path is monetizable (Lucas archetype)
- Reader App model architecturally protects from store policy changes (Netflix precedent)

## TECHNICAL DEBT INVENTORY (For Phase 6)
- Web: Stripe API version pin (Phase 6)
- Web: Firestore Security Rules deployment (Story 7.1)
- Web: Firebase Auth E2E + PlanCta hydration (Story 7.2)
- Web: Vitest parallelism flake
- Mobile: Firebase v12 `getReactNativePersistence` migration
- Mobile: Foreground Service Android decision
- Tooling: `map_config.json` resolution persistence
- Tooling: `bsd_roi_debugger.py` per-video output subfolder
- Tooling: project-sprint.md status sync to actual implementation state
- Tooling: minimap-view-mode implementation
- Tooling: match-preview Step 3-4 completion
- Tooling: warden_analyzer Tool 5 AC validation against real footage
- Tooling: 4 maps awaiting reference hashes (bastion, coliseum, lunar_outpost, the_rock)
