import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Container,
  Flex,
  Heading,
  Text,
  VStack,
  HStack,
  useBreakpointValue,
  useColorMode,
  IconButton,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  useDisclosure,
  SimpleGrid,
  Stack,
  Link as ChakraLink,
  Stat,
  StatNumber,
  StatHelpText,
  StatGroup,
  useToast,
  Icon,
  Badge,
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
import {
  FaLightbulb,
  FaSearch,
  FaBars,
  FaMoon,
  FaSun,
  FaRobot,
  FaLock,
  FaBrain,
  FaFilter,
  FaDatabase,
  FaUsers,
  FaMicrosoft,
  FaClock,
} from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../components/LanguageSwitcher';
import { getLoginUrl } from '../api/auth';
import ImageCarousel from '../components/ImageCarousel';

interface SignInProps {
  onLogin: () => void;
  isAuthenticated: boolean;
}

const SignIn: React.FC<SignInProps> = ({ onLogin, isAuthenticated }) => {
  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();
  const { colorMode, toggleColorMode } = useColorMode();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const isMobile = useBreakpointValue({ base: true, md: false });
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    // Check for token in URL after OAuth redirect
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const expires = params.get('expires');

    if (token && expires) {
      // Store tokens
      localStorage.setItem('token', token);
      localStorage.setItem('expires', expires);

      // Clear URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);

      // Update auth state and redirect
      onLogin();
      navigate('/filter', { replace: true });
      
      toast({
        title: 'Login successful',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    }
  }, [onLogin, navigate, toast]);

  const handleSignIn = async () => {
    setIsLoading(true);
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
      setIsLoading(false);

      toast({
        title: t('toast.loginError.title'),
        description: t('toast.loginError.description'),
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const carouselImages = [
    {
      src: '/images/happy-man.png',
      alt: 'Happy man making an OK gesture'
    },
    {
      src: '/images/happy2.png',
      alt: 'Happy person 2'
    },
    {
      src: '/images/happy3.png',
      alt: 'Happy person 3'
    },
    {
      src: '/images/happy4.png',
      alt: 'Happy person 4'
    },
    {
      src: '/images/happy5.png',
      alt: 'Happy person 5'
    }
  ];

  return (
    <>
      <Box as="main" minH="100vh" bg={colorMode === 'dark' ? "dark.bg" : "light.bg"} position="relative" overflow="hidden">
        {/* Hero Section */}
        <Box
          py={{ base: 2, md: 4 }} 
          px={4} 
          bg={colorMode === 'dark' ? "linear-gradient(180deg, rgba(13,18,38,0) 0%, rgba(13,18,38,1) 100%)" : "linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(240,240,250,1) 100%)"}
        >
          <Container maxW="1400px">
            <Flex direction={{ base: "column", md: "row" }} align="center" justify="space-between" gap={{ md: 8 }} position="relative">
              {/* Text Content */}
              <Box 
                w={{ base: "100%", md: "50%" }} 
                zIndex={2} 
                position="relative"
                textAlign={{ base: "center", md: "left" }}
              >
                <VStack spacing={{ base: 1.5, md: 1.5 }} align={{ base: "center", md: "flex-start" }}>
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
                      {t('app.tagline')}
                    </Text>
                  </Box>

                  <Heading
                    as="h1"
                    size={{ base: "xl", md: "2xl" }}
                    color={colorMode === 'dark' ? "white" : "gray.800"}
                    lineHeight="1.2"
                    fontWeight="bold"
                  >
                    {t('home.hero.title')}
                  </Heading>

                  <Text fontSize={{ base: "md", md: "lg" }} color={colorMode === 'dark' ? "gray.300" : "gray.700"}>
                    {t('home.hero.description')}
                  </Text>

                  <HStack spacing={{ base: 2, md: 4 }} pt={2} flexDir={{ base: "column", sm: "row" }} w={{ base: "100%", sm: "auto" }}>
                    {!isAuthenticated && (
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
                        {t('home.cta.signIn')}
                      </Button>
                    )}
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
                      {t('home.cta.learnMore')}
                    </Button>
                  </HStack>
                </VStack>
              </Box>
              
              {/* Replace Happy Man Image with ImageCarousel */}
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
                <ImageCarousel images={carouselImages} />
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
                      {t('stats.officeTimeSpent')}
                    </StatHelpText>
                  </Flex>
                </Stat>

                <Stat>
                  <Flex direction="column" align="center">
                    <Icon as={FaLightbulb} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mb={4} />
                    <StatNumber fontSize={{ base: "3xl", md: "4xl" }} fontWeight="bold">3x</StatNumber>
                    <StatHelpText fontSize={{ base: "md", md: "lg" }} color={colorMode === 'dark' ? "white" : "gray.600"}>
                      {t('stats.productivityIncrease')}
                    </StatHelpText>
                  </Flex>
                </Stat>

                <Stat>
                  <Flex direction="column" align="center">
                    <Icon as={FaUsers} w={{ base: 8, md: 10 }} h={{ base: 8, md: 10 }} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mb={4} />
                    <StatNumber fontSize={{ base: "3xl", md: "4xl" }} fontWeight="bold">10x</StatNumber>
                    <StatHelpText fontSize={{ base: "md", md: "lg" }} color={colorMode === 'dark' ? "white" : "gray.600"}>
                      {t('stats.returnOnInvestment')}
                    </StatHelpText>
                  </Flex>
                </Stat>
              </SimpleGrid>
            </StatGroup>
          </Container>
        </Box>

        {/* Features Section */}
        <Box py={{ base: 16, md: 24 }} id="features">
          <Container maxW="1400px">
            <VStack spacing={{ base: 8, md: 12 }} mb={{ base: 10, md: 16 }}>
              <Heading 
                as="h2" 
                size={{ base: "xl", md: "2xl" }} 
                textAlign="center"
                color={colorMode === 'dark' ? "white" : "gray.800"}
              >
                {t('features.title')}
              </Heading>
              <Text 
                fontSize={{ base: "lg", md: "xl" }} 
                textAlign="center" 
                maxW="800px"
                color={colorMode === 'dark' ? "gray.300" : "gray.600"}
              >
                {t('features.subtitle')}
              </Text>
            </VStack>

            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={8}>
              <FeatureCard 
                icon={FaFilter} 
                title={t('features.smartEmailProcessing.title')} 
                description={t('features.smartEmailProcessing.description')} 
                link="/docs/email-processing" 
              />
              <FeatureCard 
                icon={FaBrain} 
                title={t('features.aiPoweredKnowledgeExtraction.title')} 
                description={t('features.aiPoweredKnowledgeExtraction.description')} 
                link="/docs/ai-analysis" 
              />
              <FeatureCard 
                icon={FaDatabase} 
                title={t('features.centralizedKnowledgeBase.title')} 
                description={t('features.centralizedKnowledgeBase.description')} 
                link="/docs/knowledge-base" 
              />
              <FeatureCard 
                icon={FaLock} 
                title={t('features.enterpriseGradeSecurity.title')} 
                description={t('features.enterpriseGradeSecurity.description')} 
                link="/docs/secure-authentication" 
              />
              <FeatureCard 
                icon={FaRobot} 
                title={t('features.aiAssistantTraining.title')} 
                description={t('features.aiAssistantTraining.description')} 
                link="/docs/ai-training" 
              />
              <FeatureCard 
                icon={FaSearch} 
                title={t('features.powerfulSearchCapabilities.title')} 
                description={t('features.powerfulSearchCapabilities.description')} 
                link="/docs/smart-filtering" 
              />
            </SimpleGrid>
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
                  {t('useCases.transformingWorkAcrossDepartments')}
                </Heading>
                <Text fontSize={{ base: "md", md: "lg" }} maxW="800px" color={colorMode === 'dark' ? "whiteAlpha.900" : "gray.600"}>
                  {t('useCases.seeHowTeamsBenefit')}
                </Text>
              </VStack>

              <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={{ base: 6, md: 8 }}>
                <UseCaseCard
                  sector={t('useCases.hrDepartments')}
                  title={t('useCases.streamlinedEmployeeSupport.title')}
                  description={t('useCases.streamlinedEmployeeSupport.description')}
                />

                <UseCaseCard
                  sector={t('useCases.administrativeTeams')}
                  title={t('useCases.efficientOfficeManagement.title')}
                  description={t('useCases.efficientOfficeManagement.description')}
                />

                <UseCaseCard
                  sector={t('useCases.financeDepartments')}
                  title={t('useCases.consistentFinancialCommunication.title')}
                  description={t('useCases.consistentFinancialCommunication.description')}
                />

                <UseCaseCard
                  sector={t('useCases.salesTeams')}
                  title={t('useCases.enhancedClientCommunication.title')}
                  description={t('useCases.enhancedClientCommunication.description')}
                />

                <UseCaseCard
                  sector={t('useCases.consultingAgencies')}
                  title={t('useCases.clientKnowledgePreservation.title')}
                  description={t('useCases.clientKnowledgePreservation.description')}
                />

                <UseCaseCard
                  sector={t('useCases.financialServices')}
                  title={t('useCases.structuredDealRecords.title')}
                  description={t('useCases.structuredDealRecords.description')}
                />
              </SimpleGrid>
            </VStack>
          </Container>
        </Box>

        {/* CTA Section */}
        {!isAuthenticated && (
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
                  {t('cta.readyToFreeYourTeam')}
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
                  {t('cta.takeTheFirstStep')}
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
                  {t('cta.getStartedNow')}
                </Button>
              </VStack>
            </Container>
          </Box>
        )}

        {/* Footer */}
        <Box py={{ base: 8, md: 12 }} px={{ base: 4, md: 8 }} color={colorMode === 'dark' ? "whiteAlpha.800" : "gray.600"} position="relative" zIndex="1">
          <Container maxW="1400px">
            <Stack direction={{ base: 'column', md: 'row' }} justify="space-between" align={{ base: 'center', md: 'flex-start' }} spacing={{ base: 6, md: 0 }}>
              <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2}>
                <Heading size={{ base: "sm", md: "md" }} color={colorMode === 'dark' ? "white" : "gray.800"}>{t('app.name')}</Heading>
                <Text fontSize="sm" textAlign={{ base: 'center', md: 'left' }}>{t('footer.copyright')}</Text>
              </VStack>

              <Stack 
                direction={{ base: 'column', sm: 'row' }} 
                spacing={{ base: 3, md: 6 }}
                align="center"
                flexWrap="wrap"
                justify={{ base: 'center', md: 'flex-end' }}
                mt={{ base: 4, md: 0 }}
              >
                <ChakraLink as={RouterLink} to="/docs" _hover={{ color: colorMode === 'dark' ? 'neon.blue' : 'blue.500' }}>{t('footer.documentation')}</ChakraLink>
                <ChakraLink as={RouterLink} to="/support" _hover={{ color: colorMode === 'dark' ? 'neon.blue' : 'blue.500' }}>{t('footer.support')}</ChakraLink>
                <ChakraLink href="#" _hover={{ color: colorMode === 'dark' ? 'neon.blue' : 'blue.500' }}>{t('footer.privacyPolicy')}</ChakraLink>
                <ChakraLink href="#" _hover={{ color: colorMode === 'dark' ? 'neon.blue' : 'blue.500' }}>{t('footer.termsOfService')}</ChakraLink>
              </Stack>
            </Stack>
          </Container>
        </Box>
      </Box>
    </>
  );
};

// Feature Card Component
const FeatureCard = ({ icon, title, description, link }: {
  icon: React.ComponentType,
  title: string,
  description: string,
  link: string
}) => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Box
      bg={colorMode === 'dark' ? "rgba(255, 255, 255, 0.05)" : "white"}
      borderRadius="lg"
      p={6}
      boxShadow="md"
      transition="all 0.3s"
      _hover={{ transform: "translateY(-5px)", boxShadow: "lg" }}
      height="100%"
      display="flex"
      flexDirection="column"
    >
      <Icon as={icon} boxSize={10} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mb={4} />
      <Heading as="h3" size="md" mb={3} color={colorMode === 'dark' ? "white" : "gray.800"}>
        {title}
      </Heading>
      <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"} mb={4} flex="1">
        {description}
      </Text>
      <ChakraLink as={RouterLink} to={link} color="text.highlight" fontWeight="bold">
        {t('features.learnMore')}
      </ChakraLink>
    </Box>
  );
};

// Use Case Card Component
const UseCaseCard = ({ sector, title, description }: {
  sector: string,
  title: string,
  description: string
}) => {
  const { colorMode } = useColorMode();
  
  return (
    <Box
      bg={colorMode === 'dark' ? "rgba(255, 255, 255, 0.05)" : "white"}
      borderRadius="lg"
      p={6}
      boxShadow="md"
      transition="all 0.3s"
      _hover={{ transform: "translateY(-5px)", boxShadow: "lg" }}
      height="100%"
    >
      <Badge colorScheme="blue" mb={2} px={2} py={1} borderRadius="full" fontSize="xs">
        {sector}
      </Badge>
      <Heading as="h3" size="md" mb={3} color={colorMode === 'dark' ? "white" : "gray.800"}>
        {title}
      </Heading>
      <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"}>
        {description}
      </Text>
    </Box>
  );
};

export default SignIn;
