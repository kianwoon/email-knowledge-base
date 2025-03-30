import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider, extendTheme } from '@chakra-ui/react';
import App from './App';

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
  styles: {
    global: {
      // Global styles applied to the whole app
      body: {
        bg: '#050a30',
        color: 'white',
      },
      // Styles for documentation pages
      '.documentation-text': {
        color: 'white !important',
      },
      '.card-text': {
        color: 'white !important',
      },
    },
  },
  components: {
    Text: {
      baseStyle: {
        color: 'white',
      },
    },
    Heading: {
      baseStyle: {
        color: 'white',
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ChakraProvider theme={theme}>
      <App />
    </ChakraProvider>
  </React.StrictMode>,
);
