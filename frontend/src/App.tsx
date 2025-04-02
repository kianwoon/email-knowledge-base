import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Box, Flex, Spinner } from '@chakra-ui/react';

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
import Navbar from './components/Navbar';
import DocumentationHeader from './components/DocumentationHeader';

// Documentation Layout Component
const DocumentationLayout = ({ children }: { children: React.ReactNode }) => {
  return (
    <>
      <DocumentationHeader />
      {children}
    </>
  );
};

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  
  // Check for token on load
  useEffect(() => {
    const checkAuth = async () => {
      try {
        setIsLoading(true);
        const token = localStorage.getItem('token');
        const expires = localStorage.getItem('expires');
        
        if (!token || !expires) {
          setIsAuthenticated(false);
          return;
        }

        // Check if token is expired
        const expiryDate = new Date(expires);
        if (expiryDate <= new Date()) {
          // Token is expired
          localStorage.removeItem('token');
          localStorage.removeItem('expires');
          setIsAuthenticated(false);
          return;
        }
        
        setIsAuthenticated(true);
      } catch (error) {
        console.error('Auth check error:', error);
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };
    
    // Check for token in URL (from OAuth redirect)
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('token');
    const expires = urlParams.get('expires');
    
    if (urlToken && expires) {
      localStorage.setItem('token', urlToken);
      localStorage.setItem('expires', expires);
      setIsAuthenticated(true);
      setIsLoading(false);
      
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else {
      checkAuth();
    }
  }, []);
  
  // Handle logout
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('expires');
    setIsAuthenticated(false);
  };
  
  if (isLoading) {
    return (
      <Box height="100vh" display="flex" alignItems="center" justifyContent="center">
        <Spinner size="xl" />
      </Box>
    );
  }

  return (
    <Router>
      <Flex direction="column" minH="100vh">
        {isAuthenticated && <Navbar onLogout={handleLogout} />}
        
        <Routes>
          {/* Documentation Routes - accessible without authentication and with DocumentationHeader */}
          <Route path="/docs" element={<DocumentationLayout><Documentation /></DocumentationLayout>} />
          <Route path="/docs/secure-authentication" element={<DocumentationLayout><SecureAuthentication /></DocumentationLayout>} />
          <Route path="/docs/features/security" element={<DocumentationLayout><SecureAuthentication /></DocumentationLayout>} />
          <Route path="/docs/smart-filtering" element={<DocumentationLayout><SmartFiltering /></DocumentationLayout>} />
          <Route path="/docs/ai-analysis" element={<DocumentationLayout><AIAnalysis /></DocumentationLayout>} />
          <Route path="/docs/knowledge-base" element={<DocumentationLayout><KnowledgeBase /></DocumentationLayout>} />
          <Route path="/docs/features/knowledge-extraction" element={<DocumentationLayout><KnowledgeBase /></DocumentationLayout>} />
          <Route path="/docs/features/knowledge-base" element={<DocumentationLayout><KnowledgeBase /></DocumentationLayout>} />
          <Route path="/docs/email-processing" element={<DocumentationLayout><SmartFiltering /></DocumentationLayout>} />
          <Route path="/docs/ai-training" element={<DocumentationLayout><AITraining /></DocumentationLayout>} />
          <Route path="/docs/features/ai-training" element={<DocumentationLayout><AITraining /></DocumentationLayout>} />
          <Route path="/support" element={<DocumentationLayout><Support /></DocumentationLayout>} />
          
          {/* App Routes - with padding and authentication */}
          <Route path="/*" element={
            <Box flex="1" p={4}>
              <Routes>
                <Route 
                  path="/" 
                  element={isAuthenticated ? <Navigate to="/filter" /> : <SignIn onLogin={() => setIsAuthenticated(true)} />} 
                />
                <Route 
                  path="/filter" 
                  element={isAuthenticated ? <FilterSetup /> : <Navigate to="/" />} 
                />
                <Route 
                  path="/review" 
                  element={isAuthenticated ? <EmailReview /> : <Navigate to="/" />} 
                />
                <Route 
                  path="/search" 
                  element={isAuthenticated ? <Search /> : <Navigate to="/" />} 
                />
              </Routes>
            </Box>
          } />
        </Routes>
      </Flex>
    </Router>
  );
}

export default App;
