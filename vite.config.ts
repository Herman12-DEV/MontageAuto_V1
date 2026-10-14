import { defineConfig } from 'vite'
import type { ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'

// En développement, les appels /api sont relayés vers le backend FastAPI.
const backend = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

const apiProxy: ProxyOptions = {
  target: backend,
  changeOrigin: true,
  // Backend arrêté ou en cours de redémarrage : réponse JSON explicite (le site réessaie tout seul).
  configure: (proxy) => {
    proxy.on('error', (_error, _req, res) => {
      if (!('writeHead' in res) || res.headersSent) return
      res.writeHead(503, { 'Content-Type': 'application/json' })
      res.end(
        JSON.stringify({
          detail: {
            code: 'backend_down',
            message: 'Le serveur AutoCut ne répond pas. Lancez-le avec « npm start » puis réessayez.',
          },
        }),
      )
    })
  },
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '::',
    allowedHosts: ['.e2b.app'],
    proxy: { '/api': apiProxy },
  },
  preview: {
    host: '::',
    proxy: { '/api': apiProxy },
  },
})
