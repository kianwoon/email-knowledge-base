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
  Text
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { SunIcon, MoonIcon, HamburgerIcon, ChevronDownIcon, SettingsIcon } from '@chakra-ui/icons';
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
                  <Avatar size="sm" name="User" bg="bg.accent" />
                  <Text display={{ base: 'none', md: 'block' }}>Demo User</Text>
                </HStack>
              </MenuButton>
              <MenuList bg="bg.secondary" color="text.primary">
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
