import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The metric definitions (../metrics/definitions.yaml) are imported from
// the BasicAnalysis repository, one folder up.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 5173, strictPort: true, fs: { allow: ['..'] } },
  envPrefix: ['VITE_', 'TAURI_'],
  build: { target: 'es2022', outDir: 'dist', chunkSizeWarningLimit: 4000 },
});
