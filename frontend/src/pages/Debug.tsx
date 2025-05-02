import React, { useState, useEffect } from 'react';
import { getCurrentUser, getTokenDirectly } from '../api/auth';

const DebugPage: React.FC = () => {
  const [cookies, setCookies] = useState<string[]>([]);
  const [authStatus, setAuthStatus] = useState<string>('Checking...');
  const [manualToken, setManualToken] = useState<string>('');

  // Refresh cookies display
  const refreshCookies = () => {
    const cookieArr = document.cookie.split(';').map(cookie => cookie.trim());
    setCookies(cookieArr.length === 1 && cookieArr[0] === '' ? [] : cookieArr);
  };

  useEffect(() => {
    // Parse cookies
    refreshCookies();

    // Check auth status
    const checkAuth = async () => {
      try {
        const user = await getCurrentUser();
        if (user) {
          setAuthStatus(`Authenticated as: ${user.email}`);
        } else {
          setAuthStatus('Not authenticated (no user returned)');
        }
      } catch (error) {
        setAuthStatus(`Error checking auth: ${error instanceof Error ? error.message : String(error)}`);
      }
    };

    checkAuth();
  }, []);

  // Function to manually test the /me endpoint
  const testAuthEndpoint = async () => {
    try {
      console.log('Sending fetch request to /api/v1/auth/me with credentials=include');
      const response = await fetch('/api/v1/auth/me', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        }
      });
      
      console.log('Response headers:', response.headers);
      const contentType = response.headers.get('content-type');
      const isJson = contentType && contentType.includes('application/json');
      
      if (response.ok) {
        const data = isJson ? await response.json() : await response.text();
        console.log('Auth success:', data);
        alert(`Success! Status: ${response.status}\n\n${isJson ? JSON.stringify(data, null, 2) : data}`);
      } else {
        const error = isJson ? await response.json() : await response.text();
        console.error('Auth failed:', error);
        alert(`Failed! Status: ${response.status}\n\n${isJson ? JSON.stringify(error, null, 2) : error}`);
      }
    } catch (error) {
      console.error('Fetch error:', error);
      alert(`Error: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  // Function to manually test the login endpoint
  const testLoginEndpoint = async () => {
    try {
      console.log('Sending fetch request to /api/v1/auth/login');
      const response = await fetch('/api/v1/auth/login', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        }
      });
      
      const contentType = response.headers.get('content-type');
      const isJson = contentType && contentType.includes('application/json');
      
      if (response.ok) {
        const data = isJson ? await response.json() : await response.text();
        console.log('Login URL response:', data);
        
        if (data.auth_url) {
          if (confirm(`Do you want to redirect to: ${data.auth_url}?`)) {
            window.location.href = data.auth_url;
          }
        } else {
          alert(`Success but no auth_url found: ${JSON.stringify(data, null, 2)}`);
        }
      } else {
        const error = isJson ? await response.json() : await response.text();
        alert(`Failed! Status: ${response.status}\n\n${isJson ? JSON.stringify(error, null, 2) : error}`);
      }
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  // Function to manually set a token cookie
  const setManualTokenCookie = () => {
    if (!manualToken.trim()) {
      alert('Please enter a token first');
      return;
    }
    
    document.cookie = `access_token=${manualToken.trim()}; path=/; max-age=7200; SameSite=Lax`;
    console.log('Manually set cookie:', `access_token=${manualToken.trim().substring(0, 10)}...`);
    alert('Token cookie set!');
    refreshCookies();
  };

  // Function to get token directly
  const fetchTokenDirectly = async () => {
    try {
      const token = await getTokenDirectly();
      if (token) {
        alert('Successfully fetched and set token!');
        refreshCookies();
      } else {
        alert('Failed to fetch token. See console for details.');
      }
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Authentication Debug Page</h1>
      
      <div style={{ marginBottom: '20px' }}>
        <h2>Authentication Status</h2>
        <div style={{ 
          padding: '10px', 
          backgroundColor: authStatus.includes('Authenticated') ? '#d4edda' : '#f8d7da',
          borderRadius: '5px'
        }}>
          <strong>{authStatus}</strong>
        </div>
      </div>
      
      <div style={{ marginBottom: '20px' }}>
        <h2>Manual Token Input</h2>
        <div style={{ display: 'flex', marginBottom: '10px' }}>
          <input 
            type="text" 
            value={manualToken}
            onChange={(e) => setManualToken(e.target.value)}
            placeholder="Paste JWT token here"
            style={{ 
              flex: 1, 
              padding: '8px', 
              borderRadius: '4px 0 0 4px',
              border: '1px solid #ced4da',
              borderRight: 'none'
            }}
          />
          <button
            onClick={setManualTokenCookie}
            style={{
              padding: '8px 16px',
              backgroundColor: '#17a2b8',
              color: 'white',
              border: 'none',
              borderRadius: '0 4px 4px 0',
              cursor: 'pointer'
            }}
          >
            Set Cookie
          </button>
        </div>
        <button
          onClick={refreshCookies}
          style={{
            padding: '4px 8px',
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '12px'
          }}
        >
          Refresh Cookies
        </button>
      </div>
      
      <div style={{ marginBottom: '20px' }}>
        <h2>Cookies</h2>
        {cookies.length === 0 ? (
          <p>No cookies found</p>
        ) : (
          <ul>
            {cookies.map((cookie, index) => (
              <li key={index}>{cookie}</li>
            ))}
          </ul>
        )}
      </div>
      
      <div style={{ marginBottom: '20px' }}>
        <h2>Manual Tests</h2>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '10px' }}>
          <button 
            onClick={testAuthEndpoint}
            style={{
              padding: '8px 16px',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Test /auth/me Endpoint
          </button>
          <button 
            onClick={testLoginEndpoint}
            style={{
              padding: '8px 16px',
              backgroundColor: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Test Login Flow
          </button>
          <button 
            onClick={fetchTokenDirectly}
            style={{
              padding: '8px 16px',
              backgroundColor: '#17a2b8',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Fetch Token Directly
          </button>
        </div>
      </div>
      
      <div style={{ marginTop: '40px', fontSize: '14px' }}>
        <h3>Request Headers (Debug Info)</h3>
        <pre style={{ backgroundColor: '#f5f5f5', padding: '10px', borderRadius: '5px', overflow: 'auto' }}>
          {`
User-Agent: ${navigator.userAgent}
Cookie: ${document.cookie || '(none)'}
          `}
        </pre>
      </div>
    </div>
  );
};

export default DebugPage; 