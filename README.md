# Warden

Esports coaching platform for the EVA video game. One product, three deployment surfaces, one BMad workflow.

## Surfaces

- **`apps/mobile`** — Expo / React Native app. Coaches review match footage on-device: import → segment → annotate → export clips. Firebase Auth + Firestore, FFmpeg, on-device pHash detection. (Imported from the legacy `Warden` repo.)
- **`apps/web`** — Next.js marketing site + subscription portal. Stripe checkout, customer portal, webhooks. Writes the same Firestore `users/{uid}` document the mobile app reads. (Imported from the legacy `WardenWeb` repo.)
- **`apps/tooling`** — Python CLI lab. Validates detection algorithms on desktop and emits `map_config.json` (per-map discriminating pixels) consumed by the mobile app. (Imported from the legacy `Warden-tooling` repo.)

## Shared

- **`contracts/`** — language-agnostic schemas (JSON Schema). Read by Python and TS. Source of truth for `map_config.json` and the Firestore `users/{uid}` document.
- **`packages/contracts`** — Zod types generated from `contracts/*.schema.json`.
- **`packages/tsconfig`** — shared base / react-native / next tsconfigs.
- **`packages/eslint-config`** — shared flat ESLint config.

## Planning

- **`_bmad/`** — single BMad install (v6.6.0).
- **`_bmad-output/`** — unified planning surface. Active artifacts (PRD, architecture, epics, stories, sprint) at the root; pre-merge planning from each legacy repo preserved under `_bmad-output/legacy/{mobile,web,tooling}/` for traceability.

## Tooling

- **pnpm workspaces** for the TS apps + packages.
- **Turborepo** for cached `build`/`typecheck`/`test`/`lint` task graphs.
- **uv** for Python (`apps/tooling`) — interop via a thin `package.json` wrapper so Turborepo can include it.

## Get started

```sh
pnpm install         # installs TS deps for all workspaces
uv sync              # installs Python deps for tooling
pnpm typecheck       # check all TS workspaces
pnpm tooling:test    # run Python tests in apps/tooling
```

## Status

This monorepo is being assembled now from three pre-existing repos. See [the consolidation plan](C:\Users\stwie\.claude\plans\the-goal-of-this-polymorphic-popcorn.md) for the phased approach.
