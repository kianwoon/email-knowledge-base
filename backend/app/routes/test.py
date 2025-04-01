from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.config import settings

router = APIRouter()

# HTML content for the test page
TEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Microsoft Auth Test</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        pre {
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }
        button {
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px 0;
        }
        button:hover {
            background-color: #106ebe;
        }
        .log-container {
            margin-top: 20px;
            border: 1px solid #ddd;
            padding: 10px;
            border-radius: 5px;
            height: 300px;
            overflow-y: auto;
        }
        .env-info {
            background-color: #f8f8f8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <h1>Microsoft Auth Test Page</h1>
    
    <h2>Environment Information</h2>
    <div id="env-info" class="env-info"></div>
    
    <h2>Test Authentication</h2>
    <button id="test-login">Test Microsoft Login</button>
    <button id="test-api">Test API</button>
    <button id="clear-logs">Clear Logs</button>
    
    <h2>Console Logs</h2>
    <div class="log-container" id="log-output"></div>
    
    <script>
        // Override console.log to capture output
        const logOutput = document.getElementById('log-output');
        const originalConsoleLog = console.log;
        const originalConsoleError = console.error;
        
        console.log = function() {
            // Call original console.log
            originalConsoleLog.apply(console, arguments);
            
            // Add to our log display
            const args = Array.from(arguments);
            const message = args.map(arg => {
                if (typeof arg === 'object') {
                    return JSON.stringify(arg, null, 2);
                } else {
                    return String(arg);
                }
            }).join(' ');
            
            const logEntry = document.createElement('pre');
            logEntry.textContent = `LOG: ${message}`;
            logOutput.appendChild(logEntry);
            logOutput.scrollTop = logOutput.scrollHeight;
        };
        
        console.error = function() {
            // Call original console.error
            originalConsoleError.apply(console, arguments);
            
            // Add to our log display
            const args = Array.from(arguments);
            const message = args.map(arg => {
                if (typeof arg === 'object') {
                    return JSON.stringify(arg, null, 2);
                } else {
                    return String(arg);
                }
            }).join(' ');
            
            const logEntry = document.createElement('pre');
            logEntry.textContent = `ERROR: ${message}`;
            logEntry.style.color = 'red';
            logOutput.appendChild(logEntry);
            logOutput.scrollTop = logOutput.scrollHeight;
        };
        
        // Display environment information
        const envInfo = document.getElementById('env-info');
        const hostname = window.location.hostname;
        const isProduction = hostname !== 'localhost';
        
        envInfo.innerHTML = `
            <pre>
Hostname: ${hostname}
Is Production: ${isProduction}
Protocol: ${window.location.protocol}
Full URL: ${window.location.href}
            </pre>
        `;
        
        function log(message) {
            const logOutput = document.getElementById('log-output');
            const timestamp = new Date().toISOString();
            const logEntry = document.createElement('div');
            logEntry.innerHTML = `<span style="color:#888">[${timestamp}]</span> ${message}`;
            logOutput.appendChild(logEntry);
            logOutput.scrollTop = logOutput.scrollHeight;
            console.log(message);
        }
        
        function testApi() {
            log('Testing API connection...');
            
            // Show the current URL being used
            const apiUrl = window.location.origin + '/auth/login';
            log(`Making request to: ${apiUrl}`);
            
            fetch(apiUrl)
                .then(response => {
                    log(`Response status: ${response.status} ${response.statusText}`);
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    log('API response successful:');
                    log(JSON.stringify(data, null, 2));
                    
                    // Display the auth URL
                    if (data.auth_url) {
                        document.getElementById('auth-url').textContent = data.auth_url;
                    }
                })
                .catch(error => {
                    log(`Error testing API: ${error.message}`);
                    if (error.message.includes('Failed to fetch')) {
                        log('This may indicate a CORS issue or the server is not responding.');
                    }
                    console.error('API test error:', error);
                });
        }
        
        function testMicrosoftLogin() {
            log('Testing Microsoft login...');
            
            const apiUrl = window.location.origin + '/auth/login';
            log(`Getting login URL from: ${apiUrl}`);
            
            fetch(apiUrl)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.auth_url) {
                        log(`Redirecting to Microsoft login: ${data.auth_url}`);
                        // Store timestamp to track redirect
                        localStorage.setItem('ms_auth_test_time', Date.now());
                        // Redirect to Microsoft login
                        window.location.href = data.auth_url;
                    } else {
                        throw new Error('No auth_url in response');
                    }
                })
                .catch(error => {
                    log(`Error getting login URL: ${error.message}`);
                    console.error('Login error:', error);
                });
        }
        
        // Add event listeners
        document.getElementById('test-login').addEventListener('click', testMicrosoftLogin);
        document.getElementById('test-api').addEventListener('click', testApi);
        
        // Clear logs
        document.getElementById('clear-logs').addEventListener('click', function() {
            logOutput.innerHTML = '';
        });
    </script>
    <!-- ENV_PLACEHOLDER -->
</body>
</html>"""

@router.get("/auth-test", response_class=HTMLResponse)
async def auth_test_page(request: Request):
    """Serve the Microsoft authentication test page"""
    # Create HTML with environment variables injected
    html_with_env = TEST_PAGE_HTML.replace(
        "<!-- ENV_PLACEHOLDER -->",
        f"""
        <h3>Environment Variables:</h3>
        <pre>
BACKEND_URL: {settings.BACKEND_URL}
FRONTEND_URL: {settings.FRONTEND_URL}
MS_REDIRECT_URI: {settings.MS_REDIRECT_URI}
MS_CLIENT_ID: {settings.MS_CLIENT_ID[:5]}...{settings.MS_CLIENT_ID[-5:] if settings.MS_CLIENT_ID else 'Not set'}
MS_TENANT_ID: {settings.MS_TENANT_ID[:5]}...{settings.MS_TENANT_ID[-5:] if settings.MS_TENANT_ID else 'Not set'}
        </pre>
        """
    )
    return HTMLResponse(content=html_with_env)
