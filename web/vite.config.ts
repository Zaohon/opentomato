import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api/eas': {
        target: 'http://1961664646385841.cn-shanghai.pai-eas.aliyuncs.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/eas/, '')
      },
      '/api/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    }
  },
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    }
  }
});
