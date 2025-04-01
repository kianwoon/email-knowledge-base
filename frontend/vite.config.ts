import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '');
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    define: {
      __API_BASE_URL__: JSON.stringify(env.VITE_API_BASE_URL),
      __BACKEND_URL__: JSON.stringify(env.VITE_BACKEND_URL),
      'process.env.VITE_API_BASE_URL': JSON.stringify(env.VITE_API_BASE_URL),
      'process.env.VITE_BACKEND_URL': JSON.stringify(env.VITE_BACKEND_URL),
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(env.VITE_API_BASE_URL),
      'import.meta.env.VITE_BACKEND_URL': JSON.stringify(env.VITE_BACKEND_URL),
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_BACKEND_URL || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          secure: false,
        }
      },
    },
    preview: {
      port: 5173,
      host: true,
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL?.replace('/api', '') || env.VITE_BACKEND_URL,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          secure: false,
        }
      },
    }
  };
});
