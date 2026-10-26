import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  root: fileURLToPath(new URL('./test/native', import.meta.url)),
  plugins: [react()],
  build: { outDir: '../../dist-native-test', emptyOutDir: true },
});
