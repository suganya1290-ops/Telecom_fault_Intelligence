import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:8000'

  return {
    plugins: [react()],

    server: {
      port: 5173,
      strictPort: true,
      // Proxy all /api/* (including /api/v1/*) to the backend so the browser
      // never makes a cross-origin request during development.
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
          // No path rewrite — /api/v1/... passes through unchanged.
        },
      },
    },

    build: {
      outDir: 'dist',
      sourcemap: true,
      minify: 'terser',
    },
  }
})
