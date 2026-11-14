import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';


// Built files go to /ui/ (not /assets/, which the studio uses for job and variant files).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
  base: '/',
  build: { outDir: 'dist', assetsDir: 'ui', emptyOutDir: true, chunkSizeWarningLimit: 900 },
  server: { port: 5174, proxy: { '/api': 'http://localhost:5173', '/assets': 'http://localhost:5173' } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
