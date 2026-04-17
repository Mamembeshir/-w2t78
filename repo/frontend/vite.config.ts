import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      // @/ → src/ for clean imports: import { api } from '@/lib/api'
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    host: '0.0.0.0',   // bind to all interfaces for Docker + LAN access
    port: 5173,
    strictPort: true,  // fail fast if port taken
    // Allow the Docker-internal hostname used by the containerised E2E runner.
    // Vite 5+ blocks unknown Host headers by default (security hardening).
    allowedHosts: ['host.docker.internal'],
    proxy: {
      // All /api/* requests forwarded to Django backend.
      // API_PROXY_TARGET is set by docker-compose (http://backend:8000).
      // Defaults to http://localhost:8000 for local dev outside Docker.
      // NOT a VITE_-prefixed var — never embedded in browser bundle.
      '/api': {
        target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        // Do not rewrite path — Django expects /api/... intact
      },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: false,      // no sourcemaps in production build (offline, no external tools)
    rollupOptions: {
      output: {
        // Split vendor chunks for better cache utilisation
        manualChunks: {
          react:  ['react', 'react-dom'],
          router: ['react-router-dom'],
          query:  ['@tanstack/react-query'],
          axios:  ['axios'],
        },
      },
    },
  },
})
