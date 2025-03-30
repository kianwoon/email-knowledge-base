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
  Alert,
  AlertIcon,
  SimpleGrid,
  Card,
  CardBody,
  Flex,
  Tag,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  useColorMode
} from '@chakra-ui/react';
import { FaBrain, FaShieldAlt, FaTag, FaEye, FaLock, FaExclamationTriangle, FaChartLine } from 'react-icons/fa';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

const AIAnalysis: React.FC = () => {
  const { colorMode } = useColorMode();
  
  return (
    <Box bg="bg.primary" minH="100vh" color="text.primary">
      <PageBanner 
        title="AI-Powered Knowledge Extraction" 
        subtitle="Extract valuable insights and patterns from your communications using advanced AI algorithms."
        gradient={colorMode === 'dark' 
          ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
          : "linear(to-r, brand.600, brand.500, brand.400)"
        }
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaBrain} w={8} h={8} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
            <Heading 
              size="xl" 
              bgGradient={colorMode === 'dark' 
                ? "linear(to-r, neon.blue, neon.purple)"
                : "linear(to-r, brand.600, brand.400)"
              }
              bgClip="text"
            >
              AI Analysis
            </Heading>
          </HStack>
          
          <Text fontSize="lg" color="text.primary">
            Our advanced AI analysis engine processes your selected emails to extract valuable insights,
            classify content, and prepare knowledge for export while ensuring privacy and compliance.
          </Text>
          
          <Divider borderColor="border.primary" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>AI Capabilities</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaTag} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Smart Classification:</strong> Automatically categorizes emails by department, topic, and importance</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaShieldAlt} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>PII Detection:</strong> Identifies and flags personally identifiable information for review</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaEye} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Content Summarization:</strong> Creates concise summaries of email threads and conversations</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaLock} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Sensitivity Analysis:</strong> Evaluates content for confidentiality and compliance concerns</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaChartLine} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Knowledge Extraction:</strong> Identifies key facts, decisions, and actionable insights</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="bg.info" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                Our AI models are fine-tuned for business communications and can be customized for your organization's specific terminology and needs.
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>AI Model Specifications</Heading>
                <Card bg="bg.secondary" borderRadius="md">
                  <CardBody>
                    <SimpleGrid columns={2} spacing={4}>
                      <Stat>
                        <StatLabel color="text.secondary">Base Model</StatLabel>
                        <StatNumber fontSize="md" color="text.primary">ChatGPT-4o mini</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="text.secondary">Fine-tuning</StatLabel>
                        <StatNumber fontSize="md" color="text.primary">Business Communications</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="text.secondary">Context Window</StatLabel>
                        <StatNumber fontSize="md" color="text.primary">16K tokens</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="text.secondary">Processing Speed</StatLabel>
                        <StatNumber fontSize="md" color="text.primary">~3-5 sec/email</StatNumber>
                      </Stat>
                    </SimpleGrid>
                  </CardBody>
                </Card>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Analysis Process</Heading>
              
              <SimpleGrid columns={1} spacing={4}>
                <ProcessStepCard 
                  number="01"
                  title="Initial Content Scan"
                  description="Emails are processed to extract text, metadata, and attachment information"
                  progress={100}
                />
                
                <ProcessStepCard 
                  number="02"
                  title="PII & Sensitive Data Detection"
                  description="AI identifies personal information, confidential data, and compliance concerns"
                  progress={100}
                />
                
                <ProcessStepCard 
                  number="03"
                  title="Classification & Tagging"
                  description="Content is categorized by department, topic, priority, and knowledge value"
                  progress={100}
                />
                
                <ProcessStepCard 
                  number="04"
                  title="Knowledge Extraction"
                  description="Key facts, decisions, and insights are identified and structured"
                  progress={100}
                />
                
                <ProcessStepCard 
                  number="05"
                  title="Human Review Preparation"
                  description="Results are formatted for efficient human review and approval"
                  progress={100}
                />
              </SimpleGrid>
              
              <Alert status="warning" bg="bg.warning" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                AI analysis is designed to assist human reviewers, not replace them. All AI-generated tags and classifications can be modified during review.
              </Alert>
            </VStack>
          </SimpleGrid>
          
          <Divider borderColor="border.primary" />
          
          {/* Classification Categories */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Classification Categories</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <ClassificationCard 
                title="Department"
                description="Identifies which business unit the content relates to"
                tags={['Executive', 'Sales', 'Marketing', 'Finance', 'Legal', 'HR', 'IT', 'Operations', 'Customer Support']}
              />
              
              <ClassificationCard 
                title="Content Type"
                description="Categorizes the nature of the information"
                tags={['Policy', 'Procedure', 'Decision', 'Report', 'Analysis', 'Discussion', 'Approval', 'Request', 'Notification']}
              />
              
              <ClassificationCard 
                title="Sensitivity"
                description="Flags content requiring special handling"
                tags={['Public', 'Internal', 'Confidential', 'Restricted', 'PII', 'Financial', 'Legal', 'Strategic']}
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="border.primary" />
          
          {/* PII Detection */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>PII & Sensitive Data Detection</Heading>
            
            <Text mb={4} color="text.primary">
              Our AI system automatically identifies and flags personally identifiable information and sensitive data
              to ensure compliance with privacy regulations and company policies.
            </Text>
            
            <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={6}>
              <PIITag label="Names" />
              <PIITag label="Email Addresses" />
              <PIITag label="Phone Numbers" />
              <PIITag label="Addresses" />
              <PIITag label="SSN/ID Numbers" />
              <PIITag label="Financial Data" />
              <PIITag label="Health Information" />
              <PIITag label="Credentials" />
            </SimpleGrid>
            
            <Alert status="success" bg="bg.success" color="text.primary" borderRadius="md">
              <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
              All flagged PII is presented for human review before being processed. You can choose to redact, anonymize, or approve each instance.
            </Alert>
          </Box>
        </VStack>
      </Container>
      
      <Footer />
    </Box>
  );
};

// Process Step Card Component
const ProcessStepCard: React.FC<{ 
  number: string, 
  title: string, 
  description: string,
  progress: number
}> = ({ number, title, description, progress }) => {
  const { colorMode } = useColorMode();
  
  return (
    <Card 
      bg="bg.secondary" 
      borderRadius="md" 
      overflow="hidden"
      position="relative"
      border="1px solid"
      borderColor="border.primary"
    >
      <CardBody>
        <Flex align="center" mb={2}>
          <Box 
            w="30px" 
            h="30px" 
            borderRadius="full" 
            bg={colorMode === 'dark' ? "neon.blue" : "brand.600"}
            color="white"
            display="flex"
            alignItems="center"
            justifyContent="center"
            fontWeight="bold"
            mr={3}
          >
            {number}
          </Box>
          <Heading size="sm" color="text.primary">{title}</Heading>
        </Flex>
        <Text color="text.secondary" fontSize="sm" mb={3}>{description}</Text>
        <Progress 
          value={progress} 
          size="sm" 
          colorScheme={colorMode === 'dark' ? "cyan" : "blue"} 
          borderRadius="full" 
        />
      </CardBody>
    </Card>
  );
};

// Classification Card Component
const ClassificationCard: React.FC<{ 
  title: string, 
  description: string, 
  tags: string[] 
}> = ({ title, description, tags }) => {
  const { colorMode } = useColorMode();
  
  return (
    <Card 
      bg="bg.secondary" 
      borderRadius="md"
      border="1px solid"
      borderColor="border.primary"
    >
      <CardBody>
        <Heading size="sm" mb={2} color="text.primary">{title}</Heading>
        <Text fontSize="sm" color="text.secondary" mb={4}>{description}</Text>
        <Flex wrap="wrap" gap={2}>
          {tags.map((tag, index) => (
            <Tag 
              key={index} 
              size="sm" 
              bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
              color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
              borderRadius="full"
            >
              {tag}
            </Tag>
          ))}
        </Flex>
      </CardBody>
    </Card>
  );
};

// PII Tag Component
const PIITag: React.FC<{ label: string }> = ({ label }) => {
  const { colorMode } = useColorMode();
  
  return (
    <Flex 
      bg="bg.warning" 
      p={3} 
      borderRadius="md" 
      align="center"
      border="1px solid"
      borderColor="border.primary"
    >
      <Icon as={FaExclamationTriangle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} mr={2} />
      <Text fontSize="sm" fontWeight="medium" color="text.primary">{label}</Text>
    </Flex>
  );
};

export default AIAnalysis;
