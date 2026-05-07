# Deployment Guide — Warden Monorepo

> Honest assessment: deployment is **partly hand-rolled, partly missing**. There is no `.github/workflows/`, no IaC, no Dockerfiles. This document captures what _is_ deployable today and what's missing — Phase 7 (post-Phase-6) will fill the gaps.

## Targets

| Target                                   | Surface                                    | Status                                                                                                                                                                    |
| ---------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| App stores (Google Play / iOS App Store) | `apps/mobile`                              | **Manual.** Expo prebuild + native build. No EAS Build wired. No fastlane lane. Android package id `team.warden.mobile` per [app.json](../apps/mobile/app.json).          |
| Vercel (or equivalent Next.js host)      | `apps/web`                                 | **Default Next.js 16 deploy.** No `next.config.ts` customisation; no headers, redirects, or image domain config beyond defaults.                                          |
| Firebase                                 | `apps/web` writes Firestore docs and rules | Rules in [apps/web/firestore.rules](../apps/web/firestore.rules), deploy config in [apps/web/firebase.json](../apps/web/firebase.json). Deploy via Firebase CLI (manual). |
| (none for tooling)                       | `apps/tooling`                             | **Local desktop tool.** Not deployed anywhere; runs on a coach/operator machine. Distribution by checking out the repo.                                                   |
| Stripe                                   | webhook destination                        | Manual setup in Stripe Dashboard pointing at `${DOMAIN}/api/webhooks/stripe` with `STRIPE_WEBHOOK_SECRET`.                                                                |

## What gets built per part

### `apps/mobile`

```sh
pnpm --filter mobile exec expo export --platform android      # Hermes bundle (≈5.22 MB after Phase 4)
pnpm --filter mobile exec expo prebuild                       # generate native android/ + ios/
# Then drop into android/ for ./gradlew :app:bundleRelease, etc.
```

No EAS / fastlane / build-and-publish pipeline yet. Phase 7 candidate.

Required env vars at build/runtime: see [apps/mobile/.env.example](../apps/mobile/.env.example). All are `EXPO_PUBLIC_*` (compiled into the bundle). Crucially:

- `EXPO_PUBLIC_AUTH_BYPASS` — **must be `false` (or unset) for any release build.** When `true`, App.tsx injects a fake authed user and skips Firebase auth + subscription checks entirely. There's an explicit warning in source.

Native module version pins to be aware of:

- `react-native-mmkv@^3` — do **not** upgrade to v4 without first upgrading React Native to 0.83+ (Nitro Modules requirement). Silent boot crash otherwise.
- `@wokcito/ffmpeg-kit-react-native@^6.1.2` — FFmpeg-kit 6.1.4 native AAR, 16-kb page-aligned for Android 15+.

### `apps/web`

```sh
pnpm --filter web build       # next build → .next/
pnpm --filter web start       # next start (production)
```

[next.config.ts](../apps/web/next.config.ts) is empty (defaults). Vercel deploys via auto-detect.

Required env vars: see [apps/web/.env.example](../apps/web/.env.example). At minimum:

- **Firebase Admin (server):** `FIREBASE_SERVICE_ACCOUNT_KEY` — a JSON-encoded service account.
- **Firebase Client (browser):** `NEXT_PUBLIC_FIREBASE_*` (apiKey, authDomain, projectId, storageBucket, messagingSenderId, appId, measurementId).
- **Stripe (server):** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`.
- **App URL:** `NEXT_PUBLIC_APP_URL` — used to build Stripe `success_url` / `cancel_url` / `return_url`. **Set to the deployed domain in production**, otherwise these fall back to the request origin which is fragile behind reverse proxies.

Firestore rules deploy:

```sh
firebase deploy --only firestore:rules --project <project-id>
```

(from `apps/web/`). Currently the rules file [firestore.rules](../apps/web/firestore.rules) only covers `users/{uid}` (owner-read, no client write) and a wildcard deny. **`detection_config` and `stripe_events` are not covered explicitly** — they fall into the wildcard deny, which means mobile cannot read `detection_config/latest` under those rules. Either rules are out of date, or mobile is hitting a different rule set. Phase 6 must reconcile.

### `apps/tooling`

Not deployed. Run locally:

```sh
uv run python apps/tooling/wardentooling.py        # TUI launcher
# or invoke individual tools directly:
uv run python apps/tooling/tools/map_config_generator.py --images <maps_dir>
```

Output (e.g. `map_config.json`) is the deliverable, not the binary.

### `packages/contracts`

Not deployed. Build is the codegen step:

```sh
pnpm --filter @warden/contracts build              # regenerates src/generated/{map-config,user-doc}.ts
```

Consumed only via workspace deps — no npm publish.

## Stripe webhook setup (one-time per environment)

1. In Stripe Dashboard → Developers → Webhooks → Add endpoint.
2. URL: `https://<your-domain>/api/webhooks/stripe`.
3. Events to subscribe to (matches handlers in [lib/stripe/webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts)):
   - `invoice.paid`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy the signing secret → set `STRIPE_WEBHOOK_SECRET` in the deployment environment.
5. API version: the app pins **`2026-03-25.dahlia`** in [stripe/server.ts](../apps/web/src/lib/stripe/server.ts). The Stripe Dashboard should be configured to send events at this version (or the latest, as long as the schemas in [webhook-events.ts](../apps/web/src/lib/schemas/webhook-events.ts) still parse).

Replay: failed routings end up in Firestore `stripe_events/{event.id}` with `routingError: true`. Replay by re-firing the event from Stripe Dashboard → Webhooks → Events → Resend.

## Firebase setup (one-time)

| Item                     | Action                                                                                                                                                                                                                                                                                                                                             |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Firebase project         | Create. **Both web and mobile point at the same project today** (apparent — confirm in Phase 6).                                                                                                                                                                                                                                                   |
| Authentication           | Enable Email/Password and Google sign-in methods.                                                                                                                                                                                                                                                                                                  |
| Firestore                | Create `users` collection (docs auto-created by webhook). Create `stripe_events` (auto-created). Create `detection_config/latest` document with the current `DetectionConfig` payload.                                                                                                                                                             |
| Web client config        | Copy from Firebase Console → Project Settings → Web app → SDK config into `NEXT_PUBLIC_FIREBASE_*` env vars.                                                                                                                                                                                                                                       |
| Service account          | Download JSON from Firebase Console → Project Settings → Service Accounts → Generate new private key. Stringify into `FIREBASE_SERVICE_ACCOUNT_KEY` env var. **Never commit this.**                                                                                                                                                                |
| Mobile client config     | Same web SDK config, copied into `EXPO_PUBLIC_FIREBASE_*` env vars.                                                                                                                                                                                                                                                                                |
| Google sign-in (Android) | Place `google-services.json` in `apps/mobile/android/app/` (after `expo prebuild`). Register SHA-1 (and SHA-256 for release) fingerprint in Firebase Console. Use the **Web client ID** (not Android) in `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` — the native `@react-native-google-signin` SDK requires this to mint an idToken Firebase Auth accepts. |

## CI/CD — what's missing

There is **no `.github/workflows/`**. Add in Phase 7. Suggested workflows (informed by what the test/build commands already do):

| Workflow                      | Trigger                                             | Steps                                                                                               |
| ----------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `ci.yml`                      | PR + push                                           | `pnpm install` → `uv sync` → `pnpm typecheck` → `pnpm test` → `pnpm format:check`                   |
| `deploy-web.yml`              | push to `main`                                      | Build + Vercel deploy (or self-hosted equivalent)                                                   |
| `deploy-firestore-rules.yml`  | push to `main` affecting `apps/web/firestore.rules` | `firebase deploy --only firestore:rules`                                                            |
| `mobile-build.yml`            | manual                                              | `expo prebuild` + `expo export` (verify Phase 4 acceptance hasn't regressed)                        |
| `contracts-codegen-check.yml` | PR touching `contracts/**`                          | Run `pnpm contracts:build` and fail if `src/generated/*` is dirty (catches forgotten regenerations) |

## Branch protection (Phase 7 candidate)

`main` should require:

- Passing `ci.yml`.
- Conventional Commit linear history (already enforced via `commitlint` locally).
- At least one review.
- No force-pushes.

Currently advisory — relies on the developer running things locally.

## Secrets inventory

| Secret                                         | Where                                                                                                           | Used in                                                                            |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `FIREBASE_SERVICE_ACCOUNT_KEY`                 | host env                                                                                                        | [admin.ts](../apps/web/src/lib/firebase/admin.ts)                                  |
| `STRIPE_SECRET_KEY`                            | host env                                                                                                        | [stripe/server.ts](../apps/web/src/lib/stripe/server.ts)                           |
| `STRIPE_WEBHOOK_SECRET`                        | host env                                                                                                        | [api/webhooks/stripe/route.ts](../apps/web/src/app/api/webhooks/stripe/route.ts)   |
| `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`  | host env                                                                                                        | [pricing/plans.ts](../apps/web/src/lib/pricing/plans.ts) (via `stripePriceEnvKey`) |
| Service-account JSON                           | repo `.gitignore` should keep these out — verify `*-service-account*.json` and `firebase-debug.log` are ignored | n/a                                                                                |
| `apps/mobile/android/app/google-services.json` | not committed                                                                                                   | runtime                                                                            |

[.gitignore](../.gitignore) governs the in-repo set; verify before any deploy that no `.env.local`, service-account JSON, or `*.keystore` is staged.

## What "deployable today" looks like

| Surface                     | Deployable?                  | Notes                                                                      |
| --------------------------- | ---------------------------- | -------------------------------------------------------------------------- |
| Web on Vercel               | ✅ with manual env wiring    | Not yet wired through CI; deploy runs on push if Vercel project is linked. |
| Web Firestore rules         | ✅ via Firebase CLI manually | Add a Phase-7 workflow to make this automatic.                             |
| Mobile to Play / TestFlight | ⚠ manual                     | Expo prebuild + native toolchain. EAS not configured. Phase 7.             |
| Tooling                     | n/a                          | Run locally.                                                               |
| Shared packages             | n/a                          | Workspace-only.                                                            |

## Phase 7 deployment work

1. Add `.github/workflows/ci.yml`, `.github/workflows/deploy-web.yml`, `.github/workflows/deploy-firestore-rules.yml`.
2. Wire mobile to EAS Build (or document the local-build path more explicitly).
3. Reconcile `firestore.rules` with all Firestore collections actually written (`users`, `stripe_events`, `detection_config`).
4. Add a `contracts-codegen-check.yml` that fails PRs where `pnpm contracts:build` produces dirty diffs.
5. Add branch protection on `main`.
6. Document staging vs production env separation for Stripe (test mode keys + a separate webhook).
