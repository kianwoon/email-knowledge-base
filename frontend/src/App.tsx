import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import {
  Box, Flex, Spinner, Center, VStack, Text, useToast, Container,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalFooter, ModalBody, ModalCloseButton, Button, useDisclosure
} from '@chakra-ui/react';
import { getCurrentUser, logout as logoutApi } from './api/auth';
import { useTranslation } from 'react-i18next';
import { setupInterceptors } from './api/apiClient';

// Pages
import SignIn from './pages/SignIn';
import FilterSetup from './pages/FilterSetup';
import EmailReview from './pages/EmailReview';
import Search from './pages/Search';
import Support from './pages/Support';
import KnowledgeManagementPage from './pages/KnowledgeManagementPage';

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
  const [auth, setAuth] = useState<{ isAuthenticated: boolean; user: any | null }>({ isAuthenticated: false, user: null });
  const [isLoading, setIsLoading] = useState(true);
  const { isOpen: isSessionExpiredModalOpen, onOpen: onSessionExpiredModalOpen, onClose: onSessionExpiredModalClose } = useDisclosure();
  const toast = useToast();
  const navigate = useNavigate();
  const { t } = useTranslation();

  // --- Setup Interceptors on Mount --- 
  useEffect(() => {
    setupInterceptors();
    // Log to confirm it ran inside App
    console.log('[App useEffect] Interceptors set up.');
  }, []); // Empty dependency array ensures this runs only once on mount

  // --- Modified handleLogout --- 
  const handleLogout = useCallback(async () => {
    console.log("[App] handleLogout CALLED! Attempting API logout...");
    try {
      await logoutApi(); // Call the backend endpoint to clear the cookie
      console.log("[App] API logout successful.");
    } catch (error) {
      console.error("[App] API logout failed:", error);
      // Proceed with frontend state clearing even if API fails
    }
    // Update auth state
    setAuth({ isAuthenticated: false, user: null });
    // Clear any potential MS refresh token (optional, depends on storage strategy)
    // localStorage.removeItem('refresh_token'); 
    navigate('/', { replace: true });
  }, [navigate]);

  // --- Session Expired Event Listener --- 
  useEffect(() => {
    const handleSessionExpired = () => {
      console.log("[App] Caught session-expired event.");
      // Ensure user state reflects logged out
      setAuth({ isAuthenticated: false, user: null });
      // Open the modal
      onSessionExpiredModalOpen();
    };

    window.addEventListener('session-expired', handleSessionExpired);

    // Cleanup listener on component unmount
    return () => {
      window.removeEventListener('session-expired', handleSessionExpired);
    };
  }, [onSessionExpiredModalOpen]);

  // --- Modified useEffect for Cookie-Based Auth Check --- 
  useEffect(() => {
    const initializeAuth = async () => {
      console.log("--- App useEffect running initializeAuth (Cookie Based) ---"); 
      setIsLoading(true);
      let userDetails = null;
      let initialAuth = false;

      try {
         console.log("Attempting to verify session with backend via /auth/me...");
         // If the cookie exists and is valid, this call will succeed
         userDetails = await getCurrentUser(); 
         console.log("Session verified. User details fetched:", userDetails);
         initialAuth = true;
         // Optionally store MS refresh token in memory if needed for later
         // NOTE: This needs careful consideration for security
         if (userDetails?.ms_token_data?.refresh_token) {
             console.log('[App] MS Refresh Token available from /me endpoint.');
             // sessionStorage.setItem('ms_refresh_token', userDetails.ms_token_data.refresh_token);
         } else {
             console.warn('[App] MS Refresh Token not found in /me response.');
         }

      } catch (error: any) {
         // If getCurrentUser fails (e.g., 401), the cookie is invalid/missing/expired
         console.log("Session verification failed (likely no valid cookie):", error?.response?.data || error.message);
         initialAuth = false;
         userDetails = null;
         // Don't need to call logout explicitly, state is already unauthenticated
      } finally {
         console.log(`Setting final state: isAuthenticated=${initialAuth}, user=${!!userDetails}`);
         setAuth({ isAuthenticated: initialAuth, user: userDetails });
         setIsLoading(false); 
         console.log("initializeAuth finished. Loading set to false.");
      }
    };

    initializeAuth();
    // Run only once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty dependency array

  // --- Handler for closing the session expired modal and redirecting ---
  const handleCloseSessionExpiredModal = () => {
    onSessionExpiredModalClose();
    navigate('/', { replace: true });
  };

  // --- Keep LoadingScreen check --- 
  if (isLoading) {
    return <LoadingScreen />;
  }

  // --- Update TopNavbar call to pass user --- 
  return (
    <Box minH="100vh">
      <TopNavbar 
        onLogout={handleLogout} 
        isAuthenticated={auth.isAuthenticated} 
        user={auth.user} // Pass user data down
      />
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
          
          {/* App Routes */}
          <Route path="/*" element={
            <Box flex="1">
              <Box p={4}>
                <Routes>
                   {/* Sign In Route - Render SignIn component regardless of auth for '/' */}
                   <Route
                      path="/"
                      element={
                          // Pass auth state to SignIn, let it decide what to display
                          <SignIn
                              onLogin={() => {
                                  console.log('[App] SignIn onLogin called (prop requirement).');
                                  setAuth({ isAuthenticated: true, user: null }); 
                              }}
                              isAuthenticated={auth.isAuthenticated} 
                          />
                      }
                  />
                  {/* Protected Routes */} 
                  {/* Pass user data to protected components if they need it */} 
                  <Route
                      path="/filter"
                      element={ auth.isAuthenticated ? <FilterSetup /> : <Navigate to="/" replace /> }
                  />
                   <Route
                      path="/review"
                      element={ auth.isAuthenticated ? <EmailReview /> : <Navigate to="/" replace /> }
                  />
                   <Route
                      path="/search"
                      element={ auth.isAuthenticated ? <Search /> : <Navigate to="/" replace /> }
                  />
                  <Route
                      path="/knowledge"
                      element={ auth.isAuthenticated ? <KnowledgeManagementPage /> : <Navigate to="/" replace /> }
                  />
                  <Route path="*" element={<Navigate to={auth.isAuthenticated ? "/filter" : "/"} replace />} />
                </Routes>
              </Box>
            </Box>
          } />
        </Routes>
      </Container>

      {/* Session Expired Modal */}
      <Modal isOpen={isSessionExpiredModalOpen} onClose={handleCloseSessionExpiredModal} isCentered>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('sessionExpired.title')}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text>{t('sessionExpired.message')}</Text>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" onClick={handleCloseSessionExpiredModal}>
              {t('sessionExpired.loginButton')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
}

export default App;
