import React, { useState, useEffect, useCallback, lazy } from 'react';
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
import TokenUsagePage from './pages/TokenUsagePage'; // <<< Import TokenUsagePage
import AITraining from './pages/documentation/AITraining'; // <-- Import Doc Page
import AIAnalysis from './pages/documentation/AIAnalysis'; // <-- Import
import Documentation from './pages/documentation/Documentation'; // <-- Import
import KnowledgeBase from './pages/documentation/KnowledgeBase'; // <-- Import
import SecureAuthentication from './pages/documentation/SecureAuthentication'; // <-- Import
import SmartFiltering from './pages/documentation/SmartFiltering'; // <-- Import
// Import the new SharePoint page
import SharePointPage from './pages/SharePoint';
import S3Browser from '@/pages/S3Browser'; // <<< RE-ADDED S3 Browser import
import S3ConfigurationPage from '@/pages/S3ConfigurationPage'; // <<< Added S3 Config Page import
// Remove the old Azure Blob page import
// import AzureBlobPage from './pages/AzureBlob'; 
// Import the new Azure Blob browser component
import AzureBlobBrowser from './pages/DataSource/AzureBlob/AzureBlobBrowser';
// import EmailProcessing from './pages/documentation/EmailProcessing'; // <-- Comment out or remove this line

// MUI Theme imports for wrapping AzureBlobBrowser - NO LONGER NEEDED
// import { ThemeProvider as MuiThemeProvider, createTheme as createMuiTheme } from '@mui/material/styles';

// i18n
import { useTranslation } from 'react-i18next';

// Lazy load new page components
const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const KnowledgeBaseListPage = lazy(() => import('@/pages/KnowledgeBaseListPage'));
const KnowledgeBaseDetailPage = lazy(() => import('@/pages/KnowledgeBaseDetailPage'));
const BackgroundTasksPage = lazy(() => import('@/pages/BackgroundTasksPage'));
const JarvisPage = lazy(() => import('@/pages/JarvisPage'));

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

// Define protected paths
const protectedPaths = [
  '/filter',
  '/review',
  '/search',
  '/knowledge',
  '/tokens',
  '/token-usage', // <<< Add Token Usage path
  '/jarvis',
  '/sharepoint', // Added SharePoint
  '/s3', // <<< RE-ADDED S3 path
  '/settings/s3', // <<< Added S3 Settings path
  '/azure-blob', // <<< Added Azure Blob path
  // Add other protected paths like dashboard, knowledge-bases, etc.
  '/dashboard',
  '/knowledge-bases',
  '/tasks',
];

// Create a default MUI theme instance - NO LONGER NEEDED
// const defaultMuiTheme = createMuiTheme();

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
      const authUrl = await getLoginUrl(); // Returns string directly
      console.log("Login URL response:", authUrl);
      // --- CORRECTED USAGE ---
      if (authUrl) { // Check if the string URL is truthy
        // Redirect to Microsoft login page
        console.log("Redirecting to auth URL:", authUrl);
        window.location.href = authUrl; // Use the string directly
      } else {
        throw new Error('Failed to get login URL from backend (empty string received)'); // More specific error
      }
      // --- END CORRECTION ---
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
      // Note: setIsLoading(true) is redundant here as initial state is true
      // setIsLoading(true); 
      let userDetails = null;
      let initialAuth = false;
      try {
         console.log("[initializeAuth] Attempting getCurrentUser...");
         userDetails = await getCurrentUser();
         console.log("[initializeAuth] getCurrentUser success. User:", userDetails);
         initialAuth = !!userDetails;
      } catch (error: any) {
         // This includes 401 errors where getCurrentUser returns null
         console.log("[initializeAuth] getCurrentUser failed or returned null (session likely invalid):", error?.response?.data || error?.message);
         initialAuth = false;
         userDetails = null;
      } finally {
         console.log(`[initializeAuth] Setting final auth state: isAuthenticated=${initialAuth}, user=${!!userDetails}`);
         setAuth({ isAuthenticated: initialAuth, user: userDetails });
         console.log("[initializeAuth] >>> Calling setIsLoading(false) NOW.");
         setIsLoading(false);
         console.log("[initializeAuth] <<< setIsLoading(false) CALLED.");
         console.log("--- initializeAuth finished. ---");
      }
    };
    initializeAuth();
  }, []); // Empty dependency array ensures this runs only once on mount

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

  const handleLogin = async () => {
    console.log('handleLogin called');
    try {
      const authUrl = await getLoginUrl(); // Returns string directly
      // --- CORRECTED USAGE ---
      if (authUrl) { // Check if the string URL is truthy
        console.log('Redirecting to MS login:', authUrl);
        window.location.href = authUrl; // Use the string directly
      } else {
        // This case should ideally not happen if getLoginUrl throws an error on failure
        console.error('Login failed: Empty Auth URL received from backend.');
      }
      // --- END CORRECTION ---
    } catch (error) {
      console.error('Login error:', error);
      // Handle error appropriately
    }
  };

  // <<< ADD Log before the loading check >>>
  console.log(`[App Render] isLoading state is currently: ${isLoading}`);

  // Loading Screen (Restored)
  if (isLoading) {
    console.log("[App Render] Rendering LoadingScreen because isLoading is true.");
    return <LoadingScreen />;
  }

  // Main App Structure (Restored)
  console.log("[App Render] Rendering main App structure because isLoading is false.");
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
          <Route
            path="/token-usage"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <TokenUsagePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jarvis"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <React.Suspense fallback={<LoadingScreen />}>
                  <JarvisPage />
                </React.Suspense>
              </ProtectedRoute>
            }
          />
          {/* --- SharePoint Route --- */}
          <Route
            path="/sharepoint"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <SharePointPage />
              </ProtectedRoute>
            }
          />
          {/* --- End SharePoint Route --- */}
          {/* --- Start S3 Browser Route --- RE-ADDED */}
          <Route
            path="/s3"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <S3Browser />
              </ProtectedRoute>
            }
          />
          {/* --- End S3 Browser Route --- */}
          {/* --- Start S3 Configuration Route --- */}
          <Route
            path="/settings/s3"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <S3ConfigurationPage />
              </ProtectedRoute>
            }
          />
          {/* --- End S3 Configuration Route --- */}
          {/* --- Start Azure Blob Route --- */}
          <Route
            path="/azure-blob"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                 {/* Wrap AzureBlobBrowser with MUI ThemeProvider - REMOVED */}
                 {/* <MuiThemeProvider theme={defaultMuiTheme}> */}
                   <AzureBlobBrowser />
                 {/* </MuiThemeProvider> */}
              </ProtectedRoute>
            }
          />
          {/* --- End Azure Blob Route --- */}

          {/* Add routes for lazy-loaded pages */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <React.Suspense fallback={<LoadingScreen />}>
                  <DashboardPage />
                </React.Suspense>
              </ProtectedRoute>
            }
          />
          <Route
            path="/knowledge-bases"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <React.Suspense fallback={<LoadingScreen />}>
                  <KnowledgeBaseListPage />
                </React.Suspense>
              </ProtectedRoute>
            }
          />
          <Route
            path="/knowledge-bases/:id"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <React.Suspense fallback={<LoadingScreen />}>
                  <KnowledgeBaseDetailPage />
                </React.Suspense>
              </ProtectedRoute>
            }
          />
          <Route
            path="/tasks"
            element={
              <ProtectedRoute isAuthenticated={auth.isAuthenticated} onOpenLoginModal={onSessionExpiredModalOpen}>
                <React.Suspense fallback={<LoadingScreen />}>
                  <BackgroundTasksPage />
                </React.Suspense>
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
