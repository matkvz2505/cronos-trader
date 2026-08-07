import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5180,
    // Proxy para o backend: o navegador fala só com :5180, então não há CORS nem
    // configuração de URL diferente entre dev e produção.
    proxy: {
      '/api': {
        target: 'http://localhost:1840',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:1840',
        ws: true,
      },
    },
  },
  build: {
    // lightweight-charts é grande; separá-lo evita invalidar o bundle da app a cada
    // deploy só porque uma tela mudou.
    rollupOptions: {
      output: {
        manualChunks: {
          grafico: ['lightweight-charts'],
        },
      },
    },
  },
});
