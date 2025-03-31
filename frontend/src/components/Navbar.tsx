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
  Spinner
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { SunIcon, MoonIcon, HamburgerIcon, ChevronDownIcon, SettingsIcon } from '@chakra-ui/icons';
import { FaFilter, FaClipboardCheck, FaSearch, FaSignOutAlt, FaBook, FaUsers } from 'react-icons/fa';
import { getCurrentUser } from '../api/auth';

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
                  colorScheme="whiteAlpha"
                  isActive={location.pathname === item.path || location.pathname.startsWith(item.path + '/')}
                  _active={{ bg: "bg.accent", color: "text.primary" }}
                  _hover={{ bg: "bg.hover" }}
                  leftIcon={<Icon as={item.icon} color="text.highlight" />}
                  size="md"
                  fontWeight="medium"
                  px={4}
                >
                  {item.label}
                </Button>
              ))}
            </HStack>
          </Flex>
          
          {/* Right side controls */}
          <HStack spacing={2}>
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
              <MenuList bg="bg.secondary" color="text.primary" p={0} minWidth="320px">
                {/* User profile header */}
                <Box p={4} borderBottomWidth="1px" borderColor="whiteAlpha.200">
                  <Flex>
                    <Avatar 
                      size="md" 
                      name={user?.display_name || "User"} 
                      src={user?.photo_url} 
                      bg="bg.accent" 
                      mr={3} 
                    />
                    <Box>
                      <Text fontWeight="bold">{user?.display_name || "Demo User"}</Text>
                      <Text fontSize="sm" opacity={0.8}>{user?.email || "user@example.com"}</Text>
                      <HStack mt={2} spacing={2}>
                        <Button size="xs" variant="outline" colorScheme="blue">View account</Button>
                        <Button size="xs" variant="outline" colorScheme="blue">Switch directory</Button>
                      </HStack>
                    </Box>
                  </Flex>
                </Box>
                
                {/* Organization section */}
                {user?.organization && (
                  <Box p={3} borderBottomWidth="1px" borderColor="whiteAlpha.200">
                    <Flex align="center">
                      <Avatar 
                        size="sm" 
                        icon={<Icon as={FaUsers} fontSize="1.2rem" />} 
                        bg="gray.600" 
                        mr={3} 
                      />
                      <Box>
                        <Text fontSize="sm" fontWeight="medium">{user.organization}</Text>
                        <Text fontSize="xs" opacity={0.8}>{user.email}</Text>
                      </Box>
                      <Box ml="auto">
                        <IconButton
                          aria-label="More options"
                          icon={<ChevronDownIcon />}
                          variant="ghost"
                          size="sm"
                        />
                      </Box>
                    </Flex>
                  </Box>
                )}
                
                {/* Menu items */}
                <MenuItem icon={<SettingsIcon />} py={3}>Settings</MenuItem>
                <MenuItem as={RouterLink} to="/docs" icon={<FaBook />} py={3}>Documentation</MenuItem>
                <MenuDivider my={0} />
                <MenuItem icon={<FaSignOutAlt />} onClick={onLogout} py={3} color="red.300">Sign out</MenuItem>
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
