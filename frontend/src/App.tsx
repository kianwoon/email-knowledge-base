import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import {
  Box, Container, Spinner, Center, Text, useToast, useDisclosure, 
  VStack, Modal, ModalOverlay, ModalContent, ModalHeader, ModalFooter, ModalBody, ModalCloseButton, Button 
} from '@chakra-ui/react';

// Context & Auth
// Assuming context provides these, or adjust imports if needed
// import { AuthProvider, AuthConsumer, useAuth } from './context/AuthContext'; 

// API
import { getCurrentUser, logout as logoutApi, getLoginUrl } from './api/auth';
import { setupInterceptors } from './api/apiClient';

// Components
import TopNavbar from './components/TopNavbar';
import ProtectedRoute from './components/ProtectedRoute';
// Removed: import LoadingScreen from './components/LoadingScreen';
// Removed: import SessionExpiredModal from './components/SessionExpiredModal'; 

// Pages (Using actual filenames)
import SignIn from './pages/SignIn'; // Assuming this acts as home/login
// Removed: import AuthCallback from './pages/AuthCallback'; // Assuming handled within SignIn or separate logic
import FilterSetup from './pages/FilterSetup';
import EmailReview from './pages/EmailReview'; // Corrected name
import Search from './pages/Search'; // Corrected name
// Removed: import DocumentationPage from './pages/DocumentationPage'; // No such file
import Support from './pages/Support'; // Corrected name
// Removed: import NotFoundPage from './pages/NotFoundPage'; // Use catch-all redirect instead
import KnowledgeManagementPage from '@/pages/KnowledgeManagementPage'; 
import TokenManagementPage from './pages/TokenManagementPage'; 
import AITraining from './pages/documentation/AITraining'; // <-- Import Doc Page
import AIAnalysis from './pages/documentation/AIAnalysis'; // <-- Import 
import Documentation from './pages/documentation/Documentation'; // <-- Import 
import KnowledgeBase from './pages/documentation/KnowledgeBase'; // <-- Import 
import SecureAuthentication from './pages/documentation/SecureAuthentication'; // <-- Import 
import SmartFiltering from './pages/documentation/SmartFiltering'; // <-- Import 
// import EmailProcessing from './pages/documentation/EmailProcessing'; // <-- Comment out or remove this line

// i18n
import { useTranslation } from 'react-i18next';

// Loading Component (Re-defined inline for simplicity)
const LoadingScreen = () => (
  <Center height="100vh">
    <VStack spacing={4}>
      <Spinner size="xl" thickness="4px" speed="0.65s" />
      <Text>Loading your profile...</Text>
    </VStack>
  </Center>
);

// Session Modal Component (Re-defined inline - adjust content/styling as needed)
const SessionExpiredModalInline = ({ isOpen, onClose, onLogin, t }: any) => (
  <Modal isOpen={isOpen} onClose={onClose} isCentered>
    <ModalOverlay />
    <ModalContent>
      <ModalHeader>{t('sessionExpired.title')}</ModalHeader>
      <ModalCloseButton />
      <ModalBody>
        <Text>{t('sessionExpired.message')}</Text>
      </ModalBody>
      <ModalFooter>
        <Button colorScheme="blue" onClick={onLogin}> {/* Use onLogin prop */} 
          {t('sessionExpired.loginButton')}
        </Button>
      </ModalFooter>
    </ModalContent>
  </Modal>
);

// Define protected paths (Re-add this)
const protectedPaths = [
  '/filter',
  '/review',
  '/search',
  '/knowledge',
  '/tokens',
];

function App() {
  // State management (Restored from previous correct version)
  const [auth, setAuth] = useState<{ isAuthenticated: boolean; user: any | null }>({ isAuthenticated: false, user: null });
  const [isLoading, setIsLoading] = useState(true);
  const { isOpen: isSessionExpiredModalOpen, onOpen: onSessionExpiredModalOpen, onClose: onSessionExpiredModalClose } = useDisclosure();
  const toast = useToast();
  const navigate = useNavigate();
  const { t } = useTranslation();

  // Setup Interceptors (Restored)
  useEffect(() => {
    setupInterceptors();
    console.log('[App useEffect] Interceptors set up.');
  }, []); 

  // --- Login Redirect Handler ---
  const redirectToLogin = useCallback(async () => {
    console.log("[App] redirectToLogin CALLED!");
    // Close the modal first if it's open
    onSessionExpiredModalClose();
    try {
      // Get the Microsoft login URL from our backend
      console.log("Attempting to get login URL from backend...");
      const response = await getLoginUrl();
      console.log("Login URL response:", response);
      if (response && response.auth_url) {
        // Redirect to Microsoft login page
        console.log("Redirecting to auth URL:", response.auth_url);
        window.location.href = response.auth_url;
      } else {
        throw new Error('Failed to get login URL from backend');
      }
    } catch (error) {
      console.error('Login redirection error:', error);
      toast({
        title: t('errors.loginRedirectFailed.title'),
        description: t('errors.loginRedirectFailed.description'),
        status: "error",
        duration: 5000,
        isClosable: true,
      });
      // Optionally navigate to root as a fallback
      // navigate('/', { replace: true });
    }
  }, [onSessionExpiredModalClose, t, toast]); // Dependencies: onClose, t, toast
  // --- End Login Redirect Handler ---

  // Logout Handler (Restored)
  const handleLogout = useCallback(async () => {
    console.log("[App] handleLogout CALLED! Attempting API logout...");
    try {
      await logoutApi();
      console.log("[App] API logout successful.");
    } catch (error) {
      console.error("[App] API logout failed:", error);
    }
    setAuth({ isAuthenticated: false, user: null });
    localStorage.removeItem('refresh_token');
    navigate('/', { replace: true });
  }, [navigate]);

  // Modified session expired handler - Reinstate path check
  useEffect(() => {
    const handleSessionExpired = () => {
      const currentPath = window.location.pathname;
      console.log(`[App] Caught session-expired event (likely 401) on path: ${currentPath}`);

      // Check if the current path starts with any of the protected paths
      const isProtectedPath = protectedPaths.some(path => currentPath.startsWith(path));

      if (isProtectedPath) {
        console.log("[App] Session expired on a protected path. Forcing logout and showing modal.");
        setAuth({ isAuthenticated: false, user: null });
        localStorage.removeItem('refresh_token');
        onSessionExpiredModalOpen(); // Open the modal
      } else {
        console.log("[App] Session expired on a public path or during background fetch. Ignoring for modal.");
        // Do nothing visually disruptive on public pages
      }
    };
    window.addEventListener('session-expired', handleSessionExpired);
    return () => {
      window.removeEventListener('session-expired', handleSessionExpired);
    };
  }, [onSessionExpiredModalOpen]); // Keep dependency

  // Auth Initialization Check (Restored)
  useEffect(() => {
    const initializeAuth = async () => {
      console.log("--- App useEffect running initializeAuth (Cookie Based) ---"); 
      setIsLoading(true);
      let userDetails = null;
      let initialAuth = false;
      try {
         console.log("Attempting to verify session with backend via /auth/me...");
         userDetails = await getCurrentUser(); 
         console.log("Session verified. User details fetched:", userDetails);
         initialAuth = true;
         if (userDetails?.ms_token_data?.refresh_token) {
             console.log('[App] MS Refresh Token available from /me endpoint. Storing in localStorage.');
             localStorage.setItem('refresh_token', userDetails.ms_token_data.refresh_token);
         } else {
             console.warn('[App] MS Refresh Token not found in /me response.');
         }
      } catch (error: any) {
         console.log("Session verification failed (likely no valid cookie):", error?.response?.data || error.message);
         initialAuth = false;
         userDetails = null;
         localStorage.removeItem('refresh_token');
      } finally {
         console.log(`Setting final state: isAuthenticated=${initialAuth}, user=${!!userDetails}`);
         setAuth({ isAuthenticated: initialAuth, user: userDetails });
         setIsLoading(false); 
         console.log("initializeAuth finished. Loading set to false.");
      }
    };
    initializeAuth();
  }, []);

  // Close Session Modal Handler (Restored)
  const handleCloseSessionExpiredModal = () => {
    onSessionExpiredModalClose();
    navigate('/', { replace: true }); 
  };

  // Function to update auth state (takes no args now)
  const handleSuccessfulLogin = useCallback(() => {
     // Refetch user data after login redirect
     // This might be redundant if initializeAuth runs on mount/navigation
     console.log("handleSuccessfulLogin called - potentially refetch user data?");
     // initializeAuth(); // Re-running this might cause issues, handle carefully
     // For now, simply update the state based on redirect handling in SignIn.tsx
     setAuth(prev => ({ ...prev, isAuthenticated: true })); // Assume SignIn redirect handles user details
  }, []);

  // Loading Screen (Restored)
  if (isLoading) {
    return <LoadingScreen />;
  }

  // Main App Structure (Restored)
  return (
    // Assuming Router is handled outside this component if needed
    <Box minH="100vh">
      <TopNavbar 
        onLogout={handleLogout} 
        isAuthenticated={auth.isAuthenticated} 
        user={auth.user}
      />
      <Container maxW="1400px" py={4}>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<SignIn onLogin={handleSuccessfulLogin} isAuthenticated={auth.isAuthenticated} />} />
          <Route path="/support" element={<Support />} />
          <Route path="/docs" element={<Documentation />} /> {/* Main docs page */}
          <Route path="/docs/ai-training" element={<AITraining />} /> 
          <Route path="/docs/ai-analysis" element={<AIAnalysis />} /> 
          <Route path="/docs/knowledge-base" element={<KnowledgeBase />} /> 
          <Route path="/docs/secure-authentication" element={<SecureAuthentication />} /> 
          <Route path="/docs/smart-filtering" element={<SmartFiltering />} /> 
          {/* Add route for Email Processing doc if it exists */}
          {/* <Route path="/docs/email-processing" element={<EmailProcessing />} /> */} {/* <-- Comment out or remove this line */}

          {/* Protected Routes - Use ProtectedRoute Component */}
          <Route 
            path="/filter" 
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <FilterSetup />
              </ProtectedRoute>
            }
          />
          <Route 
            path="/review" 
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <EmailReview />
              </ProtectedRoute>
            }
          />
          <Route 
            path="/search" 
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <Search />
              </ProtectedRoute>
            }
          />
          <Route 
            path="/knowledge" 
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <KnowledgeManagementPage />
              </ProtectedRoute>
            }
          />
          <Route 
            path="/tokens" 
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <TokenManagementPage />
              </ProtectedRoute>
            }
          />
          
          {/* Catch-all Route - Added back */}
          <Route path="*" element={<Navigate to={auth.isAuthenticated ? "/filter" : "/"} replace />} />
        </Routes>
      </Container>

      {/* Session Expired Modal - Stays the same, triggered by onSessionExpiredModalOpen */}
      <SessionExpiredModalInline
        isOpen={isSessionExpiredModalOpen}
        onClose={handleCloseSessionExpiredModal}
        onLogin={redirectToLogin} // Login button in modal redirects
        t={t}
      />
    </Box>
  );
}

// Removed AppWrapper and Router nesting
// const AppWrapper = () => (
//   <Router>
//     <App />
//   </Router>
// );

export default App; // Export App directly
