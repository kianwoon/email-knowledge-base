import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Box, Flex } from '@chakra-ui/react';

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

// Components
import Navbar from './components/Navbar';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  // Check for token on load
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      // In a real app, we would validate the token here
      setIsAuthenticated(true);
    }
    
    // Check for token in URL (from OAuth redirect)
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('token');
    const expires = urlParams.get('expires');
    
    if (urlToken && expires) {
      localStorage.setItem('token', urlToken);
      localStorage.setItem('expires', expires);
      setIsAuthenticated(true);
      
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);
  
  // Handle logout
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('expires');
    setIsAuthenticated(false);
  };
  
  return (
    <Router>
      <Flex direction="column" minH="100vh">
        {isAuthenticated && <Navbar onLogout={handleLogout} />}
        
        <Routes>
          {/* Documentation Routes - accessible without authentication and no padding */}
          <Route path="/docs" element={<Documentation />} />
          <Route path="/docs/secure-authentication" element={<SecureAuthentication />} />
          <Route path="/docs/smart-filtering" element={<SmartFiltering />} />
          <Route path="/docs/ai-analysis" element={<AIAnalysis />} />
          <Route path="/docs/knowledge-base" element={<KnowledgeBase />} />
          <Route path="/support" element={<Support />} />
          
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
