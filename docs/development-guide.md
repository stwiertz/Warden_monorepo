# Development Guide — Warden Monorepo

How to set up and work in the merged repo. One unified guide; per-part nuances called out inline.

## Prerequisites

| Tool               | Version               | Why                                                                                                                                                  |
| ------------------ | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Node.js            | ≥20                   | TS apps + Turbo + pnpm. Pinned in [.nvmrc](../.nvmrc) and [package.json](../package.json) `engines.node`.                                            |
| pnpm               | 9.12.0                | Package manager. Pinned in [package.json](../package.json) `packageManager`.                                                                         |
| Python             | ≥3.11                 | `apps/tooling`. Pinned in [.python-version](../.python-version) and [apps/tooling/pyproject.toml](../apps/tooling/pyproject.toml) `requires-python`. |
| uv                 | latest                | Python deps + virtualenv (workspace-aware).                                                                                                          |
| FFmpeg             | system                | Required by `apps/tooling` (subprocess + ffprobe). Mobile bundles its own via FFmpeg-kit at build time.                                              |
| Java + Android SDK | (Android dev)         | For `expo run:android` builds of the mobile app. Expo handles most of this through the dev client.                                                   |
| Xcode              | (iOS dev, macOS only) | For `expo run:ios`.                                                                                                                                  |

## First-time setup (clone → working tree)

```sh
# From a fresh clone of the repo
pnpm install        # installs TS deps for all workspaces — apps/* + packages/*
uv sync             # creates .venv at root and installs Python deps for tooling
```

`pnpm install` triggers husky's prepare script (sets up `.husky/` git hooks) and the `node-linker=hoisted` mode required by Expo/Metro (see [.npmrc](../.npmrc)).

`uv sync` reads root [pyproject.toml](../pyproject.toml) (which declares `[tool.uv.workspace] members = ["apps/tooling"]`) and installs everything into a single `.venv` shared across the repo.

### Per-app env files

Copy and fill:

```sh
cp apps/web/.env.example apps/web/.env.local
cp apps/mobile/.env.example apps/mobile/.env.local
```

See [.env.example for web](../apps/web/.env.example) (Firebase Admin + Stripe) and [.env.example for mobile](../apps/mobile/.env.example) (Firebase + Google Web client ID + optional `EXPO_PUBLIC_AUTH_BYPASS`).

`apps/tooling` has no env file. All config is in [config/config.yaml](../apps/tooling/config/config.yaml).

## Daily commands

All scripts run from the repo root.

| Goal                      | Command                                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Type-check everything     | `pnpm typecheck` (Turbo task — caches per-workspace)                                                                 |
| Run all tests             | `pnpm test` (runs Vitest for web, jest for mobile, pytest for tooling — all via Turbo)                               |
| Run one workspace's tests | `pnpm --filter <name> test` where `<name>` is `mobile` / `web` / `tooling` / `@warden/contracts`                     |
| Type-check one workspace  | `pnpm --filter <name> typecheck`                                                                                     |
| Lint everything           | `pnpm lint` (web only effectively — mobile has placeholder echo, tooling has no Python lint)                         |
| Format the whole repo     | `pnpm format` (Prettier — excludes `apps/mobile/**` and `apps/tooling/**` per [.prettierignore](../.prettierignore)) |
| Verify formatting (CI)    | `pnpm format:check`                                                                                                  |
| Build all (TS)            | `pnpm build`                                                                                                         |
| Run dev (parallel)        | `pnpm dev` — starts `next dev`, `expo start`, etc. in parallel; cache-disabled, persistent                           |

### Per-part conveniences

```sh
# Web
pnpm --filter web dev               # next dev on http://localhost:3000
pnpm --filter web build             # production build
pnpm --filter web test              # vitest run

# Mobile
pnpm --filter mobile start          # expo start (Metro)
pnpm --filter mobile android        # expo run:android (needs dev client built)
pnpm --filter mobile ios            # expo run:ios (macOS only)
pnpm --filter mobile test           # jest

# Tooling — Python
pnpm tooling:test                   # short alias for the next line
pnpm --filter tooling test          # uv run pytest
uv run python apps/tooling/wardentooling.py    # interactive TUI launcher

# Shared contracts
pnpm --filter @warden/contracts build           # regenerate Zod from JSON Schema
pnpm contracts:build                            # short alias
```

### When to regenerate contracts

After **any edit** to [contracts/\*.schema.json](../contracts/), run:

```sh
pnpm contracts:build
```

This re-emits [packages/contracts/src/generated/{map-config,user-doc}.ts](../packages/contracts/src/generated/). Commit the schema change and the regenerated TS together so reviewers see the contract bump and the consumer-visible diff in one PR.

## Build verification

The big-deal verification from Phase 4 was that mobile bundles end-to-end through Metro from the monorepo:

```sh
pnpm --filter mobile exec expo export --platform android
```

Expected outcome: a 5.22 MB Hermes bundle. Don't break this without re-validating Expo monorepo wiring (especially [.npmrc](../.npmrc) `node-linker=hoisted`, [apps/mobile/metro.config.js](../apps/mobile/metro.config.js), and the `.js`-extension drop in `packages/contracts/src/index.ts`).

## Project structure conventions

- **One feature → one folder** under `apps/mobile/src/features/<slice>/` or `apps/web/src/components/<feature>/`. Tests live next to subjects.
- **Shared primitives → `shared/` (mobile) or `components/ui/` (web)**. Don't import features into shared.
- **No mobile/web → tooling code path.** Tooling is a CLI lab, not a runtime dependency. The only artefact crossing is `map_config.json` (and its schema).
- **Workspace deps via `workspace:*`**. Don't pin `@warden/contracts` to a version; use `workspace:*`.
- **Server-only modules in web start with `import 'server-only'`** so accidental client imports fail the build.

## Testing approach per part

| Part    | Framework                               | Where                        | Run                         |
| ------- | --------------------------------------- | ---------------------------- | --------------------------- |
| mobile  | jest + jest-expo                        | `src/**/__tests__/*.test.ts` | `pnpm --filter mobile test` |
| web     | vitest + jsdom + @testing-library/react | `src/**/*.test.ts(x)`        | `pnpm --filter web test`    |
| tooling | pytest                                  | `tests/` (uv venv)           | `pnpm tooling:test`         |
| shared  | n/a                                     | (no tests yet)               | —                           |

Mobile tests inject synthetic `FrameLoader`s into the processing pipeline because the OpenCV JSI bridge is not wired yet. Don't rely on a real video file in the test suite.

Web tests use `vi.spyOn(webhooksModule, 'handleX')` to intercept Stripe handler routing — see the self-namespace import note in [webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts). Don't refactor `routeEvent` to call handlers directly without rewriting the spies.

Tooling tests use fixtures under [apps/tooling/tests/fixtures/](../apps/tooling/tests/fixtures/).

## Commits

Conventional Commits enforced by husky + commitlint. The pre-commit hook also runs Prettier on staged files.

```
<type>(<optional scope>): <subject>

[optional body]

[optional footer]
```

Examples (from `git log`):

```
feat(mobile): wire apps/mobile for the monorepo (phase 4 verified)
chore: merge Warden mobile under apps/mobile (phase 4)
feat(web): import WardenWeb under apps/web (phase 2)
```

Hooks:

- `.husky/pre-commit` — runs Prettier on staged files (excluded folders skipped).
- `.husky/commit-msg` — runs `commitlint`.

## Editor / agent guardrails

- **`apps/web/AGENTS.md`** ([here](../apps/web/AGENTS.md)) is a hard "this is NOT the Next.js you know" warning. Next.js 16 has breaking changes from older training data — read `apps/web/node_modules/next/dist/docs/` before assuming an older convention applies.
- `.prettierrc` sets `endOfLine: auto` for Windows-friendly checkouts.
- `.prettierignore` excludes `apps/mobile/**` (legacy formatting; not yet modernized) and `apps/tooling/**` (Python — not Prettier's concern).

## Adding a new dependency

| Target                                                                          | Command                                                                                          |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Add a TS dep to one workspace                                                   | `pnpm --filter <name> add <pkg>`                                                                 |
| Add a TS dep to the monorepo root (rare — only for tooling like Prettier/Turbo) | `pnpm add -w -D <pkg>`                                                                           |
| Add a Python dep to tooling                                                     | `uv add --package warden-tooling <pkg>` (run from `apps/tooling/` or from root with `--package`) |
| Bump the lockfile                                                               | `pnpm install` (and `uv sync` for Python)                                                        |

## What's missing right now

- **No `.github/workflows/`.** CI/CD is Phase 7. Branch protection on `main` is currently advisory only.
- **No mobile ESLint config.** [package.json](../apps/mobile/package.json) `lint` script is an echo.
- **No Python lint or type-check.** [tooling/package.json](../apps/tooling/package.json) `lint` and `typecheck` scripts are echoes. Wire `ruff` + `mypy` in Phase 7.
- **No e2e test runner.** Sprint 7 candidate.
- **Husky's `pre-commit` runs Prettier but not the type-checker or tests.** Keep PRs small or run `pnpm typecheck && pnpm test` locally before pushing.
