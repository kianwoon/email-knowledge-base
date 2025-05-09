import axios from 'axios';

// Simple function to determine the MCP server URL
function getMcpServerUrl() {
  // Hardcoded URL for Docker build (will be replaced by Vite)
  const hardcodedUrl = 'https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/invoke/';
  
  try {
    // Try to get from window.__env if it exists (runtime config)
    if (typeof window !== 'undefined' && 
        window.__env && 
        typeof window.__env.MCP_SERVER === 'string' && 
        window.__env.MCP_SERVER.trim().length > 0) {
      console.log('Using MCP_SERVER from window.__env:', window.__env.MCP_SERVER);
      return window.__env.MCP_SERVER.trim();
    }
    
    // Otherwise, use the hardcoded URL
    console.log('Using hardcoded MCP_SERVER URL:', hardcodedUrl);
    return hardcodedUrl;
  } catch (err) {
    console.error('Error determining MCP server URL, using hardcoded URL:', err);
    return hardcodedUrl;
  }
}

// Global types for TypeScript
declare global {
  interface Window {
    __env?: {
      MCP_SERVER?: string;
      [key: string]: any;
    }
  }
}

// Create the client
const mcpClient = axios.create({
  baseURL: getMcpServerUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000
});

// Basic request logging
mcpClient.interceptors.request.use(
  (config) => {
    console.log(`MCP Request to: ${config.url}`);
    console.log('MCP Request full config:', config);
    return config;
  },
  (error) => {
    console.error('MCP Request Error:', error);
    return Promise.reject(error);
  }
);

// Basic response logging
mcpClient.interceptors.response.use(
  (response) => {
    console.log(`MCP Response from: ${response.config.url}, Status: ${response.status}`);
    return response;
  },
  (error) => {
    if (error.response) {
      console.error(`MCP Error: ${error.response.status} - ${error.response.statusText}`);
    } else if (error.request) {
      console.error('MCP No Response Received:', error.request);
    } else {
      console.error('MCP Error:', error.message);
    }
    return Promise.reject(error);
  }
);

// Export the client
export default mcpClient; 