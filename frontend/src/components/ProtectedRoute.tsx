import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

interface ProtectedRouteProps {
  isAuthenticated: boolean;
  onOpenLoginModal: () => void;
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  isAuthenticated, 
  onOpenLoginModal, 
  children 
}) => {
  const location = useLocation();

  useEffect(() => {
    if (!isAuthenticated) {
      console.log(`[ProtectedRoute] User not authenticated trying to access ${location.pathname}. Opening login modal.`);
      // Open the modal passed down from App.tsx
      onOpenLoginModal(); 
    }
  }, [isAuthenticated, onOpenLoginModal, location.pathname]); // Rerun check if auth status or path changes

  // Render children if authenticated, otherwise render null (modal will handle UI)
  return isAuthenticated ? <>{children}</> : null;
};

export default ProtectedRoute; 