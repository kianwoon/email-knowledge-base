import { AxiosError, AxiosResponse } from 'axios';
import apiClient from './apiClient';
import { refreshToken } from './auth'; // Import the specific function

export const setupResponseInterceptor = () => {
  apiClient.interceptors.response.use(
    (response: AxiosResponse) => {
      console.log('[Interceptor] Response Status:', response.status);
      return response;
    },
    async (error: AxiosError) => {
      console.error('[Interceptor] Response Error:', error);

      const originalRequest = error.config as any; // Use 'any' or define a type for _retry

      // If the error is 401 and we haven't tried to refresh the token yet
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        try {
          const msRefreshToken = localStorage.getItem('refresh_token');
          if (!msRefreshToken) {
            throw new Error('Cannot refresh: MS refresh token not found in localStorage.');
          }
          console.log('[Interceptor] Attempting token refresh...');
          const refreshResponse = await refreshToken(msRefreshToken);
          console.log('[Interceptor] Refresh successful.');
          
          if (refreshResponse.access_token && originalRequest.headers) {
             // Update the authorization header in the original request config
            originalRequest.headers['Authorization'] = `Bearer ${refreshResponse.access_token}`;
            // Retry the original request using the modified config
            console.log('[Interceptor] Retrying original request with new token.');
            return apiClient(originalRequest);
          } else {
             throw new Error('Refresh response did not contain access token.');
          }
        } catch (refreshError) {
          console.error('[Interceptor] Token refresh failed:', refreshError);
          // Clear tokens and redirect to login
          localStorage.removeItem('token');
          localStorage.removeItem('expires');
          localStorage.removeItem('refresh_token');
          // Redirect to root, which should handle login redirect if needed
          window.location.href = '/';
          return Promise.reject(refreshError); // Reject the promise after redirecting
        }
      }

      return Promise.reject(error);
    }
  );
  console.log('[Interceptor] Response interceptor set up.');
}; 