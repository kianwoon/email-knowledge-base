import React, { useState } from 'react';
import {
  Box,
  Button,
  Container,
  Heading,
  Text,
  VStack,
  Flex,
  HStack,
  SimpleGrid,
  Icon,
  Stack,
  Badge,
  Link as ChakraLink,
  Stat,
  StatNumber,
  StatHelpText,
  StatGroup,
  useToast,
  useColorMode,
  IconButton,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  useDisclosure,
  useBreakpointValue,
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import {
  FaRobot,
  FaSearch,
  FaLock,
  FaBrain,
  FaFilter,
  FaDatabase,
  FaChartLine,
  FaBuilding,
  FaUserTie,
  FaClock,
  FaLightbulb,
  FaUsers,
  FaMicrosoft,
  FaBars,
  FaSun,
  FaMoon,
} from 'react-icons/fa';

interface SignInProps {
  onLogin: () => void;
}

const SignIn: React.FC<SignInProps> = ({ onLogin }) => {
  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();
  const { colorMode, toggleColorMode } = useColorMode();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const isMobile = useBreakpointValue({ base: true, md: false });

  const handleSignIn = async () => {
    setIsLoading(true);
    try {
      // For demo purposes, we'll bypass the actual OAuth flow
      // and simulate a successful login
      setTimeout(() => {
        // Store a mock token in localStorage
        localStorage.setItem('token', 'mock-token-12345');
        localStorage.setItem('expires', new Date(Date.now() + 86400000).toISOString());

        // Call the onLogin callback to update authentication state
        onLogin();

        toast({
          title: "Login successful",
          description: "You are now signed in with a demo account",
          status: "success",
          duration: 3000,
          isClosable: true,
        });

        setIsLoading(false);
      }, 1000);
    } catch (error) {
      console.error('Login error:', error);
      setIsLoading(false);

      toast({
        title: "Login failed",
        description: "There was an error signing in",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  // Custom Navbar for the landing page
  const LandingNavbar = () => (
    <Box as="nav" bg="bg.primary" color="text.primary" boxShadow="sm" position="sticky" top="0" zIndex="sticky">
      <Flex justify="space-between" align="center" px={{ base: 4, md: 8 }} py={2} maxW="1400px" mx="auto">
        <Box as={RouterLink} to="/" fontWeight="bold" fontSize={{ base: "lg", md: "xl" }} color="text.primary" _hover={{ textDecoration: 'none' }}>Email Knowledge Base</Box>
        
        {isMobile ? (
          <>
            <HStack spacing={2}>
              <IconButton
                aria-label="Toggle color mode"
                icon={<Icon as={colorMode === 'light' ? FaMoon : FaSun} />}
                onClick={toggleColorMode}
                variant="ghost"
                color="text.primary"
                _hover={{ bg: "bg.accent" }}
                size="sm"
              />
              <IconButton
                aria-label="Open menu"
                icon={<Icon as={FaBars} />}
                onClick={onOpen}
                variant="ghost"
                color="text.primary"
                _hover={{ bg: "bg.accent" }}
              />
            </HStack>
            <Drawer isOpen={isOpen} placement="right" onClose={onClose}>
              <DrawerOverlay />
              <DrawerContent bg={colorMode === 'dark' ? "bg.primary" : "white"}>
                <DrawerCloseButton color="text.primary" />
                <DrawerHeader color="text.primary">Menu</DrawerHeader>
                <DrawerBody>
                  <VStack spacing={4} align="stretch">
                    <Button as={RouterLink} to="/#features" leftIcon={<Box as="span" fontSize="sm">🔍</Box>} variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      Features
                    </Button>
                    <Button as={RouterLink} to="/docs" leftIcon={<Box as="span" fontSize="sm">📄</Box>} variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      Documentation
                    </Button>
                    <Button as={RouterLink} to="/support" leftIcon={<Box as="span" fontSize="sm">❓</Box>} variant="ghost" w="full" justifyContent="flex-start" onClick={onClose}>
                      Support
                    </Button>
                    <Button 
                      onClick={() => {
                        handleSignIn();
                        onClose();
                      }}
                      colorScheme="blue"
                      w="full"
                      justifyContent="flex-start"
                    >
                      Sign In
                    </Button>
                    <Flex align="center" justify="space-between" w="full" pt={2} borderTop="1px solid" borderColor={colorMode === 'dark' ? "whiteAlpha.300" : "gray.200"}>
                      <Text fontSize="sm">Toggle theme</Text>
                      <IconButton
                        aria-label="Toggle color mode"
                        icon={colorMode === 'light' ? <Icon as={FaMoon} /> : <Icon as={FaSun} />}
                        onClick={toggleColorMode}
                        variant="ghost"
                        color="text.primary"
                        _hover={{ bg: "bg.accent" }}
                        size="md"
                      />
                    </Flex>
                  </VStack>
                </DrawerBody>
              </DrawerContent>
            </Drawer>
          </>
        ) : (
          <Flex align="center" gap={4}>
            <Flex align="center" gap={1}>
              <Box as="span" fontSize="sm">🔍</Box>
              <Box as="a" href="/docs" px={2} py={2} _hover={{ textDecoration: 'none' }} color="text.primary" fontSize="sm">Features</Box>
            </Flex>
            <Flex align="center" gap={1}>
              <Box as="span" fontSize="sm">📄</Box>
              <Box as="a" href="/docs" px={2} py={2} _hover={{ textDecoration: 'none' }} color="text.primary" fontSize="sm">Documentation</Box>
            </Flex>
            <Flex align="center" gap={1}>
              <Box as="span" fontSize="sm">❓</Box>
              <Box as="a" href="/support" px={2} py={2} _hover={{ textDecoration: 'none' }} color="text.primary" fontSize="sm">Support</Box>
            </Flex>
            <IconButton
              aria-label="Toggle color mode"
              icon={colorMode === 'light' ? <Icon as={FaMoon} /> : <Icon as={FaSun} />}
              onClick={toggleColorMode}
              variant="ghost"
              colorScheme={colorMode === 'dark' ? "whiteAlpha" : "blackAlpha"}
              color="text.primary"
              _hover={{ bg: "bg.accent" }}
              size="sm"
              borderRadius="full"
            />
            <Button
              onClick={handleSignIn}
              px={4}
              py={2}
              bg="bg.highlight"
              color="text.inverted"
              borderRadius="md"
              _hover={{ opacity: 0.9 }}
              fontSize="sm"
              size="sm"
            >
              Sign In
            </Button>
          </Flex>
        )}
      </Flex>
    </Box>
  );

  return (
    <Box bg={colorMode === 'dark' ? 'dark.bg' : 'light.bg'} minH="100vh" position="relative" overflow="hidden">
      {/* Custom Navbar */}
      <LandingNavbar />
      
      {/* Hero Section */}
      <Box
        py={{ base: 10, md: 20 }}
        px={{ base: 4, md: 8 }}
        position="relative"
        zIndex="1"
      >
        <Container maxW="1400px">
          <Flex direction={{ base: "column", md: "row" }} align="center" justify="space-between" gap={{ md: 8 }} position="relative">
            {/* Text Content */}
            <Box 
              w={{ base: "100%", md: "50%" }} 
              zIndex={2} 
              position="relative"
            >
              <VStack spacing={{ base: 6, md: 6 }} align={{ base: "center", md: "flex-start" }} textAlign={{ base: "center", md: "left" }}>
                <Box 
                  bg={colorMode === 'dark' ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.05)"} 
                  px={3} 
                  py={1} 
                  borderRadius="full"
                >
                  <Text 
                    fontSize={{ base: "sm", md: "md" }} 
                    color={colorMode === 'dark' ? "cyan.400" : "blue.500"}
                    fontWeight="medium"
                  >
                    AI-POWERED EMAIL KNOWLEDGE BASE
                  </Text>
                </Box>

                <Heading
                  as="h1"
                  size={{ base: "xl", md: "2xl" }}
                  color={colorMode === 'dark' ? "white" : "gray.800"}
                  lineHeight="1.2"
                  fontWeight="bold"
                >
                  Reclaim Your Time from Routine Email Tasks
                </Heading>

                <Text fontSize={{ base: "md", md: "lg" }} color={colorMode === 'dark' ? "gray.300" : "gray.700"}>
                  Office workers spend over 50% of their time on repetitive email communications. Our platform extracts valuable knowledge from your emails, enabling AI to handle routine tasks with personalized tone and clarity.
                </Text>

                <HStack spacing={{ base: 2, md: 4 }} pt={2} flexDir={{ base: "column", sm: "row" }} w={{ base: "100%", sm: "auto" }}>
                  <Button
                    leftIcon={<Icon as={FaMicrosoft} />}
                    onClick={handleSignIn}
                    isLoading={isLoading}
                    loadingText="Signing in..."
                    size={{ base: "md", md: "md" }}
                    colorScheme="cyan"
                    bg={colorMode === 'dark' ? "cyan.400" : "cyan.500"}
                    color="white"
                    _hover={{
                      bg: colorMode === 'dark' ? "cyan.500" : "cyan.600",
                    }}
                    px={6}
                    w={{ base: "100%", sm: "auto" }}
                    mb={{ base: 2, sm: 0 }}
                    zIndex={3}
                  >
                    Sign in with Microsoft
                  </Button>
                  <Button
                    as={RouterLink}
                    to="/docs"
                    variant="outline"
                    size={{ base: "md", md: "md" }}
                    borderColor={colorMode === 'dark' ? "gray.600" : "gray.300"}
                    color={colorMode === 'dark' ? "white" : "gray.800"}
                    _hover={{
                      bg: colorMode === 'dark' ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.05)",
                    }}
                    w={{ base: "100%", sm: "auto" }}
                    zIndex={3}
                  >
                    Learn More
                  </Button>
                </HStack>
              </VStack>
            </Box>
            
            {/* Happy Man Image - Now shown on mobile at a smaller size */}
            <Box 
              w={{ base: "70%", md: "50%" }}
              h="auto"
              position="relative"
              display="block"
              overflow="visible"
              ml={{ md: 4 }}
              textAlign="center"
              pr={{ md: 2 }}
              mt={{ base: 12, md: 0 }}
              mb={{ base: 8, md: 0 }}
              order={{ base: 2, md: 1 }}
            >
              <Box
                as="img"
                src="/images/happy-man.png"
                alt="Happy man making OK gesture"
                objectFit="contain"
                height="auto"
                width="100%"
                maxH={{ base: "250px", md: "500px" }}
                position="relative"
                zIndex={1}
                sx={{
                  clipPath: 'circle(40% at 50% 40%)',
                  transform: { base: 'scale(1.2)', md: 'scale(1.8) translateX(40px)' }
                }}
              />
            </Box>
          </Flex>
        </Container>
      </Box>

      {/* Stats Section */}
      <Box
        py={{ base: 8, md: 12 }}
        px={{ base: 4, md: 8 }}
        position="relative"
        zIndex="1"
        bg={colorMode === 'dark' ? "rgba(255, 255, 255, 0.03)" : "rgba(0, 0, 0, 0.02)"}
        borderTop={colorMode === 'dark' ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(0, 0, 0, 0.1)"}
        borderBottom={colorMode === 'dark' ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(0, 0, 0, 0.1)"}
      >
        <Container maxW="1400px">
          <StatGroup textAlign="center" color={colorMode === 'dark' ? "white" : "gray.800"}>
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={{ base: 6, md: 10 }} width="100%">
              <Stat>
                <Flex direction="column" align="center">
                  <Icon as={FaClock} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mb={4} />
                  <StatNumber fontSize={{ base: "3xl", md: "4xl" }} fontWeight="bold">50%+</StatNumber>
                  <StatHelpText fontSize={{ base: "md", md: "lg" }} color={colorMode === 'dark' ? "white" : "gray.600"}>
                    Office time spent on routine emails
                  </StatHelpText>
                </Flex>
              </Stat>

              <Stat>
                <Flex direction="column" align="center">
                  <Icon as={FaLightbulb} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mb={4} />
                  <StatNumber fontSize={{ base: "3xl", md: "4xl" }} fontWeight="bold">3x</StatNumber>
                  <StatHelpText fontSize={{ base: "md", md: "lg" }} color={colorMode === 'dark' ? "white" : "gray.600"}>
                    Productivity increase with AI assistance
                  </StatHelpText>
                </Flex>
              </Stat>

              <Stat>
                <Flex direction="column" align="center">
                  <Icon as={FaUsers} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mb={4} />
                  <StatNumber fontSize={{ base: "3xl", md: "4xl" }} fontWeight="bold">10x</StatNumber>
                  <StatHelpText fontSize={{ base: "md", md: "lg" }} color={colorMode === 'dark' ? "white" : "gray.600"}>
                    Return on investment for enterprise users
                  </StatHelpText>
                </Flex>
              </Stat>
            </SimpleGrid>
          </StatGroup>
        </Container>
      </Box>

      {/* Features Section */}
      <Box py={{ base: 16, md: 20 }} px={{ base: 4, md: 8 }} position="relative" zIndex="1">
        <Container maxW="1400px">
          <VStack spacing={{ base: 8, md: 12 }} align="stretch">
            <VStack spacing={4} align="center" textAlign="center">
              <Heading
                size={{ base: "lg", md: "xl" }}
                color={colorMode === 'dark' ? "white" : "gray.800"}
              >
                Unlock the Hidden Knowledge in Your Communications
              </Heading>
              <Text fontSize={{ base: "md", md: "lg" }} maxW="800px" color={colorMode === 'dark' ? "whiteAlpha.900" : "gray.600"}>
                Transform your team's emails into a powerful knowledge resource that enables AI to handle routine tasks with personalized tone and clarity.
              </Text>
            </VStack>

            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={{ base: 6, md: 8 }}>
              <FeatureCard
                icon={FaFilter}
                title="Smart Email Processing"
                description="Automatically filter and categorize emails based on content, priority, and knowledge value."
                link="/docs/smart-filtering"
              />

              <FeatureCard
                icon={FaBrain}
                title="AI-Powered Knowledge Extraction"
                description="Extract valuable insights and patterns from your communications using advanced AI algorithms."
                link="/docs/ai-analysis"
              />

              <FeatureCard
                icon={FaDatabase}
                title="Centralized Knowledge Base"
                description="Store all extracted knowledge in a searchable, secure database accessible to your entire team."
                link="/docs/knowledge-base"
              />

              <FeatureCard
                icon={FaLock}
                title="Enterprise-Grade Security"
                description="Keep your sensitive information protected with our robust security infrastructure and compliance measures."
                link="/docs/secure-authentication"
              />

              <FeatureCard
                icon={FaRobot}
                title="AI Assistant Training"
                description="Train AI to handle routine communications with personalized tone, freeing your team for higher-value work."
                link="/docs/ai-analysis"
              />

              <FeatureCard
                icon={FaSearch}
                title="Powerful Search Capabilities"
                description="Quickly find the information you need with our advanced semantic search technology."
                link="/docs/knowledge-base"
              />
            </SimpleGrid>
          </VStack>
        </Container>
      </Box>

      {/* Use Cases Section */}
      <Box
        py={{ base: 16, md: 20 }}
        px={{ base: 4, md: 8 }}
        position="relative"
        zIndex="1"
        bg={colorMode === 'dark' ? "rgba(255, 255, 255, 0.03)" : "rgba(0, 0, 0, 0.02)"}
        borderTop={colorMode === 'dark' ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(0, 0, 0, 0.1)"}
        borderBottom={colorMode === 'dark' ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(0, 0, 0, 0.1)"}
      >
        <Container maxW="1400px">
          <VStack spacing={{ base: 8, md: 12 }} align="stretch">
            <VStack spacing={4} align="center" textAlign="center">
              <Heading
                size={{ base: "lg", md: "xl" }}
                color={colorMode === 'dark' ? "white" : "gray.800"}
              >
                Transforming Work Across Departments
              </Heading>
              <Text fontSize={{ base: "md", md: "lg" }} maxW="800px" color={colorMode === 'dark' ? "whiteAlpha.900" : "gray.600"}>
                See how teams across your organization can benefit from our email knowledge base solution.
              </Text>
            </VStack>

            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={{ base: 6, md: 8 }}>
              <UseCaseCard
                icon={FaUserTie}
                sector="HR DEPARTMENTS"
                title="Streamlined Employee Support"
                description="Automate responses to common HR inquiries, onboarding processes, and policy questions with consistent, accurate information."
              />

              <UseCaseCard
                icon={FaBuilding}
                sector="ADMINISTRATIVE TEAMS"
                title="Efficient Office Management"
                description="Handle routine administrative requests and information sharing while maintaining personalized service levels."
              />

              <UseCaseCard
                icon={FaChartLine}
                sector="FINANCE DEPARTMENTS"
                title="Consistent Financial Communication"
                description="Provide standardized responses to budget inquiries, expense procedures, and financial reporting questions."
              />

              <UseCaseCard
                icon={FaUsers}
                sector="SALES TEAMS"
                title="Enhanced Client Communication"
                description="Maintain consistent messaging across client interactions while personalizing responses based on relationship history."
              />

              <UseCaseCard
                icon={FaBrain}
                sector="CONSULTING AGENCIES"
                title="Client Knowledge Preservation"
                description="Preserve high-value electronic insights as an end-to-end confidential records and archive."
              />

              <UseCaseCard
                icon={FaChartLine}
                sector="FINANCIAL SERVICES"
                title="Structured Deal Records"
                description="Manage and export data recordings to structured total records accessing retention."
              />
            </SimpleGrid>
          </VStack>
        </Container>
      </Box>

      {/* CTA Section */}
      <Box
        py={{ base: 16, md: 20 }}
        px={{ base: 4, md: 8 }}
        position="relative"
        zIndex="1"
        bg={colorMode === 'dark' ? "#2A4365" : "#3182CE"}
      >
        <Container maxW="1400px">
          <VStack spacing={{ base: 6, md: 8 }} align="center" textAlign="center">
            <Heading
              size={{ base: "lg", md: "xl" }}
              color="white !important"
              textShadow="0px 1px 2px rgba(0, 0, 0, 0.5)"
              fontWeight="bold"
              letterSpacing="0.2px"
            >
              Ready to free your team from routine emails?
            </Heading>
            <Text 
              fontSize={{ base: "md", md: "lg" }} 
              maxW="800px" 
              color="white !important"
              textShadow="0px 1px 2px rgba(0, 0, 0, 0.5)"
              fontWeight="semibold"
              letterSpacing="0.2px"
              opacity="1"
            >
              Take the first step toward multiplying your team's productivity. Our platform makes it easy to harness the knowledge hidden in your emails, enabling AI to handle routine correspondence while your team focuses on making greater contributions.
            </Text>
            <Button
              size={{ base: "md", md: "lg" }}
              bg="white"
              color={colorMode === 'dark' ? "#2A4365" : "#3182CE"}
              _hover={{ bg: "gray.100" }}
              px={8}
              onClick={handleSignIn}
              leftIcon={<Icon as={FaMicrosoft} color={colorMode === 'dark' ? "#2A4365" : "#3182CE"} />}
              isLoading={isLoading}
              loadingText="Connecting..."
              boxShadow="md"
              w={{ base: "100%", sm: "auto" }}
              maxW={{ base: "100%", sm: "300px" }}
            >
              Get Started Now
            </Button>
          </VStack>
        </Container>
      </Box>

      {/* Footer */}
      <Box py={{ base: 8, md: 12 }} px={{ base: 4, md: 8 }} color={colorMode === 'dark' ? "whiteAlpha.800" : "gray.600"} position="relative" zIndex="1">
        <Container maxW="1400px">
          <Stack direction={{ base: 'column', md: 'row' }} justify="space-between" align={{ base: 'center', md: 'flex-start' }} spacing={{ base: 6, md: 0 }}>
            <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2}>
              <Heading size={{ base: "sm", md: "md" }} color={colorMode === 'dark' ? "white" : "gray.800"}>Email Knowledge Base</Heading>
              <Text fontSize="sm" textAlign={{ base: 'center', md: 'left' }}> 2025 Email Knowledge Base. All rights reserved.</Text>
            </VStack>

            <Stack 
              direction={{ base: 'column', sm: 'row' }} 
              spacing={{ base: 3, md: 6 }}
              align="center"
              flexWrap="wrap"
              justify={{ base: 'center', md: 'flex-end' }}
              mt={{ base: 4, md: 0 }}
            >
              <ChakraLink as={RouterLink} to="/docs" _hover={{ color: colorMode === 'dark' ? 'neon.blue' : 'blue.500' }}>Documentation</ChakraLink>
              <ChakraLink as={RouterLink} to="/support" _hover={{ color: colorMode === 'dark' ? 'neon.blue' : 'blue.500' }}>Support</ChakraLink>
              <ChakraLink href="#" _hover={{ color: colorMode === 'dark' ? 'neon.blue' : 'blue.500' }}>Privacy Policy</ChakraLink>
              <ChakraLink href="#" _hover={{ color: colorMode === 'dark' ? 'neon.blue' : 'blue.500' }}>Terms of Service</ChakraLink>
            </Stack>
          </Stack>
        </Container>
      </Box>

      {/* Background Elements */}
    </Box>
  );
};

// Feature Card Component
const FeatureCard = ({ icon, title, description, link }: {
  icon: any,
  title: string,
  description: string,
  link: string
}) => {
  const { colorMode } = useColorMode();
  return (
    <Box
      bg={colorMode === 'dark' ? "rgba(255, 255, 255, 0.05)" : "white"}
      borderRadius="xl"
      p={{ base: 4, md: 6 }}
      transition="all 0.3s"
      _hover={{ 
        transform: "translateY(-5px)", 
        bg: colorMode === 'dark' ? "rgba(255, 255, 255, 0.08)" : "gray.50",
        boxShadow: "md"
      }}
      height="100%"
      boxShadow="sm"
      borderWidth="1px"
      borderColor={colorMode === 'dark' ? "transparent" : "gray.200"}
    >
      <Icon as={icon} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color="text.highlight" mb={4} />
      <Heading as="h3" size={{ base: "md", md: "lg" }} mb={2} color={colorMode === 'dark' ? "white" : "gray.800"}>
        {title}
      </Heading>
      <Text color={colorMode === 'dark' ? "whiteAlpha.800" : "gray.600"} mb={4} fontSize={{ base: "sm", md: "md" }}>
        {description}
      </Text>
      <ChakraLink as={RouterLink} to={link} color="text.highlight" fontWeight="bold">
        Learn more →
      </ChakraLink>
    </Box>
  );
};

// Use Case Card Component
const UseCaseCard = ({ icon, sector, title, description }: {
  icon: any,
  sector: string,
  title: string,
  description: string
}) => {
  const { colorMode } = useColorMode();
  return (
    <Box
      bg={colorMode === 'dark' ? "rgba(255, 255, 255, 0.05)" : "white"}
      borderRadius="xl"
      p={{ base: 4, md: 6 }}
      transition="all 0.3s"
      _hover={{ 
        transform: "translateY(-5px)", 
        bg: colorMode === 'dark' ? "rgba(255, 255, 255, 0.08)" : "gray.50",
        boxShadow: "md"
      }}
      height="100%"
      boxShadow="sm"
      borderWidth="1px"
      borderColor={colorMode === 'dark' ? "transparent" : "gray.200"}
    >
      <Flex align="center" mb={4}>
        <Icon as={icon} w={{ base: 6, md: 8 }} h={{ base: 6, md: 8 }} color="text.highlight" mr={3} />
        <Badge colorScheme={colorMode === 'dark' ? "purple" : "blue"}>{sector}</Badge>
      </Flex>
      <Heading as="h3" size={{ base: "md", md: "lg" }} mb={2} color={colorMode === 'dark' ? "white" : "gray.800"}>
        {title}
      </Heading>
      <Text color={colorMode === 'dark' ? "whiteAlpha.800" : "gray.600"} fontSize={{ base: "sm", md: "md" }}>
        {description}
      </Text>
    </Box>
  );
};

export default SignIn;
