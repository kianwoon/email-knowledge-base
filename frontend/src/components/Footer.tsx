import React from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  Stack,
  VStack,
  Link as ChakraLink,
  useColorMode
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

const Footer: React.FC = () => {
  const { colorMode } = useColorMode();
  
  return (
    <Box 
      py={{ base: 8, md: 12 }} 
      px={{ base: 4, md: 8 }} 
      color="text.secondary" 
      position="relative" 
      zIndex="1"
      bg="bg.primary"
      borderTop="1px solid"
      borderColor="border.primary"
    >
      <Container maxW="1400px">
        <Stack 
          direction={{ base: 'column', md: 'row' }} 
          justify="space-between" 
          align={{ base: 'center', md: 'flex-start' }}
          spacing={{ base: 6, md: 0 }}
        >
          <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2}>
            <Heading size={{ base: "sm", md: "md" }} color="text.primary">Email Knowledge Base</Heading>
            <Text fontSize="sm" textAlign={{ base: 'center', md: 'left' }}> 2025 Email Knowledge Base. All rights reserved.</Text>
          </VStack>
          
          <VStack spacing={{ base: 4, md: 6 }} align={{ base: 'center', md: 'flex-end' }}>
            <Stack 
              direction={{ base: 'column', sm: 'row' }} 
              spacing={{ base: 3, md: 6 }}
              align="center"
              flexWrap="wrap"
              justify={{ base: 'center', md: 'flex-end' }}
            >
              <ChakraLink as={RouterLink} to="/docs" color="text.primary" _hover={{ color: colorMode === 'dark' ? "neon.blue" : "brand.600" }}>Documentation</ChakraLink>
              <ChakraLink as={RouterLink} to="/support" color="text.primary" _hover={{ color: colorMode === 'dark' ? "neon.blue" : "brand.600" }}>Support</ChakraLink>
              <ChakraLink href="#" color="text.primary" _hover={{ color: colorMode === 'dark' ? "neon.blue" : "brand.600" }}>Privacy Policy</ChakraLink>
              <ChakraLink href="#" color="text.primary" _hover={{ color: colorMode === 'dark' ? "neon.blue" : "brand.600" }}>Terms of Service</ChakraLink>
            </Stack>
          </VStack>
        </Stack>
      </Container>
    </Box>
  );
};

export default Footer;
