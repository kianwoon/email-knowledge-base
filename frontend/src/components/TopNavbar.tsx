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
  useBreakpointValue,
  Spacer
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
import { SunIcon, MoonIcon, HamburgerIcon, ChevronDownIcon } from '@chakra-ui/icons';
import { FaFilter, FaClipboardCheck, FaSearch, FaSignOutAlt, FaBook, FaUsers, FaGlobe, FaHome, FaMicrosoft, FaBoxes, FaDatabase, FaShareSquare, FaConfluence, FaServer, FaGoogleDrive, FaAws, FaBrain, FaKey, FaRobot, FaShareAltSquare, FaEnvelopeOpenText, FaChartBar, FaUsersCog } from 'react-icons/fa';
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

  // Updated navigation items structure
  const navItems = [
    { path: '/', label: t('navigation.home'), icon: FaHome },
    {
      label: t('navigation.dataSource'),
      icon: FaDatabase,
      children: [
        { path: '/filter', label: t('navigation.filterEmails'), icon: FaFilter },
        { path: '/outlook-sync', label: t('navigation.outlookSync'), icon: FaEnvelopeOpenText },
        { path: '/sharepoint', label: t('navigation.sharepoint'), icon: FaShareSquare },
        { path: '/s3', label: t('navigation.awsS3'), icon: FaAws, disabled: false },
        { path: '/azure-blob', label: t('navigation.azureBlob'), icon: FaMicrosoft, disabled: false },
        { path: '#confluence', label: t('navigation.confluence'), icon: FaConfluence, disabled: true },
        { path: '#elastic', label: t('navigation.elasticsearch'), icon: FaServer, disabled: true },
        { path: '#gdrive', label: t('navigation.googleDrive'), icon: FaGoogleDrive, disabled: true },
      ]
    },
    { path: '/review', label: t('navigation.review'), icon: FaClipboardCheck },
    { path: '/search', label: t('navigation.search'), icon: FaSearch },
    // New AI Data Management Menu
    {
      label: t('navigation.aiDataManagement'),
      icon: FaBrain,
      children: [
        { path: '/knowledge', label: t('navigation.knowledgeManagement'), icon: FaBoxes },
        { path: '/tokens', label: t('navigation.tokenManagement'), icon: FaKey },
        { path: '/jarvis', label: t('navigation.jarvis'), icon: FaRobot },
        { path: '/token-usage', label: t('navigation.tokenUsage'), icon: FaChartBar, disabled: false },
        { path: '/autogen', label: t('navigation.agenticAI'), icon: FaUsersCog, disabled: false }
      ]
    },
    { path: '/docs', label: t('navigation.documentation'), icon: FaBook },
  ];

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  // Check if language is Chinese (use 'cn')
  const isChinese = i18n.language === 'cn' || i18n.language.startsWith('zh');

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
      const authUrl = await getLoginUrl(); // Returns string directly
      
      console.log("Login URL response:", authUrl);
      
      if (authUrl) { // Check if the string URL is truthy
        // Redirect to Microsoft login page
        console.log("Redirecting to auth URL:", authUrl);
        window.location.href = authUrl; // Use the string directly
      } else {
        // This case should ideally not happen if getLoginUrl throws an error on failure
        console.error("Failed to get login URL (empty string received).");
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
      <Container maxW="1400px" py={2} px={{ base: 4, md: 8 }}>
        <Flex align="center" justify="space-evenly" display={{ base: 'none', md: 'flex' }}>
          <Box
            as={RouterLink}
            to="/"
            _hover={{ opacity: 0.8 }}
            display="flex"
            alignItems="center"
          >
            <img src="/NLOGO.svg" alt={t('app.name')} style={{ height: '32px' }} />
          </Box>

          {navItems.map((item) => (
            item.children ? (
              <Menu key={item.label}>
                <MenuButton
                  as={Button}
                  variant="ghost"
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                  leftIcon={<Icon as={item.icon} />}
                  rightIcon={<ChevronDownIcon />}
                  size="md"
                  fontWeight="medium"
                  px={4}
                  color={useColorModeValue('gray.800', 'whiteAlpha.900')}
                >
                  {item.label}
                </MenuButton>
                <MenuList bg={useColorModeValue('white', 'gray.800')} borderColor={useColorModeValue('gray.200', 'whiteAlpha.300')}>
                  {item.children.map((child) => {
                    const linkProps = !child.disabled ? { to: child.path } : {};
                    return (
                      <MenuItem
                        key={child.path}
                        as={child.disabled ? 'button' : RouterLink}
                        {...linkProps}
                        icon={<Icon as={child.icon} />}
                        isDisabled={child.disabled}
                        onClick={child.disabled ? (e) => e.preventDefault() : undefined}
                        _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                      >
                        {child.label}
                      </MenuItem>
                    );
                  })}
                </MenuList>
              </Menu>
            ) : (
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
            )
          ))}

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
              {isChinese ? '中文' : t('language.english')}
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
                中文
              </MenuItem>
            </MenuList>
          </Menu>

          <IconButton
            aria-label={t('common.toggleColorMode')}
            icon={colorMode === 'dark' ? <SunIcon /> : <MoonIcon />}
            onClick={toggleColorMode}
            variant="ghost"
            _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
            color={useColorModeValue('gray.800', 'whiteAlpha.900')}
          />

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
        </Flex>

        <Flex display={{ base: 'flex', md: 'none' }} justify="space-between" align="center">
          <Box
            as={RouterLink}
            to="/"
            _hover={{ opacity: 0.8 }}
            display="flex"
            alignItems="center"
          >
            <img src="/NLOGO.svg" alt={t('app.name')} style={{ height: '32px' }} />
          </Box>
          <Spacer />
          <HStack spacing={1}>
            <Menu>
              <MenuButton
                as={IconButton}
                icon={<Icon as={FaGlobe} />}
                variant="ghost"
                size="sm"
              />
              <MenuList bg={useColorModeValue('white', 'gray.800')} borderColor={useColorModeValue('gray.200', 'whiteAlpha.300')}>
                <MenuItem onClick={() => changeLanguage('en')}>{t('language.english')}</MenuItem>
                <MenuItem onClick={() => changeLanguage('cn')}>中文</MenuItem>
              </MenuList>
            </Menu>
            <IconButton
              aria-label={t('common.toggleColorMode')}
              icon={colorMode === 'dark' ? <SunIcon /> : <MoonIcon />}
              onClick={toggleColorMode}
              variant="ghost"
              size="sm"
            />
            {isAuthenticated ? (
              <UserMenu />
            ) : (
              <Button
                leftIcon={<Icon as={FaMicrosoft} />}
                onClick={handleSignIn}
                size="sm"
                colorScheme="cyan"
                px={2}
              >
                {t('home.cta.signIn')}
              </Button>
            )}
            <IconButton
              onClick={onDrawerOpen}
              icon={<HamburgerIcon />}
              aria-label={t('common.openMenu')}
              variant="ghost"
              size="sm"
            />
          </HStack>
        </Flex>
      </Container>

      <Drawer isOpen={isDrawerOpen} placement="right" onClose={onDrawerClose}>
        <DrawerOverlay />
        <DrawerContent bg="bg.primary">
          <DrawerCloseButton />
          <DrawerHeader borderBottomWidth="1px" borderColor="border.primary">{t('common.menu')}</DrawerHeader>
          <DrawerBody>
            <VStack spacing={2} align="stretch">
              {navItems.map((item) => (
                item.children ? (
                  <React.Fragment key={item.label}>
                    <Text fontWeight="bold" mt={4} mb={2} px={4} color="gray.500">{item.label}</Text>
                    {item.children.map((child) => {
                      const linkProps = !child.disabled ? { to: child.path } : {};
                      return (
                        <Button
                          key={child.path}
                          as={child.disabled ? 'button' : RouterLink}
                          {...linkProps}
                          variant="ghost"
                          w="full"
                          justifyContent="start"
                          leftIcon={<Icon as={child.icon} />}
                          isDisabled={child.disabled}
                          onClick={() => {
                            if (!child.disabled) onDrawerClose();
                          }}
                        >
                          {child.label}
                        </Button>
                      );
                    })}
                  </React.Fragment>
                ) : (
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
                )
              ))}
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Box>
  );
};

export default TopNavbar; 