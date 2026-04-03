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
    proxy: {
      // All /api/* requests forwarded to Django backend inside Docker network
      '/api': {
        target: process.env.VITE_API_BASE_URL ?? 'http://backend:8000',
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
