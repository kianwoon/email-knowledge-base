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
  useBreakpointValue,
  Stat,
  StatNumber,
  StatHelpText,
  StatGroup,
  useToast,
  IconButton,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  useDisclosure,
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
} from 'react-icons/fa';
import { getLoginUrl } from '../api/auth';

interface SignInProps {
  onLogin: () => void;
}

const SignIn: React.FC<SignInProps> = ({ onLogin }) => {
  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();
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

  // Mobile Navigation Drawer
  const MobileNav = () => (
    <Drawer isOpen={isOpen} placement="right" onClose={onClose}>
      <DrawerOverlay />
      <DrawerContent bg="#050a30">
        <DrawerCloseButton color="white" />
        <DrawerHeader borderBottomWidth="1px" color="white">Menu</DrawerHeader>
        <DrawerBody>
          <VStack spacing={4} align="stretch" mt={4}>
            <Button as={RouterLink} to="/#features" variant="glass" size="md" onClick={onClose}>Features</Button>
            <Button as={RouterLink} to="/docs" variant="glass" size="md" onClick={onClose}>Documentation</Button>
            <Button as={RouterLink} to="/support" variant="glass" size="md" onClick={onClose}>Support</Button>
          </VStack>
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  );

  return (
    <Box bg="#050a30" minH="100vh" position="relative" overflow="hidden">
      {/* Header/Nav */}
      <Box 
        py={4} 
        px={{ base: 4, md: 8 }} 
        color="white" 
        position="relative" 
        zIndex="1"
        bgGradient="linear(to-r, neon.dark, neon.purple, neon.pink)"
      >
        <Flex maxW="1400px" mx="auto" justify="space-between" align="center">
          <Heading size={{ base: "md", md: "lg" }} fontWeight="bold">Email Knowledge Base</Heading>
          {isMobile ? (
            <IconButton
              aria-label="Open menu"
              icon={<FaBars />}
              variant="ghost"
              color="white"
              onClick={onOpen}
            />
          ) : (
            <HStack spacing={4}>
              <Button as={RouterLink} to="/#features" variant="glass" size="sm">Features</Button>
              <Button as={RouterLink} to="/docs" variant="glass" size="sm">Documentation</Button>
              <Button as={RouterLink} to="/support" variant="glass" size="sm">Support</Button>
            </HStack>
          )}
        </Flex>
      </Box>
      
      {/* Mobile Navigation */}
      <MobileNav />
      
      {/* Hero Section */}
      <Box
        py={{ base: 10, md: 28 }}
        px={{ base: 4, md: 8 }}
        position="relative"
        zIndex="1"
      >
        <Container maxW="1400px">
          <VStack spacing={{ base: 6, md: 8 }} align={{ base: "center", md: "flex-start" }} textAlign={{ base: "center", md: "left" }}>
            <Badge colorScheme="purple" fontSize={{ base: "sm", md: "md" }} px={3} py={1} borderRadius="full">
              AI-Powered Email Knowledge Base
            </Badge>

            <Heading
              as="h1"
              size={{ base: "xl", md: "2xl" }}
              lineHeight="1.2"
              bgGradient="linear(to-r, white, #3ef2f2)"
              bgClip="text"
              mb={{ base: 2, md: 4 }}
            >
              Reclaim Your Time from <br />
              Routine Email Tasks
            </Heading>

            <Text fontSize={{ base: "md", md: "xl" }} maxW="800px" color="whiteAlpha.900" mb={{ base: 4, md: 6 }}>
              Office workers spend over 50% of their time on repetitive email communications.
              Our platform extracts valuable knowledge from your emails, enabling AI to handle
              routine tasks with personalized tone and clarity.
            </Text>

            <Stack direction={{ base: "column", sm: "row" }} spacing={4} w={{ base: "100%", sm: "auto" }}>
              <Button
                size="lg"
                variant="neon"
                px={8}
                onClick={handleSignIn}
                leftIcon={<Icon as={FaMicrosoft} />}
                isLoading={isLoading}
                loadingText="Connecting..."
                width={{ base: "100%", sm: "auto" }}
              >
                Sign in with Microsoft
              </Button>
              <Button
                as={RouterLink}
                to="/docs"
                size="lg"
                variant="outline"
                colorScheme="whiteAlpha"
                px={8}
                width={{ base: "100%", sm: "auto" }}
              >
                Learn More
              </Button>
            </Stack>
          </VStack>
        </Container>
      </Box>

      {/* Stats Section */}
      <Box
        py={{ base: 8, md: 12 }}
        px={{ base: 4, md: 8 }}
        position="relative"
        zIndex="1"
        bg="rgba(255, 255, 255, 0.03)"
        borderTop="1px solid rgba(255, 255, 255, 0.1)"
        borderBottom="1px solid rgba(255, 255, 255, 0.1)"
      >
        <Container maxW="1400px">
          <StatGroup textAlign="center" color="white">
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={{ base: 6, md: 10 }} width="100%">
              <Stat>
                <Flex direction="column" align="center">
                  <Icon as={FaClock} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color="neon.blue" mb={4} />
                  <StatNumber fontSize={{ base: "3xl", md: "4xl" }} fontWeight="bold">50%+</StatNumber>
                  <StatHelpText fontSize={{ base: "md", md: "lg" }} color="white">
                    Office time spent on routine emails
                  </StatHelpText>
                </Flex>
              </Stat>

              <Stat>
                <Flex direction="column" align="center">
                  <Icon as={FaLightbulb} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color="neon.blue" mb={4} />
                  <StatNumber fontSize={{ base: "3xl", md: "4xl" }} fontWeight="bold">3x</StatNumber>
                  <StatHelpText fontSize={{ base: "md", md: "lg" }} color="white">
                    Productivity increase with AI assistance
                  </StatHelpText>
                </Flex>
              </Stat>

              <Stat>
                <Flex direction="column" align="center">
                  <Icon as={FaUsers} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color="neon.blue" mb={4} />
                  <StatNumber fontSize={{ base: "3xl", md: "4xl" }} fontWeight="bold">10x</StatNumber>
                  <StatHelpText fontSize={{ base: "md", md: "lg" }} color="white">
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
                bgGradient="linear(to-r, white, #3ef2f2)"
                bgClip="text"
              >
                Unlock the Hidden Knowledge in Your Communications
              </Heading>
              <Text fontSize={{ base: "md", md: "lg" }} maxW="800px" color="whiteAlpha.900">
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
                link="/docs"
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
        bg="rgba(255, 255, 255, 0.03)"
        borderTop="1px solid rgba(255, 255, 255, 0.1)"
        borderBottom="1px solid rgba(255, 255, 255, 0.1)"
      >
        <Container maxW="1400px">
          <VStack spacing={{ base: 8, md: 12 }} align="stretch">
            <VStack spacing={4} align="center" textAlign="center">
              <Heading
                size={{ base: "lg", md: "xl" }}
                bgGradient="linear(to-r, white, #3ef2f2)"
                bgClip="text"
              >
                Transforming Work Across Departments
              </Heading>
              <Text fontSize={{ base: "md", md: "lg" }} maxW="800px" color="whiteAlpha.900">
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
        bgGradient="linear(to-r, neon.dark, neon.purple)"
      >
        <Container maxW="1400px">
          <VStack spacing={{ base: 6, md: 8 }} align="center" textAlign="center">
            <Heading
              size={{ base: "lg", md: "xl" }}
              bgGradient="linear(to-r, white, #3ef2f2)"
              bgClip="text"
            >
              Ready to free your team from routine emails?
            </Heading>
            <Text fontSize={{ base: "md", md: "lg" }} maxW="800px" color="whiteAlpha.900">
              Take the first step toward multiplying your team's productivity. Our platform makes it easy to harness the knowledge hidden in your emails, enabling AI to handle routine correspondence while your team focuses on making greater contributions.
            </Text>
            <Button
              size="lg"
              variant="neon"
              px={8}
              onClick={handleSignIn}
              leftIcon={<Icon as={FaMicrosoft} />}
              isLoading={isLoading}
              loadingText="Connecting..."
            >
              Get Started Now
            </Button>
          </VStack>
        </Container>
      </Box>

      {/* Footer */}
      <Box py={12} px={{ base: 4, md: 8 }} color="whiteAlpha.800" position="relative" zIndex="1">
        <Container maxW="1400px">
          <Stack direction={{ base: 'column', md: 'row' }} justify="space-between" align="center">
            <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2}>
              <Heading size="md" color="white">Email Knowledge Base</Heading>
              <Text fontSize="sm"> 2025 Email Knowledge Base. All rights reserved.</Text>
            </VStack>

            <HStack spacing={6} mt={{ base: 4, md: 0 }}>
              <ChakraLink as={RouterLink} to="/docs" _hover={{ color: 'neon.blue' }}>Documentation</ChakraLink>
              <ChakraLink as={RouterLink} to="/support" _hover={{ color: 'neon.blue' }}>Support</ChakraLink>
              <ChakraLink href="#" _hover={{ color: 'neon.blue' }}>Privacy Policy</ChakraLink>
              <ChakraLink href="#" _hover={{ color: 'neon.blue' }}>Terms of Service</ChakraLink>
            </HStack>
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
  return (
    <Box
      bg="rgba(255, 255, 255, 0.05)"
      borderRadius="xl"
      p={{ base: 4, md: 6 }}
      transition="all 0.3s"
      _hover={{ transform: "translateY(-5px)", bg: "rgba(255, 255, 255, 0.08)" }}
      height="100%"
    >
      <Icon as={icon} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color="neon.blue" mb={4} />
      <Heading as="h3" size={{ base: "md", md: "lg" }} mb={2} color="white">
        {title}
      </Heading>
      <Text color="whiteAlpha.800" mb={4} fontSize={{ base: "sm", md: "md" }}>
        {description}
      </Text>
      <ChakraLink as={RouterLink} to={link} color="neon.blue" fontWeight="bold">
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
  return (
    <Box
      bg="rgba(255, 255, 255, 0.05)"
      borderRadius="xl"
      p={{ base: 4, md: 6 }}
      transition="all 0.3s"
      _hover={{ transform: "translateY(-5px)", bg: "rgba(255, 255, 255, 0.08)" }}
      height="100%"
    >
      <Flex align="center" mb={4}>
        <Icon as={icon} w={{ base: 6, md: 8 }} h={{ base: 6, md: 8 }} color="neon.blue" mr={3} />
        <Badge colorScheme="purple">{sector}</Badge>
      </Flex>
      <Heading as="h3" size={{ base: "md", md: "lg" }} mb={2} color="white">
        {title}
      </Heading>
      <Text color="whiteAlpha.800" fontSize={{ base: "sm", md: "md" }}>
        {description}
      </Text>
    </Box>
  );
};

export default SignIn;
