import React from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  Stack,
  HStack,
  Link as ChakraLink,
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

const Footer: React.FC = () => {
  return (
    <Box py={12} px={8} color="whiteAlpha.800" position="relative" zIndex="1">
      <Container maxW="1400px">
        <Stack direction={{ base: 'column', md: 'row' }} justify="space-between" align="center">
          <HStack align={{ base: 'center', md: 'flex-start' }} spacing={2}>
            <Heading size="md" color="white">Email Knowledge Base</Heading>
            <Text fontSize="sm">© 2025 Email Knowledge Base. All rights reserved.</Text>
          </HStack>
          
          <HStack spacing={6} mt={{ base: 4, md: 0 }}>
            <ChakraLink as={RouterLink} to="/docs" _hover={{ color: 'neon.blue' }}>Documentation</ChakraLink>
            <ChakraLink as={RouterLink} to="/support" _hover={{ color: 'neon.blue' }}>Support</ChakraLink>
            <ChakraLink href="#" _hover={{ color: 'neon.blue' }}>Privacy Policy</ChakraLink>
            <ChakraLink href="#" _hover={{ color: 'neon.blue' }}>Terms of Service</ChakraLink>
          </HStack>
        </Stack>
      </Container>
    </Box>
  );
};

export default Footer;
