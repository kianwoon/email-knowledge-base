import React from 'react';
import {
  Box,
  Flex,
  Button,
  Heading,
  HStack,
  useColorMode,
  IconButton,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  VStack,
  useDisclosure,
  useBreakpointValue
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import { HamburgerIcon } from '@chakra-ui/icons';

const DocumentationHeader: React.FC = () => {
  const { colorMode } = useColorMode();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const isMobile = useBreakpointValue({ base: true, md: false });
  
  return (
    <Box 
      py={3} 
      px={{ base: 4, md: 8 }} 
      color="text.primary" 
      position="sticky" 
      top="0" 
      zIndex="sticky"
      bg={colorMode === 'dark' ? "bg.primary" : "white"}
      borderBottom="1px solid"
      borderColor={colorMode === 'dark' ? "whiteAlpha.200" : "gray.200"}
      boxShadow="sm"
    >
      <Flex maxW="1400px" mx="auto" justify="space-between" align="center">
        <Heading 
          size={{ base: "md", md: "lg" }} 
          fontWeight="bold" 
          as={RouterLink} 
          to="/" 
          _hover={{ textDecoration: 'none' }}
        >
          Email Knowledge Base
        </Heading>
        
        {isMobile ? (
          <>
            <IconButton
              aria-label="Open menu"
              icon={<HamburgerIcon />}
              onClick={onOpen}
              variant="outline"
              colorScheme={colorMode === 'dark' ? "whiteAlpha" : "blackAlpha"}
            />
            <Drawer isOpen={isOpen} placement="right" onClose={onClose}>
              <DrawerOverlay />
              <DrawerContent bg={colorMode === 'dark' ? "bg.primary" : "white"}>
                <DrawerCloseButton color="text.primary" />
                <DrawerHeader color="text.primary">Menu</DrawerHeader>
                <DrawerBody>
                  <VStack spacing={4} align="stretch">
                    <Button as={RouterLink} to="/#features" variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      Features
                    </Button>
                    <Button as={RouterLink} to="/docs" variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      Documentation
                    </Button>
                    <Button as={RouterLink} to="/support" variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      Support
                    </Button>
                  </VStack>
                </DrawerBody>
              </DrawerContent>
            </Drawer>
          </>
        ) : (
          <HStack spacing={4}>
            <Button as={RouterLink} to="/#features" variant="ghost" size="sm">Features</Button>
            <Button as={RouterLink} to="/docs" variant="ghost" size="sm">Documentation</Button>
            <Button as={RouterLink} to="/support" variant="ghost" size="sm">Support</Button>
          </HStack>
        )}
      </Flex>
    </Box>
  );
};

export default DocumentationHeader;
