import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['test/**/*.test.ts'],
    testTimeout: 30000,
    hookTimeout: 15000,
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
