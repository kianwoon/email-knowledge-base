import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

// Define a structure for potential error details from the backend
interface ApiErrorDetail {
  loc?: (string | number)[];
  msg: string;
  type: string;
}

// Define the expected structure of an error response from the API
interface ApiErrorResponse {
  detail?: string | ApiErrorDetail[];
}

// Create an Axios instance with base configuration
export const apiClient = axios.create({
  // Use VITE_ environment variable for base URL, fallback to relative path
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json', // Ensure we accept JSON responses
  },
  timeout: 30000, // 30 second timeout for requests
  // *** CRUCIAL FOR HttpOnly COOKIE AUTHENTICATION ***
  withCredentials: true, 
});

// --- Request Interceptor --- 
// Note: No need to manually attach Authorization header for HttpOnly cookies
// The browser handles sending the cookie automatically if withCredentials=true
// const requestInterceptor = ... 
// apiClient.interceptors.request.use(requestInterceptor);
console.log('[API Client] Configured with withCredentials=true for HttpOnly cookie auth.');

// --- Response Interceptor --- 
// Handle successful responses (passthrough)
const responseInterceptor = (response: any) => response;

// Handle errors, specifically 401 for session expiry
const errorInterceptor = (error: AxiosError<ApiErrorResponse>) => {
  // Log the full error for debugging
  console.error('[API Client] Request Error:', error);

  // Check if it's a 401 Unauthorized error
  if (error.response?.status === 401) {
    console.warn('[API Client] Received 401 Unauthorized. Assuming session expired.');
    
    // Optionally remove potentially invalid tokens
    // localStorage.removeItem('access_token');
    // localStorage.removeItem('refresh_token');
    
    // Dispatch a custom event that App.tsx can listen for to show login modal/redirect
    window.dispatchEvent(new CustomEvent('session-expired'));
    
    // It's usually better to let the main App component handle redirection/UI changes 
    // rather than doing window.location.href here, to allow for smoother UX (e.g., showing a modal).
    
  } else {
    // Log details of other errors
    const status = error.response?.status;
    const errorMsg = error.response?.data?.detail || error.message;
    console.error(`[API Client] Error Details: Status ${status}, Message: ${JSON.stringify(errorMsg)}`);
  }

  // IMPORTANT: Reject the promise so the calling code (.catch block) can handle the error
  return Promise.reject(error);
};

// Apply the response interceptor
apiClient.interceptors.response.use(responseInterceptor, errorInterceptor);

// Optional: Function to setup interceptors if needed (e.g., for HMR)
export const setupInterceptors = () => {
  // This function can be called in your main App component useEffect 
  // to ensure interceptors are applied, especially if issues arise with hot module replacement.
  // Note: Interceptors are already applied above during module initialization.
  console.log('[API Client] Ensuring Axios interceptors are set up (withCredentials=true).');
}; 