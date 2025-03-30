import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider, extendTheme } from '@chakra-ui/react';
import App from './App';
import './i18n/i18n';
// We'll add these fonts later after fixing the basic functionality
// import '@fontsource/orbitron';
// import '@fontsource/inter';
// import '@fontsource/poppins';

// Define the type for color mode props
type ColorModeProps = {
  colorMode: 'light' | 'dark';
};

// Extend the theme to include custom colors, fonts, etc
const theme = extendTheme({
  config: {
    initialColorMode: 'dark',
    useSystemColorMode: true,
  },
  semanticTokens: {
    colors: {
      // Base colors
      "bg.primary": { 
        default: 'dark.bg', 
        _light: 'light.bg' 
      },
      "bg.secondary": { 
        default: 'dark.card', 
        _light: 'light.card' 
      },
      "bg.accent": { 
        default: 'rgba(62, 242, 242, 0.2)', 
        _light: 'rgba(10, 124, 255, 0.1)' 
      },
      "bg.warning": { 
        default: 'rgba(247, 37, 133, 0.2)', 
        _light: 'rgba(247, 37, 133, 0.1)' 
      },
      "bg.info": { 
        default: 'rgba(62, 242, 242, 0.2)', 
        _light: 'rgba(62, 242, 242, 0.1)' 
      },
      
      // Text colors
      "text.primary": { 
        default: 'dark.text', 
        _light: 'light.text' 
      },
      "text.secondary": { 
        default: 'dark.subtext', 
        _light: 'light.subtext' 
      },
      "text.muted": { 
        default: 'dark.muted', 
        _light: 'light.muted' 
      },
      "text.highlight": { 
        default: 'dark.highlight', 
        _light: 'light.highlight' 
      },
      
      // Border colors
      "border.primary": { 
        default: 'dark.border', 
        _light: 'light.border' 
      },
      "border.accent": { 
        default: 'rgba(62, 242, 242, 0.3)', 
        _light: 'rgba(10, 124, 255, 0.3)' 
      },
    }
  },
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
    },
    dark: {
      bg: '#050a30',
      card: 'rgba(255, 255, 255, 0.05)',
      text: 'white',
      subtext: 'rgba(255, 255, 255, 0.8)',
      muted: 'rgba(255, 255, 255, 0.6)',
      border: 'rgba(255, 255, 255, 0.15)',
      highlight: '#3ef2f2',
    },
    light: {
      bg: '#f7f9fc',
      card: 'white',
      text: '#1A202C', // Chakra's gray.800
      subtext: '#2D3748', // Chakra's gray.700
      muted: '#4A5568', // Chakra's gray.600
      border: '#E2E8F0', // Chakra's gray.200
      highlight: '#0062e3', // Primary.600
    }
  },
  fonts: {
    // Using system fonts for now to ensure it works
    heading: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    body: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
  },
  styles: {
    global: (props: ColorModeProps) => ({
      body: {
        bg: props.colorMode === 'dark' ? 'dark.bg' : 'light.bg',
        color: props.colorMode === 'dark' ? 'dark.text' : 'light.text',
      }
    })
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
        solid: (props: ColorModeProps) => ({
          bg: props.colorMode === 'dark' ? 'primary.500' : 'primary.600',
          color: 'white',
          _hover: {
            bg: props.colorMode === 'dark' ? 'primary.600' : 'primary.700',
          }
        }),
        neon: {
          bg: 'neon.blue',
          color: 'black',
          boxShadow: '0 0 12px #3ef2f2',
          _hover: {
            bg: 'neon.blue',
            boxShadow: '0 0 20px #3ef2f2',
          }
        },
        glass: (props: ColorModeProps) => ({
          bg: props.colorMode === 'dark' ? 'glass.bg' : 'white',
          backdropFilter: props.colorMode === 'dark' ? 'blur(10px)' : 'none',
          border: '1px solid',
          borderColor: props.colorMode === 'dark' ? 'glass.border' : 'light.border',
          color: props.colorMode === 'dark' ? 'white' : 'light.text',
          boxShadow: props.colorMode === 'light' ? 'md' : 'none',
          _hover: {
            bg: props.colorMode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'gray.50',
          }
        })
      }
    },
    Card: {
      baseStyle: (props: ColorModeProps) => ({
        container: {
          background: props.colorMode === 'dark' ? 'dark.card' : 'light.card',
          backdropFilter: props.colorMode === 'dark' ? 'blur(10px)' : 'none',
          border: '1px solid',
          borderColor: props.colorMode === 'dark' ? 'dark.border' : 'light.border',
          borderRadius: 'xl',
          boxShadow: props.colorMode === 'light' ? 'md' : '0 4px 30px rgba(0,0,0,0.1)',
        }
      })
    },
    Heading: {
      baseStyle: (props: ColorModeProps) => ({
        letterSpacing: '0.5px',
        color: props.colorMode === 'dark' ? 'dark.text' : 'light.text',
      })
    },
    Link: {
      baseStyle: (props: ColorModeProps) => ({
        color: props.colorMode === 'dark' ? 'dark.highlight' : 'light.highlight',
        _hover: {
          textDecoration: 'none',
          color: props.colorMode === 'dark' ? 'neon.blue' : 'primary.500',
        }
      })
    },
    Text: {
      baseStyle: (props: ColorModeProps) => ({
        color: props.colorMode === 'dark' ? 'dark.text' : 'light.text',
      }),
      variants: {
        muted: (props: ColorModeProps) => ({
          color: props.colorMode === 'dark' ? 'dark.muted' : 'light.muted',
          fontSize: 'sm',
        }),
        subtitle: (props: ColorModeProps) => ({
          color: props.colorMode === 'dark' ? 'dark.subtext' : 'light.subtext',
          fontSize: 'md',
        })
      }
    },
    Badge: {
      baseStyle: () => ({
        borderRadius: 'md',
        px: 2,
        py: 1,
        fontWeight: 'medium',
      }),
      variants: {
        solid: (props: ColorModeProps) => ({
          bg: props.colorMode === 'dark' ? 'dark.highlight' : 'light.highlight',
          color: props.colorMode === 'dark' ? 'black' : 'white',
        }),
        outline: (props: ColorModeProps) => ({
          borderColor: props.colorMode === 'dark' ? 'dark.highlight' : 'light.highlight',
          color: props.colorMode === 'dark' ? 'dark.highlight' : 'light.highlight',
        }),
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
