import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Box, Flex, Spinner, Center, VStack, Text, useToast, Container } from '@chakra-ui/react';
import { getCurrentUser, refreshToken } from './api/auth';

// Pages
import SignIn from './pages/SignIn';
import FilterSetup from './pages/FilterSetup';
import EmailReview from './pages/EmailReview';
import Search from './pages/Search';
import Support from './pages/Support';

// Documentation Pages
import Documentation from './pages/documentation/Documentation';
import SecureAuthentication from './pages/documentation/SecureAuthentication';
import SmartFiltering from './pages/documentation/SmartFiltering';
import AIAnalysis from './pages/documentation/AIAnalysis';
import KnowledgeBase from './pages/documentation/KnowledgeBase';
import AITraining from './pages/documentation/AITraining';

// Components
import TopNavbar from './components/TopNavbar';

// Loading Component
const LoadingScreen = () => (
  <Center height="100vh">
    <VStack spacing={4}>
      <Spinner size="xl" thickness="4px" speed="0.65s" />
      <Text>Loading your profile...</Text>
    </VStack>
  </Center>
);

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const toast = useToast();
  const navigate = useNavigate();
  
  // Handle logout
  const handleLogout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('expires');
    localStorage.removeItem('refresh_token');
    setIsAuthenticated(false);
    navigate('/', { replace: true });
  }, [navigate]);

  // Function to refresh token
  const handleTokenRefresh = useCallback(async () => {
    console.log('handleTokenRefresh called');
    try {
      // Get the MS refresh token from localStorage
      const msRefreshToken = localStorage.getItem('refresh_token');
      if (!msRefreshToken) {
        console.log('No MS refresh token available in localStorage');
        throw new Error('No MS refresh token available');
      }
      
      console.log('Calling refreshToken API with MS token...');
      // Call the updated API function, passing the MS refresh token
      const response = await refreshToken(msRefreshToken);
      
      // Check if the backend returned a new internal access token
      if (response.access_token) {
        console.log('Token refresh successful, updating localStorage');
        // Store the NEW internal JWT access token and its expiry
        localStorage.setItem('token', response.access_token);
        localStorage.setItem('expires', response.expires_at);
        
        // If the backend also returned a NEW MS refresh token, update it
        // (Assuming backend might return it as 'ms_refresh_token')
        // if (response.ms_refresh_token) {
        //   localStorage.setItem('refresh_token', response.ms_refresh_token);
        // }
        
        return true; // Indicate success
      }
      // If backend didn't return access_token (shouldn't happen on success)
      console.log('Token refresh API call succeeded but no access_token returned');
      return false;
    } catch (error) {
      console.error('handleTokenRefresh failed:', error);
      // Error handling (like clearing localStorage) might already be done in the API function
      // handleLogout(); // Optionally call logout here if not handled in API
      return false; // Indicate failure
    }
  }, []); // Removed refreshToken from dependencies as it's an import

  // Function to check token expiration and refresh if needed
  const checkAndRefreshToken = useCallback(async () => {
    const expires = localStorage.getItem('expires');
    if (!expires) return false;

    const expiryDate = new Date(expires);
    const now = new Date();
    const timeUntilExpiry = expiryDate.getTime() - now.getTime();

    // If token expires in less than 5 minutes, try to refresh it
    if (timeUntilExpiry < 5 * 60 * 1000) {
      return await handleTokenRefresh();
    }
    return true;
  }, [handleTokenRefresh]);

  // Check for token on load and set up refresh interval
  useEffect(() => {
    const checkAuth = async () => {
      try {
        setIsLoading(true);
        const token = localStorage.getItem('token');
        const expires = localStorage.getItem('expires');
        
        if (!token || !expires) {
          setIsAuthenticated(false);
          setIsLoading(false);
          setIsInitialLoad(false);
          return;
        }

        // Check if token is expired
        const expiryDate = new Date(expires);
        if (expiryDate <= new Date()) {
          // Try to refresh token first
          const refreshed = await handleTokenRefresh();
          if (!refreshed) {
            handleLogout();
            return;
          }
        }
        
        // Verify token with backend
        try {
          await getCurrentUser();
          setIsAuthenticated(true);
          console.log('Authentication successful');
        } catch (error: any) {
          console.error('Token verification failed:', error);
          // Try to refresh token on verification failure
          const refreshed = await handleTokenRefresh();
          if (!refreshed) {
            handleLogout();
          } else {
            // Try verification again after refresh
            try {
              await getCurrentUser();
              setIsAuthenticated(true);
              console.log('Authentication successful after token refresh');
            } catch (error) {
              console.error('Token verification failed after refresh:', error);
              handleLogout();
            }
          }
        }
      } catch (error: any) {
        console.error('Auth check error:', error);
        handleLogout();
      } finally {
        setIsLoading(false);
        setIsInitialLoad(false);
      }
    };

    // Check auth on mount
    checkAuth();

    // Set up interval to check token expiration
    const interval = setInterval(checkAndRefreshToken, 4 * 60 * 1000); // Check every 4 minutes
    return () => clearInterval(interval);
  }, [navigate, handleTokenRefresh, checkAndRefreshToken, handleLogout]);
  
  // Show loading screen only during initial load
  if (isInitialLoad && isLoading) {
    return <LoadingScreen />;
  }

  return (
    <Box minH="100vh">
      <TopNavbar onLogout={handleLogout} isAuthenticated={isAuthenticated} />
      <Container maxW="1400px" py={4}>
        <Routes>
          {/* Documentation Routes */}
          <Route path="/docs" element={<Documentation />} />
          <Route path="/docs/secure-authentication" element={<SecureAuthentication />} />
          <Route path="/docs/features/secure-authentication" element={<SecureAuthentication />} />
          <Route path="/docs/smart-filtering" element={<SmartFiltering />} />
          <Route path="/docs/features/smart-filtering" element={<SmartFiltering />} />
          <Route path="/docs/knowledge-base" element={<KnowledgeBase />} />
          <Route path="/docs/features/knowledge-base" element={<KnowledgeBase />} />
          <Route path="/docs/email-processing" element={<SmartFiltering />} />
          <Route path="/docs/ai-analysis" element={<AIAnalysis />} />
          <Route path="/docs/features/ai-analysis" element={<AIAnalysis />} />
          <Route path="/docs/ai-training" element={<AITraining />} />
          <Route path="/support" element={<Support />} />
          
          {/* App Routes - with padding and authentication */}
          <Route path="/*" element={
            <Box flex="1">
              <Box p={4}>
                <Routes>
                  <Route 
                    path="/" 
                    element={
                      <SignIn 
                        onLogin={() => {
                          setIsAuthenticated(true);
                        }}
                        isAuthenticated={isAuthenticated}
                      />
                    } 
                  />
                  <Route 
                    path="/filter" 
                    element={
                      isLoading ? (
                        <LoadingScreen />
                      ) : isAuthenticated ? (
                        <FilterSetup />
                      ) : (
                        <Navigate to="/" replace={true} />
                      )
                    } 
                  />
                  <Route 
                    path="/review" 
                    element={
                      isLoading ? (
                        <LoadingScreen />
                      ) : isAuthenticated ? (
                        <EmailReview />
                      ) : (
                        <Navigate to="/" replace={true} />
                      )
                    } 
                  />
                  <Route 
                    path="/search" 
                    element={
                      isLoading ? (
                        <LoadingScreen />
                      ) : isAuthenticated ? (
                        <Search />
                      ) : (
                        <Navigate to="/" replace={true} />
                      )
                    } 
                  />
                </Routes>
              </Box>
            </Box>
          } />
        </Routes>
      </Container>
    </Box>
  );
}

export default App;
