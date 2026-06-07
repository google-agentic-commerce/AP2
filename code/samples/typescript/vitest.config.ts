import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['test/**/*.test.ts'],
    testTimeout: 30000,
    hookTimeout: 15000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      // Scope to the Verifiable Intent integration core (the unit-tested glue).
      // The role servers / mandate-tools need stdio servers to exercise, so they
      // are covered by e2e, not the unit suite — see BACKLOG.md.
      include: ['src/common/vi/**/*.ts'],
      exclude: ['src/common/vi/index.ts'],
    },
  },
  resolve: {
    extensions: ['.ts', '.js'],
    alias: {
      // Allow .js imports to resolve to .ts source files
    },
    conditions: ['import', 'module', 'browser', 'default'],
  },
  // Vite will strip .js extensions from imports automatically in resolve
  // But for NodeNext module resolution we need this:
  esbuild: {
    target: 'node18',
  },
});
