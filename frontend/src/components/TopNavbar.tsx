import React, { useState, useEffect } from 'react';
import {
  Box,
  Flex,
  Button,
  Heading,
  useColorMode,
  IconButton,
  HStack,
  Container,
  Avatar,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
  useDisclosure,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  VStack,
  Icon,
  Text,
  Spinner,
  useColorModeValue,
  useBreakpointValue
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
import { SunIcon, MoonIcon, HamburgerIcon, ChevronDownIcon } from '@chakra-ui/icons';
import { FaFilter, FaClipboardCheck, FaSearch, FaSignOutAlt, FaBook, FaUsers, FaGlobe, FaHome, FaMicrosoft } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { getLoginUrl } from '../api/auth';

// Define user interface
interface UserInfo {
  id: string;
  email: string;
  display_name: string;
  photo_url?: string;
  organization?: string;
}

interface TopNavbarProps {
  onLogout?: () => void;
  isAuthenticated?: boolean;
  user?: UserInfo | null;
}

const TopNavbar = ({ onLogout, isAuthenticated, user }: TopNavbarProps): JSX.Element => {
  const { colorMode, toggleColorMode } = useColorMode();
  const location = useLocation();
  const { isOpen: isDrawerOpen, onOpen: onDrawerOpen, onClose: onDrawerClose } = useDisclosure();
  const { t, i18n } = useTranslation();
  const isMobile = useBreakpointValue({ base: true, md: false });
  const navigate = useNavigate();

  // Define navigation items
  const navItems = [
    { path: '/', label: t('navigation.home'), icon: FaHome },
    { path: '/filter', label: t('navigation.filterEmails'), icon: FaFilter },
    { path: '/review', label: t('navigation.review'), icon: FaClipboardCheck },
    { path: '/search', label: t('navigation.search'), icon: FaSearch },
    { path: '/docs', label: t('navigation.documentation'), icon: FaBook },
  ];

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  // Check if language is Chinese (either zh or cn)
  const isChinese = i18n.language === 'zh' || i18n.language === 'cn';

  // User menu component
  const UserMenu = () => {
    if (!user) return <Spinner size="sm" />;

    return (
      <Menu>
        <MenuButton
          as={Button}
          variant="ghost"
          _hover={{ bg: "bg.hover" }}
          padding={2}
        >
          <HStack spacing={2}>
            <Avatar
              size="sm"
              name={user.display_name}
              src={user.photo_url}
            />
            <Text display={{ base: 'none', md: 'block' }}>
              {user.display_name}
            </Text>
            <ChevronDownIcon />
          </HStack>
        </MenuButton>
        <MenuList bg={useColorModeValue('white', 'gray.800')} borderColor={useColorModeValue('gray.200', 'whiteAlpha.300')}>
          <MenuItem
            icon={<FaUsers />}
            onClick={() => {}}
            _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
          >
            {t('userMenu.account')}
          </MenuItem>
          <MenuDivider />
          <MenuItem
            icon={<FaSignOutAlt />}
            onClick={onLogout}
            _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
          >
            {t('userMenu.signOut')}
          </MenuItem>
        </MenuList>
      </Menu>
    );
  };

  const handleSignIn = async () => {
    try {
      // Get the Microsoft login URL from our backend
      console.log("Attempting to get login URL from backend...");
      const response = await getLoginUrl();
      
      console.log("Login URL response:", response);
      
      if (response && response.auth_url) {
        // Redirect to Microsoft login page
        console.log("Redirecting to auth URL:", response.auth_url);
        window.location.href = response.auth_url;
      } else {
        throw new Error('Failed to get login URL');
      }
    } catch (error) {
      console.error('Login error:', error);
      // You can add toast notification here if needed
    }
  };

  return (
    <Box
      as="nav"
      bg="bg.primary"
      color="text.primary"
      boxShadow="md"
      position="sticky"
      top="0"
      zIndex="sticky"
    >
      <Container maxW="1400px" py={2}>
        <Flex justify="space-between" align="center">
          {/* Logo and Brand */}
          <Flex align="center">
            <Box
              as={RouterLink}
              to="/"
              _hover={{ opacity: 0.8 }}
              mr={8}
              display="flex"
              alignItems="center"
            >
              <img src="/NLOGO.svg" alt={t('app.name')} style={{ height: '32px' }} />
            </Box>

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
                variant="ghost"
                leftIcon={<Icon as={FaGlobe} />}
                _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                size="md"
                px={2}
                color={useColorModeValue('gray.800', 'whiteAlpha.900')}
              >
                {isChinese ? t('language.chinese') : t('language.english')}
              </MenuButton>
              <MenuList bg={useColorModeValue('white', 'gray.800')} borderColor={useColorModeValue('gray.200', 'whiteAlpha.300')}>
                <MenuItem
                  onClick={() => changeLanguage('en')}
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                >
                  {t('language.english')}
                </MenuItem>
                <MenuItem
                  onClick={() => changeLanguage('cn')}
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                >
                  {t('language.chinese')}
                </MenuItem>
              </MenuList>
            </Menu>

            {/* Color Mode Toggle */}
            <IconButton
              aria-label={t('common.toggleColorMode')}
              icon={colorMode === 'dark' ? <SunIcon /> : <MoonIcon />}
              onClick={toggleColorMode}
              variant="ghost"
              _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
              color={useColorModeValue('gray.800', 'whiteAlpha.900')}
            />

            {/* User Menu or Sign In Button */}
            {isAuthenticated ? (
              <UserMenu />
            ) : (
              <Button
                leftIcon={<Icon as={FaMicrosoft} />}
                onClick={handleSignIn}
                size="md"
                colorScheme="cyan"
                bg={useColorModeValue('cyan.400', 'cyan.500')}
                color="white"
                _hover={{
                  bg: useColorModeValue('cyan.500', 'cyan.600'),
                }}
              >
                {t('home.cta.signIn')}
              </Button>
            )}

            {/* Mobile Menu Button */}
            <IconButton
              display={{ base: 'flex', md: 'none' }}
              onClick={onDrawerOpen}
              icon={<HamburgerIcon />}
              aria-label={t('common.openMenu')}
              variant="ghost"
            />
          </HStack>
        </Flex>
      </Container>

      {/* Mobile Drawer */}
      <Drawer isOpen={isDrawerOpen} placement="right" onClose={onDrawerClose}>
        <DrawerOverlay />
        <DrawerContent bg="bg.primary">
          <DrawerCloseButton />
          <DrawerHeader borderBottomWidth="1px" borderColor="border.primary">{t('common.menu')}</DrawerHeader>
          <DrawerBody>
            <VStack spacing={4} align="stretch">
              {navItems.map((item) => (
                <Button
                  key={item.path}
                  as={RouterLink}
                  to={item.path}
                  variant="ghost"
                  w="full"
                  justifyContent="start"
                  leftIcon={<Icon as={item.icon} />}
                  onClick={onDrawerClose}
                >
                  {item.label}
                </Button>
              ))}
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Box>
  );
};

export default TopNavbar; 