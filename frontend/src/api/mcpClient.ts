import axios from 'axios';

// Add type definition for the window.__env property
declare global {
  interface Window {
    __env?: {
      MCP_SERVER?: string;
      [key: string]: any;
    }
  }
  // Declare the global constant that Vite will define
  const __MCP_SERVER_URL__: string;
}

// Check for MCP server URL
const getMcpServerUrl = () => {
  // 1. Prioritize __MCP_SERVER_URL__ (defined by Vite)
  // Also check it's not the literal string "undefined" which can happen if env var was missing at build time and stringified
  if (typeof __MCP_SERVER_URL__ === 'string' && __MCP_SERVER_URL__ !== 'undefined' && __MCP_SERVER_URL__.length > 0) {
    console.log("Using MCP_SERVER from global __MCP_SERVER_URL__ (defined by Vite):", __MCP_SERVER_URL__);
    return __MCP_SERVER_URL__;
  }

  // 2. Try to access from window.__env (runtime config injected via script)
  if (typeof window !== 'undefined' && 
      window.__env && 
      typeof window.__env.MCP_SERVER === 'string' && 
      window.__env.MCP_SERVER.length > 0) {
    console.log("Using MCP_SERVER from window.__env.MCP_SERVER:", window.__env.MCP_SERVER);
    return window.__env.MCP_SERVER;
  }
  
  // 3. If no configuration is found, throw an error
  const errorMessage = "MCP_SERVER URL is not configured. Ensure MCP_SERVER is set in .env for Vite build (to define __MCP_SERVER_URL__) or MCP_SERVER in window.__env for runtime config.";
  console.error(errorMessage);
  throw new Error(errorMessage);
};

// Get MCP server URL using our helper function
const MCP_SERVER = getMcpServerUrl();
console.log(`MCP client initialized with server URL: ${MCP_SERVER}`);

// Create a dedicated MCP client
const mcpClient = axios.create({
  baseURL: MCP_SERVER,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request and response interceptors for better logging
mcpClient.interceptors.request.use(
  (config) => {
    console.log(`MCP Request to: ${config.url}`);
    console.log('MCP Request full config:', {
      method: config.method,
      url: config.url,
      baseURL: config.baseURL,
      headers: config.headers,
      data: config.data
    });
    return config;
  },
  (error) => {
    console.error('MCP Request Error:', error);
    return Promise.reject(error);
  }
);

mcpClient.interceptors.response.use(
  (response) => {
    console.log(`MCP Response from: ${response.config.url}, Status: ${response.status}`);
    return response;
  },
  (error) => {
    if (error.response) {
      console.error(`MCP Error: ${error.response.status} - ${error.response.statusText}`);
      console.error('MCP Error Data:', error.response.data);
    } else if (error.request) {
      console.error('MCP No Response Received:', error.request);
    } else {
      console.error('MCP Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default mcpClient; 