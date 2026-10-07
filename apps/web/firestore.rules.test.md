# Firestore rules: emulator verification

Story 1.14 (architecture Decision #7). [`firestore.rules`](./firestore.rules) is verified against the
local Firestore emulator by [`firestore.rules.test.ts`](./firestore.rules.test.ts).

## Run

```sh
pnpm --filter web test:rules
```

The script runs:

```sh
npx -y firebase-tools@15.32.1 emulators:exec --only firestore --project demo-warden-rules \
  "vitest run --config vitest.rules.config.ts"
```

`emulators:exec` starts the Firestore emulator (port 8080, from [`firebase.json`](./firebase.json)),
sets `FIRESTORE_EMULATOR_HOST`, runs the suite and shuts the emulator down. The `demo-` project id
keeps everything offline: no real Firebase project and no credentials are touched.

The suite is **not** part of `pnpm --filter web test`. `vitest.config.ts` excludes it, because it needs
the emulator.

## Prerequisites

- Java 21+ on `PATH` (the Firestore emulator is a JAR).
- Node 20+.
- Network on the first run: npx downloads `firebase-tools@15.32.1`, and the CLI downloads the
  Firestore emulator JAR (about 60 MB, cached under `~/.cache/firebase/emulators`). Later runs work
  offline.
- Port 8080 free.

## Matrix

Seeded with security rules disabled before each test: `users/u1`, `users/u2`, `users/u1/anything/x`,
`detection_config/latest`, `detection_config/latest/history/r0`, `detection_config/other`, `stripe_events/evt_1`, `random/doc`.

| Path                                                                      | anon | signed-in `u1` | Why                                        |
| ------------------------------------------------------------------------- | ---- | -------------- | ------------------------------------------ |
| `users/u1` get                                                            | deny | **allow**      | owner read only                            |
| `users/u2` get                                                            | deny | deny           | not someone else's                         |
| `users` list (unfiltered)                                                 | deny | deny           | rules are not filters                      |
| `users/u1` create / set / update / delete                                 | deny | deny           | [INVARIANT 2]: web (admin) is the writer   |
| `users/u1/anything/x` get                                                 | deny | deny           | sub-collections fall to the catch-all      |
| `users/u3` create by `u3` itself                                          | n/a  | deny           | no client-side profile bootstrap           |
| `detection_config/latest` get                                             | deny | **allow**      | the mobile post-auth overlay (Story 1.13)  |
| `detection_config/other` get                                              | deny | **allow**      | `{docId}` match, per the architecture spec |
| `detection_config` list                                                   | deny | **allow**      | `read` = get + list                        |
| `detection_config/latest/history/r0` get                                  | deny | deny           | sub-collection falls to the catch-all      |
| `detection_config/latest` create / set / update / delete                  | deny | deny           | server-only writes                         |
| `stripe_events/evt_1` get / list / set                                    | deny | deny           | server-only, no client access              |
| collection-group query on `users`, `anything`, `history`, `stripe_events` | deny | deny           | no `{path=**}` match grants them           |
| `random/doc` get / set                                                    | deny | deny           | catch-all                                  |

"create" is a `setDoc` on a new id in the same collection; "set" overwrites the seeded doc.

## Manual fallback (no Node test run)

1. In `apps/web`, run `npx -y firebase-tools@15.32.1 emulators:start --only firestore --project demo-warden-rules`
   after setting `"ui": { "enabled": true }` in `firebase.json` (do not commit that change).
2. Open the Emulator UI, Firestore, then **Rules playground**.
3. For each matrix row, pick the method and path, toggle **Authenticated** (uid `u1`) on or off, and
   check the verdict against the table.

## V2: wire into CI

Phase 7 `ci.yml` should run `pnpm --filter web test:rules` on a runner with Java 21, and cache
`~/.cache/firebase/emulators`. The production deploy of these rules is Story 1.15.
