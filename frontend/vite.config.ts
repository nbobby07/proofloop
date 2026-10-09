import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

const envDir = fileURLToPath(new URL('..', import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, envDir, 'PROOFLOOP_')
  return {
    plugins: [react(), tailwindcss()],
    envDir,
    server: {
      host: process.env.PROOFLOOP_FRONTEND_HOST ?? env.PROOFLOOP_FRONTEND_HOST ?? 'localhost',
      port: Number(process.env.PROOFLOOP_FRONTEND_PORT ?? env.PROOFLOOP_FRONTEND_PORT ?? 5173),
      strictPort: true,
    },
  }
})
