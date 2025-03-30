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
  Flex
} from '@chakra-ui/react';
import { FaLock, FaShieldAlt, FaKey, FaUserShield, FaCheckCircle, FaExclamationTriangle } from 'react-icons/fa';
import DocumentationHeader from '../../components/DocumentationHeader';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

const SecureAuthentication: React.FC = () => {
  return (
    <Box bg="#050a30" minH="100vh" color="white">
      <DocumentationHeader />
      <PageBanner 
        title="Enterprise-Grade Security" 
        subtitle="Keep your sensitive information protected with our robust security infrastructure and compliance measures."
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaLock} w={8} h={8} color="neon.blue" />
            <Heading 
              size="xl" 
              bgGradient="linear(to-r, #3ef2f2, #f72585)" 
              bgClip="text"
            >
              Secure Authentication
            </Heading>
          </HStack>
          
          <Text fontSize="lg">
            Our platform uses enterprise-grade security protocols to ensure your email data remains protected
            while providing seamless access to authorized users.
          </Text>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color="neon.blue">How It Works</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color="neon.blue" />
                    <Text><strong>OAuth 2.0 Protocol:</strong> Industry-standard authorization framework that enables secure access without sharing passwords.</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color="neon.blue" />
                    <Text><strong>Microsoft Identity Platform:</strong> Integrates with Microsoft's authentication services for Outlook access.</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color="neon.blue" />
                    <Text><strong>Token-Based Authentication:</strong> Uses secure tokens with limited lifespans rather than persistent credentials.</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCheckCircle} color="neon.blue" />
                    <Text><strong>Permission Scoping:</strong> Requests only the specific permissions needed (read-only by default).</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="rgba(62, 242, 242, 0.1)" color="white" borderRadius="md">
                <AlertIcon color="neon.blue" />
                All authentication is handled through Microsoft's secure login page - we never see or store your password.
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color="neon.blue">Requested Permissions</Heading>
                <Code p={3} borderRadius="md" bg="whiteAlpha.100" color="white" display="block" whiteSpace="pre">
{`Mail.Read               // Read user mail
Mail.ReadBasic           // Read user mail
User.Read                // Sign in and read user profile
offline_access           // Maintain access permission`}
                </Code>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color="neon.blue">Security Features</Heading>
              
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
              
              <Alert status="warning" bg="rgba(247, 37, 133, 0.1)" color="white" borderRadius="md">
                <AlertIcon color="neon.pink" />
                For enterprise deployments, we support custom security policies and SSO integration.
              </Alert>
            </VStack>
          </SimpleGrid>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Authentication Flow Diagram */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Authentication Flow</Heading>
            
            <Box 
              p={6} 
              bg="rgba(255, 255, 255, 0.05)" 
              borderRadius="lg" 
              border="1px solid rgba(255, 255, 255, 0.1)"
            >
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Box textAlign="center" p={4} bg="rgba(62, 242, 242, 0.1)" borderRadius="md">
                    <Text fontWeight="bold">User</Text>
                  </Box>
                  <Icon as={FaLock} />
                  <Box textAlign="center" p={4} bg="rgba(62, 242, 242, 0.1)" borderRadius="md">
                    <Text fontWeight="bold">Our App</Text>
                  </Box>
                  <Icon as={FaLock} />
                  <Box textAlign="center" p={4} bg="rgba(62, 242, 242, 0.1)" borderRadius="md">
                    <Text fontWeight="bold">Microsoft Identity</Text>
                  </Box>
                </HStack>
                
                <Box p={4} bg="rgba(255, 255, 255, 0.03)" borderRadius="md">
                  <Text>1. User initiates login → App redirects to Microsoft login page</Text>
                </Box>
                
                <Box p={4} bg="rgba(255, 255, 255, 0.03)" borderRadius="md">
                  <Text>2. User authenticates with Microsoft credentials</Text>
                </Box>
                
                <Box p={4} bg="rgba(255, 255, 255, 0.03)" borderRadius="md">
                  <Text>3. Microsoft validates credentials and requests permission consent</Text>
                </Box>
                
                <Box p={4} bg="rgba(255, 255, 255, 0.03)" borderRadius="md">
                  <Text>4. User grants consent → Microsoft issues authorization code</Text>
                </Box>
                
                <Box p={4} bg="rgba(255, 255, 255, 0.03)" borderRadius="md">
                  <Text>5. App exchanges code for access and refresh tokens</Text>
                </Box>
                
                <Box p={4} bg="rgba(255, 255, 255, 0.03)" borderRadius="md">
                  <Text>6. App uses access token to request email data from Microsoft Graph API</Text>
                </Box>
              </VStack>
            </Box>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* FAQ Section */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Frequently Asked Questions</Heading>
            
            <VStack spacing={4} align="stretch">
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Can the app read all my emails?</Heading>
                <Text>The app only accesses emails that match your specified filters. By default, it requests read-only permissions to your mailbox.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>What happens if I revoke access?</Heading>
                <Text>You can revoke access at any time through your Microsoft account settings. This immediately prevents the app from accessing any new data.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Does the app store my Microsoft password?</Heading>
                <Text>No. Authentication is handled entirely by Microsoft's identity platform. We never see, access, or store your password.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>How long do access tokens last?</Heading>
                <Text>Access tokens typically expire after 1 hour. The app securely manages refresh tokens to maintain access without requiring you to log in again.</Text>
              </Box>
            </VStack>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

// Security Feature Card Component
const SecurityFeatureCard = ({ icon, title, description }: { icon: any, title: string, description: string }) => {
  return (
    <Card 
      bg="rgba(255, 255, 255, 0.05)" 
      borderRadius="lg" 
      border="1px solid rgba(255, 255, 255, 0.1)"
      overflow="hidden"
      transition="all 0.3s"
      _hover={{ 
        transform: 'translateY(-5px)', 
        boxShadow: '0 8px 30px rgba(62, 242, 242, 0.2)',
        borderColor: 'rgba(62, 242, 242, 0.3)'
      }}
    >
      <CardBody>
        <HStack spacing={4}>
          <Flex
            w="40px"
            h="40px"
            bg="rgba(62, 242, 242, 0.2)"
            color="neon.blue"
            borderRadius="md"
            justify="center"
            align="center"
            boxShadow="0 0 10px rgba(62, 242, 242, 0.3)"
          >
            <Icon as={icon} w={5} h={5} />
          </Flex>
          
          <VStack align="flex-start" spacing={0}>
            <Heading size="sm">{title}</Heading>
            <Text fontSize="sm" color="whiteAlpha.800">{description}</Text>
          </VStack>
        </HStack>
      </CardBody>
    </Card>
  );
};

export default SecureAuthentication;
