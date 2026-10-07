import { defineConfig } from 'vitest/config'

// Story 1.14: Firestore security-rules suite. Runs ONLY through `pnpm --filter web test:rules`,
// which starts the Firestore emulator (firebase-tools via pinned npx) and sets
// FIRESTORE_EMULATOR_HOST. The default `vitest.config.ts` excludes this file.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['firestore.rules.test.ts'],
    // Emulator cold start + first rules compile can be slow.
    testTimeout: 30000,
    hookTimeout: 60000,
    // One emulator, one shared database: run files serially.
    fileParallelism: false,
  },
})
