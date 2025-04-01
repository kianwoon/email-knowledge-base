import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '');
  
  const apiBaseUrl = env.VITE_API_BASE_URL || 'https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api';
  const backendUrl = env.VITE_BACKEND_URL || 'https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app';
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    define: {
      __API_BASE_URL__: JSON.stringify(apiBaseUrl),
      __BACKEND_URL__: JSON.stringify(backendUrl),
      'process.env.VITE_API_BASE_URL': JSON.stringify(apiBaseUrl),
      'process.env.VITE_BACKEND_URL': JSON.stringify(backendUrl),
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(apiBaseUrl),
      'import.meta.env.VITE_BACKEND_URL': JSON.stringify(backendUrl),
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: backendUrl,
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
          target: apiBaseUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          secure: false,
        }
      },
    }
  };
});
