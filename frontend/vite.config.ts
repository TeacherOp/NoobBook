import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      src: path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174,
  },
  optimizeDeps: {
    include: ['mermaid'],
  },
  ssr: {
    noExternal: ['mermaid'],
  },
})
