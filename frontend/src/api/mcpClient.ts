import axios from 'axios';

// Add type definition for the window.__env property
declare global {
  interface Window {
    __env?: {
      MCP_SERVER?: string;
      [key: string]: any;
    }
  }
}

// Check for MCP server URL in environment variables
const getMcpServerUrl = () => {
  // 1. Prioritize MCP_SERVER from import.meta.env (if Vite is configured to expose it)
  if (import.meta.env && typeof import.meta.env.MCP_SERVER === 'string') {
    console.log("Using MCP_SERVER from import.meta.env.MCP_SERVER:", import.meta.env.MCP_SERVER);
    return import.meta.env.MCP_SERVER;
  }

  // 2. Fallback to VITE_MCP_SERVER (Vite's default prefixing)
  if (import.meta.env && typeof import.meta.env.VITE_MCP_SERVER === 'string') {
    console.log("Using MCP_SERVER from import.meta.env.VITE_MCP_SERVER:", import.meta.env.VITE_MCP_SERVER);
    return import.meta.env.VITE_MCP_SERVER;
  }

  // 3. Fallback for process.env.REACT_APP_MCP_SERVER (e.g., Create React App or polyfilled process)
  // @ts-ignore process is not defined in standard browser env
  if (typeof process !== 'undefined' && process.env && typeof process.env.REACT_APP_MCP_SERVER === 'string') {
    // @ts-ignore
    console.log("Using MCP_SERVER from process.env.REACT_APP_MCP_SERVER:", process.env.REACT_APP_MCP_SERVER);
    // @ts-ignore
    return process.env.REACT_APP_MCP_SERVER;
  }
  
  // 4. Try to access from window.__env (runtime config injected via script)
  if (typeof window !== 'undefined' && 
      window.__env && 
      typeof window.__env.MCP_SERVER === 'string') {
    console.log("Using MCP_SERVER from window.__env.MCP_SERVER:", window.__env.MCP_SERVER);
    return window.__env.MCP_SERVER;
  }
  
  // 5. Default fallback
  console.log("Using default MCP_SERVER: http://localhost:9000");
  return 'http://localhost:9000';
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