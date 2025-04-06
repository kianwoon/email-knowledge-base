import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import fs from 'fs';

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const root = process.cwd();
  
  // Debug environment files
  console.log('=== Environment Files Check ===');
  console.log('Current Mode:', mode);
  console.log('Command:', command);
  console.log('Looking for env files in:', root);
  console.log('Env files found:', {
    '.env': fs.existsSync(path.join(root, '.env')),
    '.env.local': fs.existsSync(path.join(root, '.env.local')),
    '.env.production': fs.existsSync(path.join(root, '.env.production')),
    '.env.development': fs.existsSync(path.join(root, '.env.development'))
  });

  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, root, '');
  
  console.log('=== Environment Variables Loaded ===');
  console.log('Mode:', mode);
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path
        }
      },
    },
    preview: {
      port: 5173,
      host: true,
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          secure: false,
        }
      },
    }
  };
});
