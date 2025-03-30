import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider, extendTheme } from '@chakra-ui/react';
import App from './App';
// We'll add these fonts later after fixing the basic functionality
// import '@fontsource/orbitron';
// import '@fontsource/inter';
// import '@fontsource/poppins';

// Extend the theme to include custom colors, fonts, etc
const theme = extendTheme({
  colors: {
    brand: {
      50: '#e6f3ff',
      100: '#bddcff',
      200: '#90c5ff',
      300: '#61adff',
      400: '#3495ff',
      500: '#0a7cff',
      600: '#0062e3',
      700: '#0049b3',
      800: '#003380',
      900: '#001c4d',
    },
    primary: {
      50: '#e6f3ff',
      100: '#bddcff',
      200: '#90c5ff',
      300: '#61adff',
      400: '#3495ff',
      500: '#0a7cff',
      600: '#0062e3',
      700: '#0049b3',
      800: '#003380',
      900: '#001c4d',
    },
    neon: {
      blue: '#3ef2f2',
      purple: '#7209b7',
      pink: '#f72585',
      dark: '#3a0ca3',
    },
    glass: {
      bg: 'rgba(255, 255, 255, 0.05)',
      border: 'rgba(255, 255, 255, 0.15)',
    }
  },
  fonts: {
    // Using system fonts for now to ensure it works
    heading: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    body: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
  },
  config: {
    initialColorMode: 'light',
    useSystemColorMode: false,
  },
  styles: {
    global: {
      body: {
        bg: '#050a30',
        color: 'white',
      }
    }
  },
  components: {
    Button: {
      baseStyle: {
        fontWeight: 'medium',
        borderRadius: 'md',
        letterSpacing: '0.5px',
        transition: 'transform 0.2s ease',
        _hover: {
          transform: 'scale(1.05)',
        }
      },
      variants: {
        solid: {
          bg: 'primary.600',
          color: 'white',
          _hover: {
            bg: 'primary.700',
          }
        },
        neon: {
          bg: 'neon.blue',
          color: 'black',
          boxShadow: '0 0 12px #3ef2f2',
          _hover: {
            bg: 'neon.blue',
            boxShadow: '0 0 20px #3ef2f2',
          }
        },
        glass: {
          bg: 'glass.bg',
          backdropFilter: 'blur(10px)',
          border: '1px solid',
          borderColor: 'glass.border',
          color: 'white',
          _hover: {
            bg: 'rgba(255, 255, 255, 0.1)',
          }
        }
      }
    },
    Card: {
      baseStyle: {
        container: {
          background: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: 'xl',
          boxShadow: '0 4px 30px rgba(0,0,0,0.1)',
        }
      }
    },
    Heading: {
      baseStyle: {
        letterSpacing: '0.5px',
      }
    },
    Link: {
      baseStyle: {
        _hover: {
          textDecoration: 'none',
        }
      }
    }
  }
});

const root = document.getElementById('root');

if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <ChakraProvider theme={theme}>
        <App />
      </ChakraProvider>
    </React.StrictMode>
  );
}
