# Source Tree — Warden Monorepo

Annotated layout of the merged repo. Excludes `node_modules/`, `.venv/`, `.turbo/`, `.git/`, `_bmad/` (BMad install), `_bmad-output/` (planning artifacts; see legacy distillate).

```
Warden_monorepo/
├── apps/                           Workspace apps (pnpm workspace + uv workspace)
│   ├── mobile/                     Part: mobile (Expo / React Native, package "mobile")
│   │   ├── App.tsx                 Entry — fonts, AuthBypass branch, listeners
│   │   ├── index.ts                Expo registration
│   │   ├── app.json                Expo config (Android pkg team.warden.mobile, newArchEnabled)
│   │   ├── metro.config.js         Monorepo Metro: watchFolders=root, disableHierarchicalLookup
│   │   ├── babel.config.js         Babel preset
│   │   ├── global.css              NativeWind global stylesheet
│   │   ├── tailwind.config.ts      NativeWind / Tailwind config
│   │   ├── tsconfig.json           Extends @warden/tsconfig/react-native.json
│   │   ├── package.json            "mobile" — Expo SDK 54, RN 0.81, React 19.1, Firebase 12, NativeWind 4
│   │   ├── plugins/                Expo config plugins
│   │   ├── assets/                 Icons, splashes
│   │   └── src/
│   │       ├── app/                App shell
│   │       │   ├── RootNavigator.tsx        Auth-gated stack: Login | (Home + Processing)
│   │       │   └── screens/HomeScreen.tsx
│   │       ├── features/           Vertical slices (one folder per epic)
│   │       │   ├── auth/                    Firebase Auth + subscription gate (Zustand+MMKV cache)
│   │       │   ├── audio-commentary/
│   │       │   ├── clip-export/             Clip-mode + share screens
│   │       │   ├── session/                 Session list + repository (SQLite) + Card View
│   │       │   ├── video-import/            DocumentPicker → MP4 validation → SQLite session
│   │       │   ├── video-playback/          Cinema mode
│   │       │   └── video-processing/        Detection pipeline (FFmpeg → game/black-screen → maps)
│   │       │       ├── processingPipeline.ts  Orchestrator with 4-stage MMKV checkpointing
│   │       │       ├── detectionConfig*.ts     Stale-while-revalidate Firestore-backed config
│   │       │       ├── blackScreenDetector.ts  Long-GOP fallback (2-pass team-bar saturation)
│   │       │       ├── gameDetector.ts         Short-GOP KDA/HSV detector
│   │       │       ├── mapIdentifier.ts        pHash matcher against map_config
│   │       │       ├── segmentation.ts         START/END pair → MapSegment timeline
│   │       │       └── segmentRepository.ts    SQLite map_segments writer
│   │       ├── shared/             Cross-feature primitives
│   │       │   ├── components/{Button,Card,LoadingSpinner,Toast}.tsx + hud/  HUD design system (~12 atoms)
│   │       │   ├── hooks/
│   │       │   ├── services/{database,ffmpeg,opencv,storage}.ts  Native bridges
│   │       │   ├── types/index.ts            Domain types: Session, MapSegment, ClipExport, AudioComment
│   │       │   └── utils/
│   │       └── __tests__/          App-level tests (per-feature tests live with each feature)
│   │
│   ├── web/                        Part: web (Next.js, package "web")
│   │   ├── next.config.ts          (Empty config — defaults)
│   │   ├── firebase.json           Firestore rules deploy config
│   │   ├── firestore.rules         users/{uid}: read=owner, write=false (server-only via admin)
│   │   ├── eslint.config.mjs       Web ESLint flat config
│   │   ├── postcss.config.mjs      Tailwind 4 / @tailwindcss/postcss
│   │   ├── components.json         shadcn/ui registry config
│   │   ├── vitest.config.ts        Vitest + jsdom + @vitejs/plugin-react
│   │   ├── vitest.setup.ts
│   │   ├── tsconfig.json           Extends @warden/tsconfig/next.json (uses `@/*` alias)
│   │   ├── package.json            "web" — Next.js 16.2.2, React 19.2, Stripe 22, Zod 4, Firebase admin 13
│   │   ├── AGENTS.md               ⚠ "This is NOT the Next.js you know" — heed deprecation notices
│   │   ├── CLAUDE.md               @ AGENTS.md
│   │   ├── public/                 Static assets
│   │   └── src/
│   │       ├── app/                Next.js App Router
│   │       │   ├── layout.tsx              Root layout (AuthProvider, font loading)
│   │       │   ├── page.tsx                Marketing landing
│   │       │   ├── auth/sign-in/page.tsx   Sign-in (email/password + Google)
│   │       │   ├── pricing/page.tsx        Plan picker + checkout entry
│   │       │   ├── dashboard/              Authed: SubscriptionCard + portal CTA
│   │       │   └── api/                    Route handlers (see api-contracts-web.md)
│   │       │       ├── auth/session/route.ts            POST/DELETE — session cookie
│   │       │       ├── checkout/coupon/route.ts         POST — preview coupon
│   │       │       ├── checkout/session/route.ts        POST — create Stripe Checkout
│   │       │       ├── subscription/route.ts            GET  — read users/{uid}
│   │       │       ├── subscription/portal/route.ts     POST — Stripe billing portal
│   │       │       └── webhooks/stripe/route.ts         POST — Stripe webhook ingress
│   │       ├── components/         UI inventory
│   │       │   ├── auth/           Sign-in/up forms, Google button, sign-out
│   │       │   ├── checkout/       Coupon input, plan card / CTA, CheckoutContext
│   │       │   ├── dashboard/      SubscriptionCard
│   │       │   ├── layout/         Header, HeaderAuthActions, Footer, CookieBanner
│   │       │   └── ui/             shadcn/ui primitives (button, card, input, alert, dialog, badge, skeleton)
│   │       ├── contexts/AuthContext.tsx     Firebase onAuthStateChanged → React context
│   │       ├── hooks/{useAuth,useSubscription}.ts
│   │       ├── lib/
│   │       │   ├── firebase/{admin,client,auth,session,analytics,errors}.ts
│   │       │   ├── stripe/{server,webhooks,coupons}.ts
│   │       │   ├── pricing/{plans,discount}.ts            EUR plans, savings calc
│   │       │   ├── schemas/{auth,subscription,webhook-events}.ts  Zod validators
│   │       │   ├── env.ts
│   │       │   └── utils.ts                               clsx + tailwind-merge cn()
│   │       └── fonts/
│   │
│   └── tooling/                    Part: tooling (Python CLI, package "tooling")
│       ├── wardentooling.py        TUI launcher (questionary) — main entry
│       ├── pyproject.toml          warden-tooling — opencv, numpy, imagehash, pyyaml, questionary
│       ├── package.json            Thin Turborepo wrapper — `pnpm --filter tooling test` → uv run pytest
│       ├── requirements.txt        Pinned deps (legacy pip parallel to uv)
│       ├── description.md          Original tooling brief (4 tools)
│       ├── README.md               How to invoke each tool
│       ├── config/config.yaml      All tunables — ROI zones, thresholds, HSV bands, 14+ map fingerprints
│       ├── tools/                  CLI entry points
│       │   ├── black_screen_detector.py        Tool 1 — round transitions (BSD)
│       │   ├── frame_labeler.py                Tool 2 — manual labeling helper
│       │   ├── map_config_generator.py         Tool 3 — emits map_config.json
│       │   ├── hash_validator.py               Tool 4 — accuracy reporter
│       │   ├── warden_analyzer.py              Tool 5 — full-pipeline analyzer
│       │   ├── game_detector.py                KDA / hybrid detector
│       │   ├── points_state_detector.py        Dev: per-frame point colour state
│       │   ├── bsd_roi_debugger.py             Dev: ROI overlay debugger
│       │   ├── hash_comparator.py              Hamming-distance helpers
│       │   ├── common/video_player.py          Shared OpenCV video preview
│       │   ├── image_inspector/                Dev GUI (modes, canvas, logger)
│       │   └── minimap_zone_selector/          Dev GUI for HSV zone calibration
│       ├── utils/
│       │   ├── config.py                       YAML loader
│       │   ├── format.py                       Print helpers
│       │   ├── image.py                        downscale / extract_roi / find_text_anchor / scale_roi
│       │   └── video.py                        ffmpeg/ffprobe subprocess wrappers
│       ├── tests/
│       │   └── fixtures/                       (Test data)
│       └── docs/                   Pre-existing per-app docs (kept for now; superseded by docs/architecture-tooling.md)
│
├── packages/                       Shared TS packages
│   ├── contracts/                  @warden/contracts
│   │   ├── package.json            ESM, exports ./, ./map-config, ./user-doc — build = node scripts/generate-zod.mjs
│   │   ├── tsconfig.json
│   │   ├── scripts/generate-zod.mjs    Reads contracts/*.schema.json → emits src/generated/*.ts
│   │   └── src/
│   │       ├── index.ts            Re-exports both schemas
│   │       └── generated/
│   │           ├── map-config.ts   AUTO-GENERATED zod schema (do not edit)
│   │           └── user-doc.ts     AUTO-GENERATED zod schema (do not edit)
│   ├── tsconfig/                   @warden/tsconfig
│   │   ├── base.json               strict + noUncheckedIndexedAccess + Bundler resolution
│   │   ├── next.json               + jsx=preserve + Next plugin
│   │   └── react-native.json       + jsx=react-native + allowJs + jest types
│   └── eslint-config/              @warden/eslint-config
│       └── index.js                Flat config baseline (no-unused-vars, eqeqeq, no-console allow warn/error/info)
│
├── contracts/                      Language-agnostic JSON Schemas (cross-language source of truth)
│   ├── map-config.schema.json      MapConfig — emitted by tooling, consumed by mobile
│   └── user-doc.schema.json        UserDoc — written by web, read by mobile (see open conflict)
│
├── _bmad/                          BMad install (v6.6.0) — ignore for app code
├── _bmad-output/                   Planning surface
│   ├── legacy/                     Pre-merge planning preserved per app
│   │   ├── distillate/             Phase 5a output — 9 lossless distillate files
│   │   ├── _intermediates/         Audit-trail fan-outs (g1..g5)
│   │   ├── mobile/                 33 stories + planning artifacts (French PRD)
│   │   ├── web/                    5 epics + planning artifacts (English PRD)
│   │   └── tooling/                32 implementation tech-specs
│   └── (Phase 6 unified artifacts will land at this level)
│
├── docs/                           THIS folder — Phase 5b output (as-built code docs)
├── .husky/                         Pre-commit + commit-msg hooks (commitlint)
├── commitlint.config.ts            Conventional commits enforcement
├── .prettierrc                     endOfLine: auto (Windows-friendly)
├── .prettierignore                 Excludes apps/mobile and apps/tooling
├── .npmrc                          node-linker=hoisted (REQUIRED for Expo/Metro)
├── pnpm-workspace.yaml             apps/* + packages/*
├── pyproject.toml                  Root Python — only [tool.uv.workspace] members=apps/tooling
├── turbo.json                      Task graph: build/typecheck/test/lint/dev (dev not cached, persistent)
├── package.json                    Root TS — turbo, prettier, husky, commitlint
├── README.md                       Surfaces overview + get-started
└── (no .github/ yet — flagged in deployment-guide.md)
```

## Critical entry points

| Part           | Entry                                                                                             | Notes                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| mobile         | [App.tsx](../apps/mobile/App.tsx) → [RootNavigator.tsx](../apps/mobile/src/app/RootNavigator.tsx) | `EXPO_PUBLIC_AUTH_BYPASS=true` short-circuits auth + subscription        |
| web            | [src/app/layout.tsx](../apps/web/src/app/layout.tsx)                                              | App Router root; AuthProvider wraps tree                                 |
| web (server)   | [src/app/api/\*\*/route.ts](../apps/web/src/app/api/)                                             | All `runtime = 'nodejs'`                                                 |
| tooling        | [wardentooling.py](../apps/tooling/wardentooling.py)                                              | TUI; tools also runnable directly via `python tools/<x>.py …`            |
| shared codegen | [packages/contracts/scripts/generate-zod.mjs](../packages/contracts/scripts/generate-zod.mjs)     | `pnpm --filter @warden/contracts build` regenerates Zod from JSON Schema |

## Folders that are intentionally absent

- **`.github/`** — no CI/CD wired yet. Phase 7 work (see [deployment-guide.md](./deployment-guide.md)).
- **`apps/mobile/android/` and `apps/mobile/ios/`** — Expo prebuild not committed; native shells generated on demand.
- **`apps/web/.next/`** — build output, gitignored.
- **Per-app `_bmad/`** — old per-repo BMad installs were dropped in favour of the single root install.
