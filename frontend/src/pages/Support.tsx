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
  Link,
  Button,
  Card,
  CardBody,
  SimpleGrid,
  Flex,
} from '@chakra-ui/react';
import { FaEnvelope, FaMapMarkerAlt, FaBuilding, FaGlobe } from 'react-icons/fa';
import DocumentationHeader from '../components/DocumentationHeader';
import Footer from '../components/Footer';
import PageBanner from '../components/PageBanner';

const Support: React.FC = () => {
  return (
    <Box bg="#050a30" minH="100vh" color="white">
      <DocumentationHeader />
      <PageBanner 
        title="Support & Contact" 
        subtitle="Our support team is ready to help you get the most out of our email knowledge base solution."
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaEnvelope} w={8} h={8} color="neon.blue" />
            <Heading 
              size="xl" 
              bgGradient="linear(to-r, #3ef2f2, #f72585)" 
              bgClip="text"
            >
              Support & Contact
            </Heading>
          </HStack>
          
          <Text fontSize="lg">
            Have questions or need assistance with our Email Knowledge Base platform? 
            Our support team is ready to help you get the most out of our solution.
          </Text>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Contact Information */}
          <Box>
            <Heading size="md" color="neon.blue" mb={6}>Contact Information</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={8}>
              <Card 
                bg="rgba(255, 255, 255, 0.05)" 
                borderRadius="lg" 
                border="1px solid rgba(255, 255, 255, 0.1)"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaBuilding} color="neon.blue" w={6} h={6} />
                      <Heading size="md">Company Information</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text fontWeight="bold" color="white">Beyondsoft Singapore</Text>
                      <Text color="white">BFSI Delivery Service, Asia Pacific Business Group</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="rgba(255, 255, 255, 0.05)" 
                borderRadius="lg" 
                border="1px solid rgba(255, 255, 255, 0.1)"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaEnvelope} color="neon.blue" w={6} h={6} />
                      <Heading size="md">Email Support</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Link href="mailto:BFSI_SG@beyondsoft.com" color="neon.blue" fontWeight="bold">
                        BFSI_SG@beyondsoft.com
                      </Link>
                      <Text color="white">For technical support, sales inquiries, and general questions</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="rgba(255, 255, 255, 0.05)" 
                borderRadius="lg" 
                border="1px solid rgba(255, 255, 255, 0.1)"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaMapMarkerAlt} color="neon.blue" w={6} h={6} />
                      <Heading size="md">Office Location</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text color="white">38 Beach Road, #20-11</Text>
                      <Text color="white">South Beach Tower</Text>
                      <Text color="white">Singapore 189767</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="rgba(255, 255, 255, 0.05)" 
                borderRadius="lg" 
                border="1px solid rgba(255, 255, 255, 0.1)"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaGlobe} color="neon.blue" w={6} h={6} />
                      <Heading size="md">Business Hours</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text color="white">Monday - Friday: 9:00 AM - 6:00 PM SGT</Text>
                      <Text color="white">Weekend: Closed</Text>
                      <Text color="white">Email support available 24/7</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Support Options */}
          <Box>
            <Heading size="md" color="neon.blue" mb={6}>Support Options</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <SupportOption 
                title="Technical Support" 
                description="Get help with installation, configuration, and troubleshooting."
              />
              
              <SupportOption 
                title="Product Training" 
                description="Schedule a training session for your team to maximize productivity."
              />
              
              <SupportOption 
                title="Custom Integration" 
                description="Work with our experts to integrate with your existing systems."
              />
            </SimpleGrid>
          </Box>
          
          {/* CTA */}
          <Box 
            bg="rgba(255, 255, 255, 0.05)" 
            p={6} 
            borderRadius="lg" 
            border="1px solid rgba(255, 255, 255, 0.1)"
            mt={4}
          >
            <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" align="center">
              <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2} mb={{ base: 4, md: 0 }}>
                <Heading size="md">Ready to get started?</Heading>
                <Text color="white">Contact our team today to learn more about our Email Knowledge Base solution.</Text>
              </VStack>
              
              <Button 
                as={Link} 
                href="mailto:BFSI_SG@beyondsoft.com" 
                variant="neon" 
                size="lg"
                _hover={{ textDecoration: 'none' }}
              >
                Contact Us
              </Button>
            </Flex>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

// Support Option Component
const SupportOption = ({ title, description }: { title: string, description: string }) => {
  return (
    <Box
      p={5}
      bg="rgba(255, 255, 255, 0.03)"
      borderRadius="lg"
      border="1px solid rgba(255, 255, 255, 0.1)"
      transition="all 0.3s"
      _hover={{ 
        bg: 'rgba(255, 255, 255, 0.05)',
        borderColor: 'rgba(62, 242, 242, 0.3)'
      }}
    >
      <VStack align="flex-start" spacing={2}>
        <Heading size="sm" color="white">{title}</Heading>
        <Text fontSize="sm" color="white">{description}</Text>
      </VStack>
    </Box>
  );
};

export default Support;
