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
  const toast = useToast();
  const navigate = useNavigate();
  
  // Handle logout
  const handleLogout = useCallback(() => {
    console.log("--- handleLogout CALLED! ---");
    localStorage.removeItem('accessToken');
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
        // Store the NEW internal JWT access token and its expiry using 'accessToken'
        localStorage.setItem('accessToken', response.access_token);
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

  // --- RESTORE checkAuth FUNCTION DEFINITION --- 
  const checkAuth = useCallback(async () => {
    console.log("--- checkAuth running ---");
    try {
      // Read using 'accessToken'
      const token = localStorage.getItem('accessToken');
      const expires = localStorage.getItem('expires');

      if (!token || !expires) {
        console.log("checkAuth: No token or expires found in localStorage.");
        // handleLogout() will set isAuthenticated to false
        setIsAuthenticated(false); 
        return; // Exit early
      }

      // Check if token is expired
      const expiryDate = new Date(expires);
      let needsVerification = true; // Assume verification is needed

      if (expiryDate <= new Date()) {
        console.log("checkAuth: Token expired, attempting refresh...");
        const refreshed = await handleTokenRefresh();
        if (!refreshed) {
          console.log("checkAuth: Token refresh failed.");
          handleLogout(); // Logout if refresh fails
          needsVerification = false; // No need to verify if logout happened
        } else {
          console.log("checkAuth: Token refresh successful.");
          // Token is refreshed, proceed to verification
          needsVerification = true; 
        }
      }

      // Verify token with backend if needed
      if (needsVerification) {
         // Re-read token in case it was just refreshed
         const currentToken = localStorage.getItem('accessToken');
         if (!currentToken) { // Safety check
             console.log("checkAuth: Token missing after potential refresh check.");
             handleLogout();
         } else {
            try {
              console.log("checkAuth: Verifying token with backend...");
              await getCurrentUser(); // Assumes getCurrentUser uses the token via interceptor
              setIsAuthenticated(true);
              console.log('checkAuth: Authentication successful (token valid).');
            } catch (verificationError: any) {
              console.error('checkAuth: Token verification failed:', verificationError);              
              // If verification fails even after potential refresh, logout
              handleLogout(); 
            }
          }
      }
    } catch (error: any) {
      console.error('checkAuth: Unexpected error:', error);
      handleLogout(); // Logout on any unexpected error during auth check
    } finally {
       // Ensure loading is always set to false after checks complete
       console.log("checkAuth: Setting isLoading to false.");
       setIsLoading(false);
    }
  }, [handleLogout, handleTokenRefresh]); // Dependencies for checkAuth

  // useEffect hook for initial auth processing
  useEffect(() => {
    const processAuth = async () => {
      console.log("--- App useEffect running processAuth ---"); 
      const urlParams = new URLSearchParams(window.location.search);
      const tokenFromUrl = urlParams.get('token');
      const expiresFromUrl = urlParams.get('expires');

      console.log(`Token from URL: ${tokenFromUrl ? 'FOUND' : 'MISSING'}`);
      console.log(`Expires from URL: ${expiresFromUrl ? 'FOUND' : 'MISSING'}`);

      if (tokenFromUrl && expiresFromUrl) {
        console.log("URL Params FOUND: Clearing old token/expires, storing new, setting auth=true."); 
        // Explicitly remove old items first
        localStorage.removeItem('accessToken');
        localStorage.removeItem('expires');
        
        // Store new items
        localStorage.setItem('accessToken', tokenFromUrl);
        localStorage.setItem('expires', expiresFromUrl);
        setIsAuthenticated(true);
        // Decode user info here if needed from tokenFromUrl
        // setUser(parseJwt(tokenFromUrl)); 
        window.history.replaceState({}, document.title, window.location.pathname);
        setIsLoading(false); // Stop loading indicator since auth state is set
      } else {
        console.log("URL Params MISSING: Calling checkAuth to look in localStorage."); 
        await checkAuth(); // Call the restored checkAuth function
      }
    };

    processAuth();
  }, [checkAuth]); // Dependency array includes checkAuth

  // Render loading state or children
  // Use isLoading directly for the loading screen check
  if (isLoading) {
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
