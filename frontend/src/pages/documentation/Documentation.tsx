import React from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  Divider,
  SimpleGrid,
  Card,
  CardBody,
  Icon,
  Button,
  Flex,
  useColorMode
} from '@chakra-ui/react';
import { FaDatabase, FaLock, FaFilter, FaChartLine, FaArrowRight } from 'react-icons/fa';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';
import { Link as RouterLink } from 'react-router-dom';

// Documentation Card Component
const DocumentationCard = ({ 
  icon, 
  title, 
  description, 
  path
}: { 
  icon: any, 
  title: string, 
  description: string,
  path: string
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
          <Text color="text.secondary" className="card-text">{description}</Text>
          
          <Button 
            as={RouterLink} 
            to={path} 
            rightIcon={<FaArrowRight />} 
            colorScheme={colorMode === 'dark' ? "cyan" : "blue"}
            variant={colorMode === 'dark' ? "solid" : "solid"}
            size="sm" 
            alignSelf="flex-end"
          >
            Learn More
          </Button>
        </VStack>
      </CardBody>
    </Card>
  );
};

// Resource Card Component
const ResourceCard = ({ 
  title, 
  description
}: { 
  title: string, 
  description: string
}) => {
  return (
    <Box
      p={5}
      bg="bg.secondary"
      borderRadius="lg"
      border="1px solid" 
      borderColor="border.primary"
      transition="all 0.3s"
      _hover={{ 
        bg: "bg.accent",
        borderColor: "border.primary"
      }}
    >
      <VStack align="flex-start" spacing={2}>
        <Heading size="sm" color="text.primary">{title}</Heading>
        <Text fontSize="sm" color="text.secondary" className="card-text">{description}</Text>
      </VStack>
    </Box>
  );
};

const Documentation: React.FC = () => {
  // We'll use the useColorMode hook for theme-aware styling
  const { colorMode } = useColorMode();
  
  return (
    <Box 
      bg="bg.primary" 
      minH="100vh" 
      color="text.primary"
      className={`documentation-page ${colorMode}`}
    >
      <PageBanner 
        title="Documentation" 
        subtitle="Welcome to the Email Knowledge Base documentation. Here you'll find detailed information about all aspects of our platform."
        gradient={colorMode === 'dark' 
          ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
          : "linear(to-r, brand.600, brand.500, brand.400)"
        }
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          <Text color="text.secondary">
            Explore comprehensive documentation covering all aspects 
            of our platform, from authentication to knowledge export.
          </Text>
          
          <Divider borderColor="border.primary" />
          
          {/* Documentation Cards */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={8}>
            <DocumentationCard 
              icon={FaLock} 
              title="Secure Authentication" 
              description="Learn about our OAuth2-based authentication system that integrates seamlessly with Microsoft 365."
              path="/docs/secure-authentication"
            />
            <DocumentationCard 
              icon={FaFilter} 
              title="Smart Filtering" 
              description="Discover how to set up intelligent email filters to capture only the most relevant communications."
              path="/docs/smart-filtering"
            />
            <DocumentationCard 
              icon={FaChartLine} 
              title="AI Analysis" 
              description="Understand how our AI analyzes and extracts knowledge from your communications."
              path="/docs/ai-analysis"
            />
            <DocumentationCard 
              icon={FaDatabase} 
              title="Knowledge Base" 
              description="Learn how to search, manage, and export your organization's knowledge repository."
              path="/docs/knowledge-base"
            />
          </SimpleGrid>
          
          <Divider borderColor="border.primary" my={4} />
          
          {/* Additional Resources */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Additional Resources</Heading>
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
              <ResourceCard 
                title="API Documentation" 
                description="Complete API reference for developers integrating with our platform."
              />
              <ResourceCard 
                title="Video Tutorials" 
                description="Step-by-step video guides for common workflows and features."
              />
              <ResourceCard 
                title="Best Practices" 
                description="Recommendations for optimizing your knowledge management process."
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="border.primary" my={4} />
          
          {/* Support Section */}
          <Box bg="bg.secondary" p={6} borderRadius="lg">
            <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" align="center">
              <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2} mb={{ base: 4, md: 0 }}>
                <Heading size="md" color="text.primary">Need Additional Help?</Heading>
                <Text color="text.secondary">Our support team is available to assist you with any questions.</Text>
              </VStack>
              <Button 
                as={RouterLink} 
                to="/support" 
                colorScheme={colorMode === 'dark' ? "cyan" : "blue"}
                variant={colorMode === 'dark' ? "solid" : "solid"}
                rightIcon={<FaArrowRight />}
              >
                Contact Support
              </Button>
            </Flex>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

export default Documentation;
