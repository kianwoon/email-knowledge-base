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
  useBreakpointValue,
  Text
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import { HamburgerIcon, MoonIcon, SunIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from './LanguageSwitcher';

const DocumentationHeader: React.FC = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const isMobile = useBreakpointValue({ base: true, md: false });
  const { t } = useTranslation();
  
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
          {t('app.name')}
        </Heading>
        
        {isMobile ? (
          <>
            <HStack spacing={2}>
              <LanguageSwitcher />
              <IconButton
                aria-label="Toggle color mode"
                icon={colorMode === 'light' ? <MoonIcon /> : <SunIcon />}
                onClick={toggleColorMode}
                variant="ghost"
                color="text.primary"
                size="sm"
              />
              <IconButton
                aria-label="Open menu"
                icon={<HamburgerIcon />}
                onClick={onOpen}
                variant="outline"
                color="text.primary"
              />
            </HStack>
            <Drawer isOpen={isOpen} placement="right" onClose={onClose}>
              <DrawerOverlay />
              <DrawerContent bg={colorMode === 'dark' ? "bg.primary" : "white"}>
                <DrawerCloseButton color="text.primary" />
                <DrawerHeader color="text.primary">{t('navigation.menu')}</DrawerHeader>
                <DrawerBody>
                  <VStack spacing={4} align="stretch">
                    <Button as={RouterLink} to="/#features" variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      {t('navigation.features')}
                    </Button>
                    <Button as={RouterLink} to="/docs" variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      {t('navigation.documentation')}
                    </Button>
                    <Button as={RouterLink} to="/support" variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      {t('navigation.support')}
                    </Button>
                    <Flex align="center" justify="space-between" w="full" pt={2} mt={2} borderTop="1px solid" borderColor={colorMode === 'dark' ? "whiteAlpha.300" : "gray.200"}>
                      <Text fontSize="sm">{t('navigation.toggleTheme')}</Text>
                      <IconButton
                        aria-label="Toggle color mode"
                        icon={colorMode === 'light' ? <MoonIcon /> : <SunIcon />}
                        onClick={toggleColorMode}
                        variant="ghost"
                        color="text.primary"
                        size="md"
                      />
                    </Flex>
                  </VStack>
                </DrawerBody>
              </DrawerContent>
            </Drawer>
          </>
        ) : (
          <HStack spacing={4}>
            <Button as={RouterLink} to="/#features" variant="ghost" size="sm">{t('navigation.features')}</Button>
            <Button as={RouterLink} to="/docs" variant="ghost" size="sm">{t('navigation.documentation')}</Button>
            <Button as={RouterLink} to="/support" variant="ghost" size="sm">{t('navigation.support')}</Button>
            <LanguageSwitcher />
            <IconButton
              aria-label="Toggle color mode"
              icon={colorMode === 'light' ? <MoonIcon /> : <SunIcon />}
              onClick={toggleColorMode}
              variant="ghost"
              color="text.primary"
              size="sm"
            />
          </HStack>
        )}
      </Flex>
    </Box>
  );
};

export default DocumentationHeader;
