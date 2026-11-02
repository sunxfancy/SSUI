import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      ssui_components: path.resolve(__dirname, '../ssui_components/src/index.ts'),
    },
  },
  test: {
    include: ['test/**/*.test.ts', 'test/**/*.test.tsx'],
    environment: 'jsdom',
    environmentOptions: {
      jsdom: { url: 'http://localhost:7420/functional_ui/' },
    },
    setupFiles: ['./test/setup.ts'],
    restoreMocks: true,
    clearMocks: true,
  },
});
