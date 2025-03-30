import React from 'react';
import {
  Box,
  Flex,
  Button,
  Heading,
  HStack,
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

const DocumentationHeader: React.FC = () => {
  return (
    <Box 
      py={4} 
      px={8} 
      color="white" 
      position="relative" 
      zIndex="1"
      bgGradient="linear(to-r, neon.dark, neon.purple, neon.pink)"
    >
      <Flex maxW="1400px" mx="auto" justify="space-between" align="center">
        <Heading size="lg" fontWeight="bold" as={RouterLink} to="/" _hover={{ textDecoration: 'none' }}>
          Email Knowledge Base
        </Heading>
        <HStack spacing={4}>
          <Button as={RouterLink} to="/#features" variant="glass" size="sm">Features</Button>
          <Button as={RouterLink} to="/docs" variant="glass" size="sm">Documentation</Button>
          <Button as={RouterLink} to="/support" variant="glass" size="sm">Support</Button>
        </HStack>
      </Flex>
    </Box>
  );
};

export default DocumentationHeader;
