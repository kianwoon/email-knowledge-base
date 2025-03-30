import React from 'react';
import { 
  Box, 
  Flex, 
  Button, 
  Heading, 
  useColorMode, 
  IconButton, 
  HStack, 
  Container,
  Image,
  Text,
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
  Icon
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { SunIcon, MoonIcon, HamburgerIcon, ChevronDownIcon, SearchIcon, EmailIcon, SettingsIcon } from '@chakra-ui/icons';
import { FaFilter, FaClipboardCheck, FaSearch, FaSignOutAlt, FaBook } from 'react-icons/fa';

interface NavbarProps {
  onLogout: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ onLogout }) => {
  const { colorMode, toggleColorMode } = useColorMode();
  const location = useLocation();
  const { isOpen, onOpen, onClose } = useDisclosure();
  
  // Define navigation items
  const navItems = [
    { path: '/filter', label: 'Filter Emails', icon: FaFilter },
    { path: '/review', label: 'Review', icon: FaClipboardCheck },
    { path: '/search', label: 'Search', icon: FaSearch },
    { path: '/docs', label: 'Documentation', icon: FaBook },
  ];
  
  return (
    <Box as="nav" bg="primary.600" color="white" boxShadow="md" position="sticky" top="0" zIndex="sticky">
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
                  _active={{ bg: 'primary.700', color: 'white' }}
                  _hover={{ bg: 'primary.500' }}
                  leftIcon={<Icon as={item.icon} />}
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
              _hover={{ bg: 'primary.500' }}
            />
            
            {/* Mobile menu button */}
            <IconButton
              display={{ base: 'flex', md: 'none' }}
              aria-label="Open menu"
              icon={<HamburgerIcon />}
              onClick={onOpen}
              variant="ghost"
              colorScheme="whiteAlpha"
              _hover={{ bg: 'primary.500' }}
            />
            
            {/* User menu */}
            <Menu>
              <MenuButton
                as={Button}
                variant="ghost"
                colorScheme="whiteAlpha"
                _hover={{ bg: 'primary.500' }}
                rightIcon={<ChevronDownIcon />}
              >
                <HStack>
                  <Avatar size="sm" name="User" bg="primary.300" />
                  <Text display={{ base: 'none', md: 'block' }}>Demo User</Text>
                </HStack>
              </MenuButton>
              <MenuList bg="white" color="gray.800">
                <MenuItem icon={<SettingsIcon />}>Settings</MenuItem>
                <MenuItem as={RouterLink} to="/docs" icon={<FaBook />}>Documentation</MenuItem>
                <MenuDivider />
                <MenuItem icon={<FaSignOutAlt />} onClick={onLogout}>Logout</MenuItem>
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
          <DrawerHeader borderBottomWidth="1px" bg="primary.600" color="white">
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
                  colorScheme={location.pathname === item.path || location.pathname.startsWith(item.path + '/') ? "primary" : "gray"}
                  leftIcon={<Icon as={item.icon} />}
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
