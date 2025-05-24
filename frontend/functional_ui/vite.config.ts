import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from 'path'
import customImport from './customImport'

const host = process.env.TAURI_DEV_HOST;

// https://vitejs.dev/config/
export default defineConfig(async ({ mode }) => {
  return {
    base: "/functional_ui/",
    plugins: [
        react(),
        customImport()
    ],

    // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
    //
    // 1. prevent vite from obscuring rust errors
    clearScreen: false,
    // 2. tauri expects a fixed port, fail if that port is not available
    resolve: {
      alias: mode === 'development'
          ? {
            'ssui_components': path.resolve(__dirname, '../ssui_components/src/index.ts'),
          }
          : {}
    },
    server: {
      port: 7420,
      strictPort: true,
      host: host || false,
      hmr: host
          ? {
            protocol: "ws",
            host,
            port: 7421,
          }
          : undefined,
      watch: {
        // 3. tell vite to ignore watching `src-tauri`
        ignored: ["**/src-tauri/**"],
      },
      proxy: {
        '/api': {
          target: 'http://localhost:7422',
          changeOrigin: true,
        },
        '/config': {
          target: 'http://localhost:7422',
          changeOrigin: true,
        },
        '/file': {
          target: 'http://localhost:7422',
          changeOrigin: true,
        },
        '/extension': {
          target: 'http://localhost:7422',
          changeOrigin: true,
        },
        "/ws": {
          target: 'ws://localhost:7422',
          changeOrigin: true,
          ws: true,
        }
      }
    },
  }
});
