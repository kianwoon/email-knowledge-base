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
import { FaLock, FaShieldAlt, FaKey, FaUserShield, FaCheckCircle, FaExclamationTriangle } from 'react-icons/fa';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

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
        <VStack align="flex-start" spacing={4}>
          <Flex
            w="50px"
            h="50px"
            bg="bg.accent"
            color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
            borderRadius="lg"
            justify="center"
            align="center"
          >
            <Icon as={icon} w={6} h={6} />
          </Flex>
          
          <Heading size="md" color="text.primary">{title}</Heading>
          <Text color="text.secondary">{description}</Text>
        </VStack>
      </CardBody>
    </Card>
  );
};

const SecureAuthentication: React.FC = () => {
  const { colorMode } = useColorMode();
  
  return (
    <Box bg="bg.primary" minH="100vh" color="text.primary">
      <PageBanner 
        title="Enterprise-Grade Security" 
        subtitle="Keep your sensitive information protected with our robust security infrastructure and compliance measures."
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
              Secure Authentication
            </Heading>
          </HStack>
          
          <Text fontSize="lg" color="text.secondary">
            Our platform uses enterprise-grade security protocols to ensure your email data remains protected
            while providing seamless access to authorized users.
          </Text>
          
          <Divider borderColor="border.primary" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>How It Works</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>OAuth 2.0 Protocol:</strong> Industry-standard authorization framework that enables secure access without sharing passwords.</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Microsoft Identity Platform:</strong> Integrates with Microsoft's authentication services for Outlook access.</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Token-Based Authentication:</strong> Uses secure tokens with limited lifespans rather than persistent credentials.</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Permission Scoping:</strong> Requests only the specific permissions needed (read-only by default).</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="bg.info" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                All authentication is handled through Microsoft's secure login page - we never see or store your password.
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Requested Permissions</Heading>
                <Code p={3} borderRadius="md" bg="bg.secondary" color="text.primary" display="block" whiteSpace="pre">
{`Mail.Read               // Read user mail
Mail.ReadBasic           // Read user mail
User.Read                // Sign in and read user profile
offline_access           // Maintain access permission`}
                </Code>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Security Features</Heading>
              
              <SimpleGrid columns={1} spacing={4}>
                <SecurityFeatureCard 
                  icon={FaShieldAlt}
                  title="End-to-End Encryption"
                  description="All data is encrypted in transit using TLS 1.2+ protocols"
                />
                
                <SecurityFeatureCard 
                  icon={FaKey}
                  title="Token Refresh Management"
                  description="Secure handling of refresh tokens with automatic rotation"
                />
                
                <SecurityFeatureCard 
                  icon={FaUserShield}
                  title="Role-Based Access Control"
                  description="Granular permissions based on user roles within your organization"
                />
                
                <SecurityFeatureCard 
                  icon={FaExclamationTriangle}
                  title="Automatic Session Timeouts"
                  description="Sessions expire after periods of inactivity for added security"
                />
              </SimpleGrid>
              
              <Alert status="warning" bg="bg.warning" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "yellow.300" : "yellow.500"} />
                For enterprise deployments, we support custom security policies and SSO integration.
              </Alert>
            </VStack>
          </SimpleGrid>
          
          <Divider borderColor="border.primary" />
          
          {/* Authentication Flow Diagram */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Authentication Flow</Heading>
            
            <Box 
              p={6} 
              bg="bg.secondary" 
              borderRadius="lg" 
              border="1px solid" 
              borderColor="border.primary"
            >
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Box textAlign="center" p={4} bg="bg.accent" borderRadius="md">
                    <Text fontWeight="bold" color="text.primary">User</Text>
                  </Box>
                  <Icon as={FaLock} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                  <Box textAlign="center" p={4} bg="bg.accent" borderRadius="md">
                    <Text fontWeight="bold" color="text.primary">Our App</Text>
                  </Box>
                  <Icon as={FaLock} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                  <Box textAlign="center" p={4} bg="bg.accent" borderRadius="md">
                    <Text fontWeight="bold" color="text.primary">Microsoft Identity</Text>
                  </Box>
                </HStack>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">1. User initiates login → App redirects to Microsoft login page</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">2. User authenticates with Microsoft credentials</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">3. Microsoft validates credentials and requests permission consent</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">4. User grants consent → Microsoft issues authorization code</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">5. App exchanges code for access and refresh tokens</Text>
                </Box>
                
                <Box p={4} bg="bg.secondary" borderRadius="md">
                  <Text color="text.primary">6. App uses access token to request email data from Microsoft Graph API</Text>
                </Box>
              </VStack>
            </Box>
          </Box>
          
          <Divider borderColor="border.primary" />
          
          {/* FAQ Section */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Frequently Asked Questions</Heading>
            
            <VStack spacing={4} align="stretch">
              <Box p={4} bg="bg.secondary" borderRadius="md">
                <Heading size="sm" mb={2} color="text.primary">Can the app read all my emails?</Heading>
                <Text color="text.primary">The app only accesses emails that match your specified filters. By default, it requests read-only permissions to your mailbox.</Text>
              </Box>
              
              <Box p={4} bg="bg.secondary" borderRadius="md">
                <Heading size="sm" mb={2} color="text.primary">What happens if I revoke access?</Heading>
                <Text color="text.primary">You can revoke access at any time through your Microsoft account settings. This immediately prevents the app from accessing any new data.</Text>
              </Box>
              
              <Box p={4} bg="bg.secondary" borderRadius="md">
                <Heading size="sm" mb={2} color="text.primary">Does the app store my Microsoft password?</Heading>
                <Text color="text.primary">No. Authentication is handled entirely by Microsoft's identity platform. We never see, access, or store your password.</Text>
              </Box>
              
              <Box p={4} bg="bg.secondary" borderRadius="md">
                <Heading size="sm" mb={2} color="text.primary">How long do access tokens last?</Heading>
                <Text color="text.primary">Access tokens typically expire after 1 hour. The app securely manages refresh tokens to maintain access without requiring you to log in again.</Text>
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
