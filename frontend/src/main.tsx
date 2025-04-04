import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider, extendTheme } from '@chakra-ui/react';
import App from './App';
import i18n from './i18n/i18n'; // Import the configured i18n instance
import { I18nextProvider } from 'react-i18next'; // Import the provider
import './index.css';
import { setupResponseInterceptor } from './api/interceptors'; // Import the setup function

// Define gradient colors for reuse
const gradientColors = {
  dark: {
    primary: {
      start: '#3ef2f2',
      end: '#f72585'
    },
    secondary: {
      start: '#7209b7',
      end: '#3ef2f2'
    },
    banner: {
      start: 'rgba(62, 242, 242, 0.2)',
      end: 'transparent'
    }
  },
  light: {
    primary: {
      start: '#0078D4',
      end: '#9941D8'
    },
    secondary: {
      start: '#9941D8',
      end: '#0078D4'
    },
    banner: {
      start: 'rgba(0, 120, 212, 0.1)',
      end: 'transparent'
    }
  }
};

// Extend the theme to include custom colors, fonts, etc
const theme = extendTheme({
  colors: {
    brand: {
      50: '#e6f6ff',
      100: '#bae3ff',
      200: '#7cc4fa',
      300: '#47a3f3',
      400: '#2186eb',
      500: '#0967d2',
      600: '#0552b5',
      700: '#03449e',
      800: '#01337d',
      900: '#002159',
    },
    neon: {
      blue: '#3ef2f2',
      pink: '#f72585',
      purple: '#7209b7',
      dark: '#050a30',
    },
  },
  fonts: {
    heading: '"Inter", sans-serif',
    body: '"Inter", sans-serif',
  },
  config: {
    initialColorMode: 'dark',
    useSystemColorMode: false,
  },
  semanticTokens: {
    colors: {
      "bg.primary": { 
        _dark: '#050a30', 
        _light: 'white' 
      },
      "bg.secondary": { 
        _dark: 'rgba(255, 255, 255, 0.05)', 
        _light: 'white' 
      },
      "bg.accent": { 
        _dark: 'rgba(62, 242, 242, 0.15)', 
        _light: 'rgba(0, 181, 216, 0.1)' 
      },
      "bg.hover": {
        _dark: 'rgba(255, 255, 255, 0.08)',
        _light: 'gray.50'
      },
      "bg.highlight": {
        _dark: '#7B2CBF',
        _light: '#00B5D8'
      },
      "bg.info": { 
        _dark: 'rgba(62, 242, 242, 0.1)', 
        _light: 'blue.50' 
      },
      "bg.warning": { 
        _dark: 'rgba(247, 37, 133, 0.1)', 
        _light: 'yellow.50' 
      },
      "bg.success": { 
        _dark: 'rgba(0, 200, 81, 0.1)', 
        _light: 'green.50' 
      },
      "text.primary": { 
        _dark: 'white', 
        _light: 'gray.800' 
      },
      "text.secondary": { 
        _dark: 'whiteAlpha.800', 
        _light: 'gray.600' 
      },
      "text.highlight": { 
        _dark: 'neon.blue', 
        _light: 'blue.500' 
      },
      "text.inverted": {
        _dark: 'white',
        _light: 'white'
      },
      "border.primary": { 
        _dark: 'rgba(255, 255, 255, 0.1)', 
        _light: 'rgba(0, 0, 0, 0.1)' 
      },
      "gradient.start.primary": {
        _dark: gradientColors.dark.primary.start,
        _light: gradientColors.light.primary.start
      },
      "gradient.end.primary": {
        _dark: gradientColors.dark.primary.end,
        _light: gradientColors.light.primary.end
      },
      "gradient.start.secondary": {
        _dark: gradientColors.dark.secondary.start,
        _light: gradientColors.light.secondary.start
      },
      "gradient.end.secondary": {
        _dark: gradientColors.dark.secondary.end,
        _light: gradientColors.light.secondary.end
      },
      "gradient.bg.start": {
        _dark: gradientColors.dark.banner.start,
        _light: gradientColors.light.banner.start
      },
      "gradient.bg.end": {
        _dark: gradientColors.dark.banner.end,
        _light: gradientColors.light.banner.end
      }
    },
    gradients: {
      "heading.primary": {
        _dark: `linear(to-r, ${gradientColors.dark.primary.start}, ${gradientColors.dark.primary.end})`,
        _light: `linear(to-r, ${gradientColors.light.primary.start}, ${gradientColors.light.primary.end})`
      },
      "heading.secondary": {
        _dark: `linear(to-r, ${gradientColors.dark.secondary.start}, ${gradientColors.dark.secondary.end})`,
        _light: `linear(to-r, ${gradientColors.light.secondary.start}, ${gradientColors.light.secondary.end})`
      },
      "banner.background": {
        _dark: `linear(to-b, ${gradientColors.dark.banner.start}, ${gradientColors.dark.banner.end})`,
        _light: `linear(to-b, ${gradientColors.light.banner.start}, ${gradientColors.light.banner.end})`
      }
    }
  },
  styles: {
    global: (props: { colorMode: 'light' | 'dark' }) => ({
      // Global styles applied to the whole app
      body: {
        bg: props.colorMode === 'dark' ? '#050a30' : 'white',
        color: props.colorMode === 'dark' ? 'white' : 'gray.800',
      },
      // Styles for documentation pages
      '.documentation-text': {
        color: props.colorMode === 'dark' ? 'white !important' : 'gray.800 !important',
      },
      '.card-text': {
        color: props.colorMode === 'dark' ? 'white !important' : 'gray.800 !important',
      },
    }),
  },
  components: {
    Text: {
      baseStyle: (props: { colorMode: 'light' | 'dark' }) => ({
        color: props.colorMode === 'dark' ? 'white' : 'gray.800',
      }),
    },
    Heading: {
      baseStyle: (props: { colorMode: 'light' | 'dark' }) => ({
        color: props.colorMode === 'dark' ? 'white' : 'gray.800',
        // Add this to ensure gradient text is visible when using bgClip="text"
        '.chakra-heading[style*="background-clip: text"]': {
          color: 'transparent !important',
        }
      }),
    },
  },
});

// Setup the response interceptor
setupResponseInterceptor();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nextProvider i18n={i18n}>
      <ChakraProvider theme={theme}>
        <App />
      </ChakraProvider>
    </I18nextProvider>
  </React.StrictMode>,
);
