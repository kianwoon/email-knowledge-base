import React from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  HStack,
  Icon,
  SimpleGrid,
  Card,
  CardBody,
  Button,
  Divider,
  Flex,
} from '@chakra-ui/react';
import { Link } from 'react-router-dom';
import { FaLock, FaFilter, FaBrain, FaDatabase, FaBook, FaArrowRight } from 'react-icons/fa';
import DocumentationHeader from '../../components/DocumentationHeader';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

const Documentation: React.FC = () => {
  return (
    <Box bg="#050a30" minH="100vh" color="white">
      <DocumentationHeader />
      <PageBanner 
        title="Documentation" 
        subtitle="Welcome to the Email Knowledge Base documentation. Here you'll find detailed information about all aspects of our platform."
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaBook} w={8} h={8} color="neon.blue" />
            <Heading 
              size="xl" 
              bgGradient="linear(to-r, #3ef2f2, #f72585)" 
              bgClip="text"
            >
              Documentation
            </Heading>
          </HStack>
          
          <Text fontSize="lg">
            Welcome to the Email Knowledge Base documentation. Here you'll find detailed information about all aspects
            of our platform, from authentication to knowledge export.
          </Text>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Documentation Cards */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={8}>
            <DocumentationCard 
              icon={FaLock}
              title="Secure Authentication"
              description="Learn about our OAuth2 integration with Microsoft, security protocols, and data protection measures."
              path="/docs/secure-auth"
            />
            
            <DocumentationCard 
              icon={FaFilter}
              title="Smart Filtering"
              description="Discover how to efficiently filter emails by folder, date, sender, keywords, and more."
              path="/docs/smart-filter"
            />
            
            <DocumentationCard 
              icon={FaBrain}
              title="AI Analysis"
              description="Explore our AI capabilities for content classification, PII detection, and knowledge extraction."
              path="/docs/ai-analysis"
            />
            
            <DocumentationCard 
              icon={FaDatabase}
              title="Knowledge Base"
              description="Learn about our vector database technology, search capabilities, and integration options."
              path="/docs/knowledge-base"
            />
          </SimpleGrid>
          
          <Divider borderColor="whiteAlpha.300" my={4} />
          
          {/* Additional Resources */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Additional Resources</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <ResourceCard 
                title="API Reference"
                description="Complete API documentation for developers"
              />
              
              <ResourceCard 
                title="Tutorial Videos"
                description="Step-by-step guides for common workflows"
              />
              
              <ResourceCard 
                title="Best Practices"
                description="Tips for optimizing your knowledge base"
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" my={4} />
          
          {/* Support Section */}
          <Box bg="rgba(255, 255, 255, 0.05)" p={6} borderRadius="lg">
            <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" align="center">
              <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2} mb={{ base: 4, md: 0 }}>
                <Heading size="md">Need Additional Help?</Heading>
                <Text>Our support team is available to assist you with any questions.</Text>
              </VStack>
              
              <HStack spacing={4}>
                <Button variant="glass">Contact Support</Button>
                <Button variant="neon">Schedule Demo</Button>
              </HStack>
            </Flex>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

// Documentation Card Component
const DocumentationCard = ({ icon, title, description, path }: { 
  icon: any, 
  title: string, 
  description: string,
  path: string
}) => {
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
        <VStack align="flex-start" spacing={4}>
          <Flex
            w="50px"
            h="50px"
            bg="rgba(62, 242, 242, 0.2)"
            color="neon.blue"
            borderRadius="lg"
            justify="center"
            align="center"
            boxShadow="0 0 10px rgba(62, 242, 242, 0.3)"
          >
            <Icon as={icon} w={6} h={6} />
          </Flex>
          
          <Heading size="md" color="white">{title}</Heading>
          <Text color="white" className="card-text">{description}</Text>
          
          <Button 
            as={Link} 
            to={path}
            variant="link" 
            color="neon.blue" 
            rightIcon={<Icon as={FaArrowRight} />}
            _hover={{ textDecoration: 'none', color: 'neon.pink' }}
          >
            Read More
          </Button>
        </VStack>
      </CardBody>
    </Card>
  );
};

// Resource Card Component
const ResourceCard = ({ title, description }: { title: string, description: string }) => {
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
        <Text fontSize="sm" color="white" className="card-text">{description}</Text>
      </VStack>
    </Box>
  );
};

export default Documentation;
