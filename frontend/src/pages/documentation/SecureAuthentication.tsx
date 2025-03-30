import React from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  HStack,
  Icon,
  Divider,
  List,
  ListItem,
  ListIcon,
  Code,
  Alert,
  AlertIcon,
  SimpleGrid,
  Card,
  CardBody,
  Flex,
  useColorMode
} from '@chakra-ui/react';
import { FaLock, FaShieldAlt, FaKey, FaUserShield, FaCheckCircle } from 'react-icons/fa';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';
import { useTranslation } from 'react-i18next';

// Security Feature Card Component
const SecurityFeatureCard = ({ 
  icon, 
  title, 
  description
}: { 
  icon: any, 
  title: string, 
  description: string
}) => {
  const { colorMode } = useColorMode();
  
  return (
    <Card 
      bg="bg.secondary" 
      borderRadius="lg" 
      border="1px solid"
      borderColor="border.primary"
      overflow="hidden"
      transition="all 0.3s"
      _hover={{ 
        transform: 'translateY(-5px)', 
        boxShadow: 'xl' 
      }}
    >
      <CardBody>
        <HStack spacing={4} align="flex-start">
          <Flex
            w="50px"
            h="50px"
            bg={colorMode === 'dark' ? "gray.900" : "gray.100"}
            color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
            borderRadius="lg"
            justify="center"
            align="center"
          >
            <Icon as={icon} w={6} h={6} />
          </Flex>
          <Box>
            <Heading size="sm" mb={1} color="text.primary">{title}</Heading>
            <Text color="text.secondary">{description}</Text>
          </Box>
        </HStack>
      </CardBody>
    </Card>
  );
};

const SecureAuthentication: React.FC = () => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Box bg="bg.primary" minH="100vh" color="text.primary">
      <PageBanner 
        title={t('documentation.sections.secureAuthentication.title')}
        subtitle={t('documentation.sections.secureAuthentication.subtitle')}
        gradient={colorMode === 'dark' 
          ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
          : "linear(to-r, brand.600, brand.500, brand.400)"
        }
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaLock} w={8} h={8} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
            <Heading 
              size="xl" 
              bgGradient={colorMode === 'dark' 
                ? "linear(to-r, neon.blue, neon.purple)"
                : "linear(to-r, brand.600, brand.400)"
              }
              bgClip="text"
            >
              {t('documentation.sections.secureAuthentication.heading')}
            </Heading>
          </HStack>
          
          <Text fontSize="lg" color="text.secondary">
            {t('documentation.sections.secureAuthentication.description')}
          </Text>
          
          <Divider borderColor="border.primary" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.secureAuthentication.howItWorksTitle')}</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.secureAuthentication.oauth2Title')}</strong> {t('documentation.sections.secureAuthentication.oauth2Description')}</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.secureAuthentication.microsoftIdentityTitle')}</strong> {t('documentation.sections.secureAuthentication.microsoftIdentityDescription')}</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.secureAuthentication.tokenBasedAuthenticationTitle')}</strong> {t('documentation.sections.secureAuthentication.tokenBasedAuthenticationDescription')}</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.secureAuthentication.permissionScopingTitle')}</strong> {t('documentation.sections.secureAuthentication.permissionScopingDescription')}</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="bg.info" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                {t('documentation.sections.secureAuthentication.authenticationInfo')}
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.secureAuthentication.requestedPermissionsTitle')}</Heading>
                <Code p={3} borderRadius="md" bg="bg.secondary" color="text.primary" display="block" whiteSpace="pre">
{`Mail.Read               // ${t('documentation.sections.secureAuthentication.mailReadDescription')}
Mail.ReadBasic           // ${t('documentation.sections.secureAuthentication.mailReadBasicDescription')}
User.Read                // ${t('documentation.sections.secureAuthentication.userReadDescription')}
offline_access           // ${t('documentation.sections.secureAuthentication.offlineAccessDescription')}`}
                </Code>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.secureAuthentication.securityFeaturesTitle')}</Heading>
              
              <SimpleGrid columns={1} spacing={4}>
                <SecurityFeatureCard 
                  icon={FaShieldAlt} 
                  title={t('documentation.sections.secureAuthentication.endToEndEncryptionTitle')}
                  description={t('documentation.sections.secureAuthentication.endToEndEncryptionDescription')}
                />
                
                <SecurityFeatureCard 
                  icon={FaKey} 
                  title={t('documentation.sections.secureAuthentication.tokenRefreshManagementTitle')}
                  description={t('documentation.sections.secureAuthentication.tokenRefreshManagementDescription')}
                />
                
                <SecurityFeatureCard 
                  icon={FaUserShield} 
                  title={t('documentation.sections.secureAuthentication.roleBasedAccessControlTitle')}
                  description={t('documentation.sections.secureAuthentication.roleBasedAccessControlDescription')}
                />
                
                <SecurityFeatureCard 
                  icon={FaLock} 
                  title={t('documentation.sections.secureAuthentication.automaticSessionTimeoutsTitle')}
                  description={t('documentation.sections.secureAuthentication.automaticSessionTimeoutsDescription')}
                />
              </SimpleGrid>
              
              <Alert status="warning" bg="bg.warning" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "yellow.300" : "yellow.500"} />
                {t('documentation.sections.secureAuthentication.enterpriseDeploymentsInfo')}
              </Alert>
            </VStack>
          </SimpleGrid>
          
          {/* Authentication Flow Diagram */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.secureAuthentication.authenticationFlowTitle')}</Heading>
            
            <Box 
              p={6} 
              bg="bg.secondary" 
              borderRadius="lg" 
              borderWidth="1px" 
              borderColor="border.primary"
            >
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Box textAlign="center" p={4} bg="bg.accent" borderRadius="md">
                    <Text fontWeight="bold" color="text.primary">{t('documentation.sections.secureAuthentication.user')}</Text>
                  </Box>
                  <Icon as={FaLock} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                  <Box textAlign="center" p={4} bg="bg.accent" borderRadius="md">
                    <Text fontWeight="bold" color="text.primary">{t('documentation.sections.secureAuthentication.ourApp')}</Text>
                  </Box>
                  <Icon as={FaLock} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                  <Box textAlign="center" p={4} bg="bg.accent" borderRadius="md">
                    <Text fontWeight="bold" color="text.primary">{t('documentation.sections.secureAuthentication.microsoftIdentity')}</Text>
                  </Box>
                </HStack>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">{t('documentation.sections.secureAuthentication.authenticationFlowStep1')}</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">{t('documentation.sections.secureAuthentication.authenticationFlowStep2')}</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">{t('documentation.sections.secureAuthentication.authenticationFlowStep3')}</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">{t('documentation.sections.secureAuthentication.authenticationFlowStep4')}</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">{t('documentation.sections.secureAuthentication.authenticationFlowStep5')}</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">{t('documentation.sections.secureAuthentication.authenticationFlowStep6')}</Text>
                </Box>
              </VStack>
            </Box>
          </Box>
          
          {/* FAQ Section */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.secureAuthentication.faqTitle')}</Heading>
            
            <VStack spacing={4} align="stretch">
              <Box p={4} bg="bg.secondary" borderRadius="md">
                <Heading size="sm" mb={2} color="text.primary">{t('documentation.sections.secureAuthentication.faq1Title')}</Heading>
                <Text color="text.primary">{t('documentation.sections.secureAuthentication.faq1Description')}</Text>
              </Box>
              
              <Box p={4} bg="bg.secondary" borderRadius="md">
                <Heading size="sm" mb={2} color="text.primary">{t('documentation.sections.secureAuthentication.faq2Title')}</Heading>
                <Text color="text.primary">{t('documentation.sections.secureAuthentication.faq2Description')}</Text>
              </Box>
              
              <Box p={4} bg="bg.secondary" borderRadius="md">
                <Heading size="sm" mb={2} color="text.primary">{t('documentation.sections.secureAuthentication.faq3Title')}</Heading>
                <Text color="text.primary">{t('documentation.sections.secureAuthentication.faq3Description')}</Text>
              </Box>
              
              <Box p={4} bg="bg.secondary" borderRadius="md">
                <Heading size="sm" mb={2} color="text.primary">{t('documentation.sections.secureAuthentication.faq4Title')}</Heading>
                <Text color="text.primary">{t('documentation.sections.secureAuthentication.faq4Description')}</Text>
              </Box>
            </VStack>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

export default SecureAuthentication;
