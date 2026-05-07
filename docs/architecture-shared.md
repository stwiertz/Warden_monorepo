# Architecture — Shared (`packages/` + `contracts/`)

> The "library" part of the monorepo. Holds cross-language schemas, generated TS types, shared TS configs, and a shared ESLint flat config. Day-1 of the consolidation; intentionally small.

## Why these exist

The three apps need a single source of truth for the data shapes they exchange:

- **`map_config.json`** — emitted by `apps/tooling`, consumed by `apps/mobile` (and indirectly validated by `apps/web` if it ever served the file).
- **Firestore `users/{uid}` document** — written by `apps/web` (Stripe webhook handlers), read by `apps/mobile` (subscription gate).

Without a shared contract, schemas drift. The strategy:

1. **JSON Schema is the cross-language source of truth.** Both languages can validate against JSON Schema directly (Python `jsonschema`, TS via Zod or ajv).
2. **Auto-generate Zod** for the TS side from the JSON Schema, so type drift is impossible.
3. **Keep shared TS/ESLint configs** as workspace packages so apps share strictness, target, and lint rules.

## Layout

```
contracts/                                   ← Language-agnostic JSON Schema (root-level, not under packages/)
├── map-config.schema.json
└── user-doc.schema.json

packages/
├── contracts/                               ← @warden/contracts — TS Zod surface
│   ├── package.json                         (ESM, exports './', './map-config', './user-doc')
│   ├── tsconfig.json
│   ├── scripts/generate-zod.mjs             reads ../../contracts/*.schema.json, emits src/generated/*.ts
│   └── src/
│       ├── index.ts                         re-exports from ./generated/*
│       └── generated/
│           ├── map-config.ts                AUTO-GENERATED (banner: "Do not edit by hand")
│           └── user-doc.ts                  AUTO-GENERATED
│
├── tsconfig/                                ← @warden/tsconfig
│   ├── package.json
│   ├── base.json                            strict + noUncheckedIndexedAccess + Bundler resolution
│   ├── next.json                            extends base, jsx=preserve, Next plugin
│   └── react-native.json                    extends base, jsx=react-native, allowJs, jest types
│
└── eslint-config/                           ← @warden/eslint-config
    ├── package.json
    └── index.js                             flat config baseline
```

## Packages

### `@warden/contracts`

Workspace name: `@warden/contracts`. ESM-only (`"type": "module"`). Runtime dep: `zod ^3.23.8`. Build dep: `json-schema-to-zod ^2.6.1`.

**Exports:**

```jsonc
"exports": {
  ".":            "./src/index.ts",
  "./map-config": "./src/generated/map-config.ts",
  "./user-doc":   "./src/generated/user-doc.ts"
}
```

`main`/`types` both point at `./src/index.ts` — there's **no compile step** for consumers. Both Metro (mobile) and the Next.js bundler (web) transpile TS sources directly. The "build" script is the codegen step, not a TS compile.

**Build (codegen):**

```sh
pnpm --filter @warden/contracts build
```

[scripts/generate-zod.mjs](../packages/contracts/scripts/generate-zod.mjs) does:

1. Read `contracts/{map-config,user-doc}.schema.json` from repo root.
2. `jsonSchemaToZod(schema, { name, module: 'esm' })` → TS source.
3. Prepend an "AUTO-GENERATED — Do not edit by hand" banner.
4. Write to `src/generated/{map-config,user-doc}.ts`.

**Versioning rule.** Edit `contracts/*.schema.json` only; never edit `src/generated/*` directly. Re-run the build after schema edits and commit both the schema and the regenerated TS together.

### `@warden/tsconfig`

Three configs, intended to be consumed as `extends`:

| File                                                        | Used by                         | Highlights                                                                                                                                                                                                                    |
| ----------------------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [base.json](../packages/tsconfig/base.json)                 | other tsconfigs                 | `target: ES2022`, `module: ESNext`, `moduleResolution: Bundler`, `strict`, `noUncheckedIndexedAccess`, `isolatedModules`, `resolveJsonModule`, `esModuleInterop`. Excludes `node_modules`, `dist`, `build`, `.next`, `.expo`. |
| [next.json](../packages/tsconfig/next.json)                 | apps/web                        | extends base, `jsx: preserve`, `noEmit`, `incremental`, Next plugin.                                                                                                                                                          |
| [react-native.json](../packages/tsconfig/react-native.json) | apps/mobile, packages/contracts | extends base, `jsx: react-native`, `allowJs`, `noEmit`, `types: ['jest', 'node']`.                                                                                                                                            |

The package's `package.json` only ships the three JSON files (`"files": ["base.json", "react-native.json", "next.json"]`); there's no entry point.

### `@warden/eslint-config`

A single ESM module exporting a flat-config array. Used by apps as a base layer; apps add framework-specific presets on top (Next plugin, RN plugin, etc.).

| Rule             | Value                                                                                    |
| ---------------- | ---------------------------------------------------------------------------------------- |
| `no-unused-vars` | `warn`, `argsIgnorePattern: '^_'`, `varsIgnorePattern: '^_'`                             |
| `no-console`     | `warn`, allow `warn`/`error`/`info`                                                      |
| `eqeqeq`         | `error`, `'always'`, `null: 'ignore'`                                                    |
| `prefer-const`   | `error`                                                                                  |
| Ignored          | `node_modules`, `dist`, `build`, `.next`, `.expo`, `.turbo`, `coverage`, `*.generated.*` |

Currently:

- **apps/web** has its own [eslint.config.mjs](../apps/web/eslint.config.mjs) (not yet importing from `@warden/eslint-config`).
- **apps/mobile** has no ESLint configured (`"lint": "echo …"`).
- **apps/tooling** is Python — uses ruff (not yet wired).

Wiring all three through `@warden/eslint-config` is a Phase 6/7 cleanup.

## Contracts (JSON Schema)

### [contracts/map-config.schema.json](../contracts/map-config.schema.json)

Schema id `https://warden.team/schemas/map-config.json`. Strict (`additionalProperties: false`).

```
MapConfig {
  reference_resolution: { width:int≥1, height:int≥1 }    Source video resolution the ROI was calibrated against.
  roi:                  { x:int≥0, y:int≥0, width:int≥1, height:int≥1 }   Map-name banner rectangle.
  canvas_size:          int≥1                            Square canvas size before hashing.
  hash_size:            int≥1                            hash_size=16 → 256-bit hash → 64 hex chars.
  hash_method:          'ahash'|'phash'|'dhash'|'whash'
  text_anchor_width?:   int≥0                            Optional sub-cropping width.
  maps:                 { [mapNameSlug]: hexHashString } Map name → fingerprint. Pattern: ^[0-9a-f]+$
}
```

Map name slugs are lowercase ASCII (e.g. `the_cliff`).

### [contracts/user-doc.schema.json](../contracts/user-doc.schema.json)

Schema id `https://warden.team/schemas/user-doc.json`. **Lax** (`additionalProperties: true`) on purpose — accommodates the legacy `isPaid` field while the unified architecture decides what to keep.

```
UserDoc {
  status:                  'active' | 'past_due' | 'canceled'        Mirrored from Stripe (web webhook).
  plan:                    'monthly' | 'yearly'
  current_period_end?:     number                                    Unix timestamp (seconds).
  stripe_customer_id?:     string                                    For customer-portal handoff.
  stripe_subscription_id?: string                                    For webhook reconciliation.
  isPaid?:                 boolean                                   Legacy denormalized flag (mobile reads this historically).
  // …additionalProperties allowed (created_at/updated_at server-stamped Timestamps, etc.)
}
```

The `description` on the schema explicitly flags the integration boundary: **apps/web writes via Stripe webhooks; apps/mobile reads to gate paid features.** Phase 6 architecture must decide whether `isPaid` survives or `status === 'active'` is derived at read time.

## How consumers wire in today

| Consumer     | Method                                                                                | Wiring status                                                                                                                                                                      |
| ------------ | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| apps/mobile  | `import {…} from '@warden/contracts/user-doc'` (or root barrel)                       | Workspace dep declared (`"@warden/contracts": "workspace:*"`). Metro resolves via `nodeModulesPaths` + the package's `exports` map (TS source — no build needed at consumer time). |
| apps/web     | n/a — defines its own Zod schemas in [src/lib/schemas/](../apps/web/src/lib/schemas/) | **Not yet wired** to `@warden/contracts`. Phase 6 candidate to unify.                                                                                                              |
| apps/tooling | reads `contracts/*.schema.json` directly via `jsonschema`                             | Goes through the JSON Schema, not the TS package — language-appropriate.                                                                                                           |

## Conventions for editing contracts

1. Edit `contracts/<schema>.schema.json`.
2. Run `pnpm --filter @warden/contracts build` to regenerate the TS Zod.
3. Update consumers (`apps/mobile`, eventually `apps/web`) if the breaking part is your responsibility.
4. Commit `contracts/`, `packages/contracts/src/generated/`, and consumer changes in the same commit so reviewers see them together.
5. Bump `@warden/contracts` SemVer if anyone outside the monorepo ever depends on it (currently nobody does — `private: true`).

## Tests

Currently zero. Both `@warden/contracts` test and lint scripts are no-op echoes. The contracts are validated end-to-end (apps/tooling validates emitted JSON; apps/mobile parses Firestore docs through Zod) — formal contract tests are Phase 7 polish.

## Why JSON Schema first, not Zod first

Zod is TypeScript-only. Python tooling needs to validate emitted JSON without a TS build step. Keeping JSON Schema as the master and auto-generating Zod (via `json-schema-to-zod`) gives both ecosystems a single source. The reverse — write Zod, generate JSON Schema via `zod-to-json-schema` — would force tooling to depend on a TS toolchain just to validate map-config emissions, which is unacceptable.
