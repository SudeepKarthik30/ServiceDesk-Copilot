import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, /api calls are proxied to Django so the browser never hits CORS.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // 127.0.0.1, not localhost: Node resolves localhost to IPv6 (::1) but runserver listens on IPv4.
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
