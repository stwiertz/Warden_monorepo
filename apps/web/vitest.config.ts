import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.react-singleton.ts', './vitest.setup.ts'],
    globals: true,
    // Inlining the React libraries below makes the first transform of a suite slower; under a
    // full parallel run a cold `await import('./layout')` can exceed the 5 s default.
    testTimeout: 15000,
    // Under node-linker=hoisted several ESM React libraries carry their own nested
    // node_modules/react copy. Inline them so their `react` import goes through Vite and
    // resolve.dedupe below; CJS requires are pinned by vitest.react-singleton.ts.
    server: {
      deps: {
        inline: [
          /@base-ui[\\/]/,
          /@floating-ui[\\/]/,
          /react-hook-form/,
          /@hookform[\\/]/,
          /lucide-react/,
        ],
      },
    },
  },
  resolve: {
    dedupe: ['react', 'react-dom'],
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
