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
} from '@chakra-ui/react';
import { FaBrain, FaShieldAlt, FaTag, FaEye, FaLock, FaCheckCircle, FaExclamationTriangle, FaChartLine } from 'react-icons/fa';
import DocumentationHeader from '../../components/DocumentationHeader';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

const AIAnalysis: React.FC = () => {
  return (
    <Box bg="#050a30" minH="100vh" color="white">
      <DocumentationHeader />
      <PageBanner 
        title="AI-Powered Knowledge Extraction" 
        subtitle="Extract valuable insights and patterns from your communications using advanced AI algorithms."
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaBrain} w={8} h={8} color="neon.blue" />
            <Heading 
              size="xl" 
              bgGradient="linear(to-r, #3ef2f2, #f72585)" 
              bgClip="text"
            >
              AI Analysis
            </Heading>
          </HStack>
          
          <Text fontSize="lg">
            Our advanced AI analysis engine processes your selected emails to extract valuable insights,
            classify content, and prepare knowledge for export while ensuring privacy and compliance.
          </Text>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color="neon.blue">AI Capabilities</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaTag} color="neon.blue" />
                    <Text><strong>Smart Classification:</strong> Automatically categorizes emails by department, topic, and importance</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaShieldAlt} color="neon.blue" />
                    <Text><strong>PII Detection:</strong> Identifies and flags personally identifiable information for review</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaEye} color="neon.blue" />
                    <Text><strong>Content Summarization:</strong> Creates concise summaries of email threads and conversations</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaLock} color="neon.blue" />
                    <Text><strong>Sensitivity Analysis:</strong> Evaluates content for confidentiality and compliance concerns</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaChartLine} color="neon.blue" />
                    <Text><strong>Knowledge Extraction:</strong> Identifies key facts, decisions, and actionable insights</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="rgba(62, 242, 242, 0.1)" color="white" borderRadius="md">
                <AlertIcon color="neon.blue" />
                Our AI models are fine-tuned for business communications and can be customized for your organization's specific terminology and needs.
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color="neon.blue">AI Model Specifications</Heading>
                <Card bg="whiteAlpha.100" borderRadius="md">
                  <CardBody>
                    <SimpleGrid columns={2} spacing={4}>
                      <Stat>
                        <StatLabel color="whiteAlpha.700">Base Model</StatLabel>
                        <StatNumber fontSize="md">ChatGPT-4o mini</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="whiteAlpha.700">Fine-tuning</StatLabel>
                        <StatNumber fontSize="md">Business Communications</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="whiteAlpha.700">Context Window</StatLabel>
                        <StatNumber fontSize="md">16K tokens</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="whiteAlpha.700">Processing Speed</StatLabel>
                        <StatNumber fontSize="md">~3-5 sec/email</StatNumber>
                      </Stat>
                    </SimpleGrid>
                  </CardBody>
                </Card>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color="neon.blue">Analysis Process</Heading>
              
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
              
              <Alert status="warning" bg="rgba(247, 37, 133, 0.1)" color="white" borderRadius="md">
                <AlertIcon color="neon.pink" />
                AI analysis is designed to assist human reviewers, not replace them. All AI-generated tags and classifications can be modified during review.
              </Alert>
            </VStack>
          </SimpleGrid>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Classification Categories */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Classification Categories</Heading>
            
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
                title="Sensitivity Level"
                description="Evaluates confidentiality requirements"
                tags={['Public', 'Internal', 'Confidential', 'Restricted', 'PII Present', 'Legal Hold']}
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Privacy & Compliance */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Privacy & Compliance</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <Card 
                bg="rgba(255, 255, 255, 0.05)" 
                borderRadius="lg" 
                border="1px solid rgba(255, 255, 255, 0.1)"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaShieldAlt} color="neon.blue" w={6} h={6} />
                      <Heading size="md">PII Detection</Heading>
                    </HStack>
                    
                    <Text>Our AI is trained to identify over 50 types of personally identifiable information, including:</Text>
                    
                    <SimpleGrid columns={2} spacing={2}>
                      <PIITag label="Names" />
                      <PIITag label="Email Addresses" />
                      <PIITag label="Phone Numbers" />
                      <PIITag label="Addresses" />
                      <PIITag label="SSN/ID Numbers" />
                      <PIITag label="Credit Card Data" />
                      <PIITag label="Financial Info" />
                      <PIITag label="Health Data" />
                    </SimpleGrid>
                    
                    <Text>Detected PII is flagged for review and can be automatically redacted before export.</Text>
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
                      <Icon as={FaLock} color="neon.blue" w={6} h={6} />
                      <Heading size="md">Compliance Framework</Heading>
                    </HStack>
                    
                    <Text>Our AI analysis is designed with regulatory compliance in mind:</Text>
                    
                    <List spacing={2}>
                      <ListItem>
                        <HStack>
                          <ListIcon as={FaCheckCircle} color="neon.blue" />
                          <Text><strong>GDPR:</strong> Identifies EU personal data for proper handling</Text>
                        </HStack>
                      </ListItem>
                      
                      <ListItem>
                        <HStack>
                          <ListIcon as={FaCheckCircle} color="neon.blue" />
                          <Text><strong>CCPA/CPRA:</strong> Flags California resident information</Text>
                        </HStack>
                      </ListItem>
                      
                      <ListItem>
                        <HStack>
                          <ListIcon as={FaCheckCircle} color="neon.blue" />
                          <Text><strong>HIPAA:</strong> Detects protected health information</Text>
                        </HStack>
                      </ListItem>
                      
                      <ListItem>
                        <HStack>
                          <ListIcon as={FaCheckCircle} color="neon.blue" />
                          <Text><strong>PCI DSS:</strong> Identifies payment card information</Text>
                        </HStack>
                      </ListItem>
                    </List>
                    
                    <Text>All processing is logged for audit purposes, maintaining a compliance trail.</Text>
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* FAQ Section */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Frequently Asked Questions</Heading>
            
            <VStack spacing={4} align="stretch">
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>How accurate is the AI classification?</Heading>
                <Text>Our AI achieves 85-95% accuracy in most business contexts. The human review stage allows for correction of any misclassifications before final export.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Can I customize the classification categories?</Heading>
                <Text>Yes, enterprise customers can define custom classification taxonomies and train the system on organization-specific terminology.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Where is the AI processing performed?</Heading>
                <Text>All AI analysis is performed within your security perimeter. For cloud deployments, data is processed in compliance with your data residency requirements.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>How does the system handle multi-language content?</Heading>
                <Text>Our AI supports analysis in 25+ languages, with full classification capabilities in English, Spanish, French, German, Italian, Portuguese, Japanese, and Chinese.</Text>
              </Box>
            </VStack>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

// Process Step Card Component
const ProcessStepCard = ({ number, title, description, progress }: { 
  number: string, 
  title: string, 
  description: string,
  progress: number
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
        <HStack spacing={4} align="flex-start">
          <Box
            p={2}
            bg="rgba(62, 242, 242, 0.2)"
            color="neon.blue"
            borderRadius="md"
            boxShadow="0 0 10px rgba(62, 242, 242, 0.3)"
            fontSize="lg"
            fontWeight="bold"
            minW="40px"
            textAlign="center"
          >
            {number}
          </Box>
          <VStack align="start" spacing={2} flex="1">
            <Heading size="sm">{title}</Heading>
            <Text fontSize="sm" color="whiteAlpha.800">{description}</Text>
            <Progress 
              value={progress} 
              size="xs" 
              w="100%" 
              colorScheme="blue" 
              bg="whiteAlpha.200" 
              borderRadius="full"
              mt={1}
            />
          </VStack>
        </HStack>
      </CardBody>
    </Card>
  );
};

// Classification Card Component
const ClassificationCard = ({ title, description, tags }: { 
  title: string, 
  description: string, 
  tags: string[] 
}) => {
  return (
    <Card 
      bg="rgba(255, 255, 255, 0.05)" 
      borderRadius="lg" 
      border="1px solid rgba(255, 255, 255, 0.1)"
      overflow="hidden"
    >
      <CardBody>
        <VStack align="flex-start" spacing={4}>
          <Heading size="md">{title}</Heading>
          <Text color="whiteAlpha.800">{description}</Text>
          
          <Flex flexWrap="wrap" gap={2}>
            {tags.map((tag, index) => (
              <Tag 
                key={index} 
                bg="rgba(62, 242, 242, 0.1)" 
                color="neon.blue"
                borderRadius="full"
                size="sm"
              >
                {tag}
              </Tag>
            ))}
          </Flex>
        </VStack>
      </CardBody>
    </Card>
  );
};

// PII Tag Component
const PIITag = ({ label }: { label: string }) => {
  return (
    <HStack>
      <Icon as={FaExclamationTriangle} color="neon.pink" w={3} h={3} />
      <Text fontSize="sm">{label}</Text>
    </HStack>
  );
};

export default AIAnalysis;
