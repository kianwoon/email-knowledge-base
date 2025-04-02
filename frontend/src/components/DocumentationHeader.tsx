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
  Container,
  useColorModeValue,
  Icon,
  Menu,
  MenuButton,
  MenuList,
  MenuItem
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { HamburgerIcon, MoonIcon, SunIcon, ChevronDownIcon } from '@chakra-ui/icons';
import { FaFilter, FaClipboardCheck, FaSearch, FaBook, FaGlobe, FaHome } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';

const DocumentationHeader: React.FC = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const isMobile = useBreakpointValue({ base: true, md: false });
  const location = useLocation();
  const { t, i18n } = useTranslation();
  
  // Define navigation items
  const navItems = [
    { path: '/', label: 'Home', icon: FaHome },
    { path: '/filter', label: 'Filter Emails', icon: FaFilter },
    { path: '/review', label: 'Review', icon: FaClipboardCheck },
    { path: '/search', label: 'Search', icon: FaSearch },
    { path: '/docs', label: 'Documentation', icon: FaBook },
  ];

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };
  
  return (
    <Box 
      as="nav"
      bg="bg.primary" 
      color="text.primary" 
      position="sticky" 
      top="0" 
      zIndex="sticky"
      boxShadow="md"
    >
      <Container maxW="1400px" py={2}>
        <Flex justify="space-between" align="center">
          {/* Logo and Brand */}
          <Flex align="center">
            <Heading 
              size="md" 
              fontWeight="bold" 
              as={RouterLink} 
              to="/" 
              _hover={{ textDecoration: 'none' }}
              color={useColorModeValue('gray.800', 'whiteAlpha.900')}
              mr={8}
            >
              Email Knowledge Base
            </Heading>
            
            {/* Desktop Navigation */}
            <HStack spacing={1} display={{ base: 'none', md: 'flex' }}>
              {navItems.map((item) => (
                <Button
                  key={item.path}
                  as={RouterLink}
                  to={item.path}
                  variant="ghost"
                  isActive={location.pathname === item.path || location.pathname.startsWith(item.path + '/')}
                  _active={{ bg: "blue.500", color: "white" }}
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                  leftIcon={<Icon as={item.icon} />}
                  size="md"
                  fontWeight="medium"
                  px={4}
                  color={useColorModeValue('gray.800', 'whiteAlpha.900')}
                >
                  {item.label}
                </Button>
              ))}
            </HStack>
          </Flex>
          
          {/* Right side controls */}
          <HStack spacing={2}>
            {/* Language Switcher */}
            <Menu>
              <MenuButton
                as={Button}
                aria-label="Change language"
                leftIcon={<Icon as={FaGlobe} />}
                variant="ghost"
                _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                size="md"
                px={2}
                color={useColorModeValue('gray.800', 'whiteAlpha.900')}
              >
                {i18n.language === 'zh' ? 'CN' : 'EN'}
              </MenuButton>
              <MenuList bg={useColorModeValue('white', 'gray.800')} borderColor={useColorModeValue('gray.200', 'whiteAlpha.300')}>
                <MenuItem
                  onClick={() => changeLanguage('en')}
                  bg={i18n.language === 'en' ? useColorModeValue('blue.50', 'blue.900') : undefined}
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                  color={useColorModeValue('gray.800', 'whiteAlpha.900')}
                >
                  English
                </MenuItem>
                <MenuItem
                  onClick={() => changeLanguage('zh')}
                  bg={i18n.language === 'zh' ? useColorModeValue('blue.50', 'blue.900') : undefined}
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                  color={useColorModeValue('gray.800', 'whiteAlpha.900')}
                >
                  中文
                </MenuItem>
              </MenuList>
            </Menu>

            <IconButton
              aria-label="Toggle color mode"
              icon={colorMode === 'light' ? <MoonIcon /> : <SunIcon />}
              onClick={toggleColorMode}
              variant="ghost"
              colorScheme="whiteAlpha"
              _hover={{ bg: "bg.hover" }}
              color="text.primary"
            />
            
            {/* Mobile menu button */}
            <IconButton
              display={{ base: 'flex', md: 'none' }}
              aria-label="Open menu"
              icon={<HamburgerIcon />}
              onClick={onOpen}
              variant="ghost"
              colorScheme="whiteAlpha"
              _hover={{ bg: "bg.hover" }}
            />
          </HStack>

          {/* Mobile Menu Drawer */}
          <Drawer isOpen={isOpen} placement="right" onClose={onClose}>
            <DrawerOverlay />
            <DrawerContent bg={useColorModeValue('white', 'gray.800')}>
              <DrawerCloseButton color="text.primary" />
              <DrawerHeader color="text.primary">{t('navigation.menu')}</DrawerHeader>
              <DrawerBody>
                <VStack spacing={4} align="stretch">
                  {navItems.map((item) => (
                    <Button
                      key={item.path}
                      as={RouterLink}
                      to={item.path}
                      variant="ghost"
                      w="full"
                      justifyContent="flex-start"
                      onClick={onClose}
                      leftIcon={<Icon as={item.icon} />}
                      isActive={location.pathname === item.path || location.pathname.startsWith(item.path + '/')}
                      _active={{ bg: "blue.500", color: "white" }}
                      _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                      color={useColorModeValue('gray.800', 'whiteAlpha.900')}
                      fontWeight="medium"
                    >
                      {item.label}
                    </Button>
                  ))}
                </VStack>
              </DrawerBody>
            </DrawerContent>
          </Drawer>
        </Flex>
      </Container>
    </Box>
  );
};

export default DocumentationHeader;
