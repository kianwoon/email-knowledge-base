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
  useColorModeValue
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { SunIcon, MoonIcon, HamburgerIcon, ChevronDownIcon, SettingsIcon } from '@chakra-ui/icons';
import { FaFilter, FaClipboardCheck, FaSearch, FaSignOutAlt, FaBook, FaUsers, FaGlobe } from 'react-icons/fa';
import { getCurrentUser } from '../api/auth';
import { useTranslation } from 'react-i18next';

// Define user interface
interface UserInfo {
  id: string;
  email: string;
  display_name: string;
  photo_url?: string;
  organization?: string;
}

interface NavbarProps {
  onLogout: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ onLogout }) => {
  const { colorMode, toggleColorMode } = useColorMode();
  const location = useLocation();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { t, i18n } = useTranslation();
  
  // Fetch user information when component mounts
  useEffect(() => {
    const fetchUserInfo = async () => {
      try {
        setIsLoading(true);
        const userData = await getCurrentUser();
        setUser(userData);
      } catch (error) {
        console.error('Error fetching user info:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchUserInfo();
  }, []);
  
  // Define navigation items
  const navItems = [
    { path: '/filter', label: 'Filter Emails', icon: FaFilter },
    { path: '/review', label: 'Review', icon: FaClipboardCheck },
    { path: '/search', label: 'Search', icon: FaSearch },
    { path: '/docs', label: 'Documentation', icon: FaBook },
  ];
  
  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  return (
    <Box as="nav" bg="bg.primary" color="text.primary" boxShadow="md" position="sticky" top="0" zIndex="sticky">
      <Container maxW="1400px" py={2}>
        <Flex justify="space-between" align="center">
          {/* Logo and Brand */}
          <Flex align="center">
            <Heading size="md" fontWeight="bold" mr={8}>
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
            
            {/* User menu */}
            <Menu>
              <MenuButton
                as={Button}
                variant="ghost"
                colorScheme="whiteAlpha"
                _hover={{ bg: "bg.hover" }}
                rightIcon={<ChevronDownIcon />}
              >
                <HStack>
                  {isLoading ? (
                    <Spinner size="sm" color="text.primary" />
                  ) : (
                    <Avatar 
                      size="sm" 
                      name={user?.display_name || "User"} 
                      src={user?.photo_url} 
                      bg="bg.accent" 
                    />
                  )}
                  <Text display={{ base: 'none', md: 'block' }}>
                    {user?.display_name || "Demo User"}
                  </Text>
                </HStack>
              </MenuButton>
              <MenuList bg={useColorModeValue('white', 'gray.800')} borderColor={useColorModeValue('gray.200', 'whiteAlpha.300')} p={0} minWidth="320px">
                {/* User profile header */}
                <Box p={4} borderBottomWidth="1px" borderColor={useColorModeValue('gray.200', 'whiteAlpha.200')}>
                  <Flex>
                    <Avatar 
                      size="md" 
                      name={user?.display_name || "User"} 
                      src={user?.photo_url} 
                      bg={useColorModeValue('blue.500', 'blue.400')} 
                      mr={3} 
                    />
                    <Box>
                      <Text fontWeight="bold" color={useColorModeValue('gray.800', 'white')}>{user?.display_name || "Demo User"}</Text>
                      <Text fontSize="sm" color={useColorModeValue('gray.600', 'whiteAlpha.800')}>{user?.email || "user@example.com"}</Text>
                      <HStack mt={2} spacing={2}>
                        <Button size="xs" variant="outline" colorScheme="blue">View account</Button>
                        <Button size="xs" variant="outline" colorScheme="blue">Switch directory</Button>
                      </HStack>
                    </Box>
                  </Flex>
                </Box>
                
                {/* Organization section */}
                {user?.organization && (
                  <Box p={3} borderBottomWidth="1px" borderColor={useColorModeValue('gray.200', 'whiteAlpha.200')}>
                    <Flex align="center">
                      <Avatar 
                        size="sm" 
                        icon={<Icon as={FaUsers} fontSize="1.2rem" color={useColorModeValue('white', 'gray.800')} />} 
                        bg={useColorModeValue('blue.500', 'blue.400')} 
                        mr={3} 
                      />
                      <Box>
                        <Text fontSize="sm" fontWeight="medium" color={useColorModeValue('gray.800', 'white')}>{user.organization}</Text>
                        <Text fontSize="xs" color={useColorModeValue('gray.600', 'whiteAlpha.800')}>{user.email}</Text>
                      </Box>
                      <Box ml="auto">
                        <IconButton
                          aria-label="More options"
                          icon={<ChevronDownIcon />}
                          variant="ghost"
                          size="sm"
                          color={useColorModeValue('gray.600', 'whiteAlpha.800')}
                          _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                        />
                      </Box>
                    </Flex>
                  </Box>
                )}
                
                {/* Menu items */}
                <MenuItem 
                  icon={<SettingsIcon />} 
                  py={3} 
                  color={useColorModeValue('gray.700', 'white')}
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                >
                  Settings
                </MenuItem>
                <MenuItem 
                  as={RouterLink} 
                  to="/docs" 
                  icon={<FaBook />} 
                  py={3}
                  color={useColorModeValue('gray.700', 'white')}
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                >
                  Documentation
                </MenuItem>
                <MenuDivider my={0} borderColor={useColorModeValue('gray.200', 'whiteAlpha.200')} />
                <MenuItem 
                  icon={<FaSignOutAlt />} 
                  onClick={onLogout} 
                  py={3} 
                  color="red.400"
                  _hover={{ bg: useColorModeValue('gray.100', 'whiteAlpha.200') }}
                >
                  Sign out
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </Flex>
      </Container>
      
      {/* Mobile Navigation Drawer */}
      <Drawer isOpen={isOpen} placement="left" onClose={onClose}>
        <DrawerOverlay />
        <DrawerContent>
          <DrawerCloseButton />
          <DrawerHeader borderBottomWidth="1px" bg="bg.primary" color="text.primary">
            Email Knowledge Base
          </DrawerHeader>
          <DrawerBody>
            <VStack align="stretch" spacing={3} mt={4}>
              {navItems.map((item) => (
                <Button
                  key={item.path}
                  as={RouterLink}
                  to={item.path}
                  variant={location.pathname === item.path || location.pathname.startsWith(item.path + '/') ? "solid" : "ghost"}
                  colorScheme={location.pathname === item.path || location.pathname.startsWith(item.path + '/') ? "blue" : "gray"}
                  leftIcon={<Icon as={item.icon} color="text.highlight" />}
                  justifyContent="flex-start"
                  onClick={onClose}
                >
                  {item.label}
                </Button>
              ))}
              <Button
                variant="ghost"
                colorScheme="red"
                leftIcon={<FaSignOutAlt />}
                justifyContent="flex-start"
                onClick={() => {
                  onClose();
                  onLogout();
                }}
              >
                Logout
              </Button>
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Box>
  );
};

export default Navbar;
