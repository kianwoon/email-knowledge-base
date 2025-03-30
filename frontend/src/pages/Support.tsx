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
import Footer from '../components/Footer';
import PageBanner from '../components/PageBanner';

const Support: React.FC = () => {
  return (
    <Box bg="bg.primary" minH="100vh" color="text.primary">
      <PageBanner 
        title="Support & Contact" 
        subtitle="Our support team is ready to help you get the most out of our email knowledge base solution."
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Introduction Text */}
          <Text fontSize="lg">
            Have questions or need assistance with our Email Knowledge Base platform? 
            Our support team is ready to help you get the most out of our solution.
          </Text>
          
          <Divider borderColor="border.primary" />
          
          {/* Contact Information */}
          <Box>
            <Heading size="md" color="text.highlight" mb={6}>Contact Information</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={8}>
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaBuilding} color="text.highlight" w={6} h={6} />
                      <Heading size="md" color="text.primary">Company Information</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text fontWeight="bold" color="text.primary">Beyondsoft Singapore</Text>
                      <Text color="text.secondary">BFSI Delivery Service, Asia Pacific Business Group</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaEnvelope} color="text.highlight" w={6} h={6} />
                      <Heading size="md" color="text.primary">Email Support</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Link href="mailto:BFSI_SG@beyondsoft.com" color="text.highlight" fontWeight="bold">
                        BFSI_SG@beyondsoft.com
                      </Link>
                      <Text color="text.secondary">For technical support, sales inquiries, and general questions</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaMapMarkerAlt} color="text.highlight" w={6} h={6} />
                      <Heading size="md" color="text.primary">Office Location</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text color="text.primary">38 Beach Road, #20-11</Text>
                      <Text color="text.primary">South Beach Tower</Text>
                      <Text color="text.primary">Singapore 189767</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaGlobe} color="text.highlight" w={6} h={6} />
                      <Heading size="md" color="text.primary">Business Hours</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text color="text.primary">Monday - Friday: 9:00 AM - 6:00 PM SGT</Text>
                      <Text color="text.primary">Weekend: Closed</Text>
                      <Text color="text.primary">Email support available 24/7</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="border.primary" />
          
          {/* Support Options */}
          <Box>
            <Heading size="md" color="text.highlight" mb={6}>Support Options</Heading>
            
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
            bg="bg.secondary" 
            p={6} 
            borderRadius="lg" 
            border="1px solid"
            borderColor="border.primary"
            mt={4}
          >
            <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" align="center">
              <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2} mb={{ base: 4, md: 0 }}>
                <Heading size="md" color="text.primary">Ready to get started?</Heading>
                <Text color="text.secondary">Contact our team today to learn more about our Email Knowledge Base solution.</Text>
              </VStack>
              
              <Button 
                as={Link} 
                href="mailto:BFSI_SG@beyondsoft.com" 
                colorScheme="blue"
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
      bg="bg.tertiary"
      borderRadius="lg"
      border="1px solid"
      borderColor="border.primary"
      transition="all 0.3s"
      _hover={{ 
        bg: 'bg.tertiaryHover',
        borderColor: 'border.primaryHover'
      }}
    >
      <VStack align="flex-start" spacing={2}>
        <Heading size="sm" color="text.primary">{title}</Heading>
        <Text fontSize="sm" color="text.secondary">{description}</Text>
      </VStack>
    </Box>
  );
};

export default Support;
