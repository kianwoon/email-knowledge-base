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
  // Explicitly log MCP_SERVER and its type for Docker build debugging
  console.log('[VITE_CONFIG_DEBUG] MCP_SERVER value from loadEnv:', env.MCP_SERVER);
  console.log('[VITE_CONFIG_DEBUG] typeof env.MCP_SERVER:', typeof env.MCP_SERVER);
  console.log('[VITE_CONFIG_DEBUG] We are using a direct hardcoded URL in mcpClient.ts for maximum build compatibility.');
  
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
          configure: (proxy, options) => {
            proxy.on('proxyReq', (proxyReq, req, res) => {
              // Forward Authorization header if present on incoming request
              if (req.headers['authorization']) {
                console.log('[Vite Proxy] Forwarding Authorization header:', req.headers['authorization']);
                proxyReq.setHeader('Authorization', req.headers['authorization']);
              }
              // Forward Cookies if present (Vite might do this with changeOrigin, but explicitly helps)
              if (req.headers.cookie) {
                 console.log('[Vite Proxy] Forwarding Cookie header:', req.headers.cookie);
                 proxyReq.setHeader('Cookie', req.headers.cookie);
              }
            });
          }
        },
        // Add WebSocket proxy configuration
        '/ws': {
          target: 'ws://localhost:8000', // Target your backend WebSocket server
          ws: true, // Enable WebSocket proxying
          changeOrigin: true,
          secure: false, // Adjust if your backend uses wss
          rewrite: (path) => path.replace(/^\/ws/, ''), // Remove /ws prefix
          configure: (proxy, options) => {
            proxy.on('error', (err, req, res) => {
              console.error('[Vite WS Proxy] Proxy error:', err);
              if (res && typeof res.writeHead === 'function') { // Check if res is a valid ServerResponse
                res.writeHead(500, {
                  'Content-Type': 'text/plain',
                });
                res.end('WebSocket proxy error');
              } else if (res && res.socket && typeof res.socket.end === 'function') { // For WS connections
                 res.socket.end();
              }
            });
          }
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
          secure: false,
           configure: (proxy, options) => {
            proxy.on('proxyReq', (proxyReq, req, res) => {
              // Forward Authorization header if present on incoming request
              if (req.headers['authorization']) {
                 console.log('[Vite Proxy Preview] Forwarding Authorization header:', req.headers['authorization']);
                 proxyReq.setHeader('Authorization', req.headers['authorization']);
              }
              // Forward Cookies if present
              if (req.headers.cookie) {
                 console.log('[Vite Proxy Preview] Forwarding Cookie header:', req.headers.cookie);
                 proxyReq.setHeader('Cookie', req.headers.cookie);
              }
            });
          }
        },
        // Add WebSocket proxy configuration for preview as well
        '/ws': {
          target: 'ws://localhost:8000', // Adjust if your VITE_API_BASE_URL implies a different WS target
          ws: true,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/ws/, ''), // Remove /ws prefix
          configure: (proxy, options) => {
            proxy.on('error', (err, req, res) => {
              console.error('[Vite WS Proxy Preview] Proxy error:', err);
              if (res && typeof res.writeHead === 'function') {
                res.writeHead(500, {
                  'Content-Type': 'text/plain',
                });
                res.end('WebSocket proxy error');
              } else if (res && res.socket && typeof res.socket.end === 'function') {
                 res.socket.end();
              }
            });
          }
        }
      },
    }
  };
});
