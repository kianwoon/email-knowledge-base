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
  Tag,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Flex,
  useColorMode
} from '@chakra-ui/react';
import { FaSearch, FaFilter, FaCalendarAlt, FaUser, FaTag, FaFolder, FaPaperclip, FaInfoCircle } from 'react-icons/fa';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

// Filter Tip Card Component
const FilterTipCard = ({ 
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

// Workflow Step Card Component
const WorkflowStepCard = ({ 
  number, 
  title, 
  description
}: { 
  number: string, 
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
    >
      <CardBody>
        <HStack spacing={4} align="flex-start">
          <Flex
            w="40px"
            h="40px"
            bg="bg.accent"
            color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
            borderRadius="full"
            justify="center"
            align="center"
            fontSize="lg"
            fontWeight="bold"
          >
            {number}
          </Flex>
          
          <VStack align="flex-start" spacing={2}>
            <Heading size="sm" color="text.primary">{title}</Heading>
            <Text color="text.secondary">{description}</Text>
          </VStack>
        </HStack>
      </CardBody>
    </Card>
  );
};

// Use Case Card Component
const UseCaseCard = ({ 
  title, 
  description, 
  tags 
}: { 
  title: string, 
  description: string, 
  tags: string[] 
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
          <Heading size="md" color="text.primary">{title}</Heading>
          <Text color="text.secondary">{description}</Text>
          
          <HStack spacing={2} flexWrap="wrap">
            {tags.map((tag, index) => (
              <Tag 
                key={index} 
                bg="bg.accent" 
                color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                borderRadius="full" 
                size="md"
              >
                {tag}
              </Tag>
            ))}
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

const SmartFiltering: React.FC = () => {
  const { colorMode } = useColorMode();
  
  return (
    <Box bg="bg.primary" minH="100vh" color="text.primary">
      <PageBanner 
        title="Smart Email Processing" 
        subtitle="Automatically filter and categorize emails based on content, priority, and knowledge value."
        gradient={colorMode === 'dark' 
          ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
          : "linear(to-r, brand.600, brand.500, brand.400)"
        }
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaFilter} w={8} h={8} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
            <Heading 
              size="xl" 
              bgGradient={colorMode === 'dark' 
                ? "linear(to-r, neon.blue, neon.purple)"
                : "linear(to-r, brand.600, brand.400)"
              }
              bgClip="text"
            >
              Smart Filtering
            </Heading>
          </HStack>
          
          <Text fontSize="lg" color="text.secondary">
            Our advanced filtering system helps you precisely target the most valuable emails in your organization's
            mailboxes, ensuring you only process the content that matters most.
          </Text>
          
          <Divider borderColor="border.primary" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Filter Categories</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaFolder} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Folder-based:</strong> Target specific Outlook folders and subfolders</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCalendarAlt} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Date Range:</strong> Filter by specific time periods (last week, month, custom range)</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaUser} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Sender/Recipient:</strong> Filter by specific contacts or domains</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaSearch} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Keyword Search:</strong> Find emails containing specific terms or phrases</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaPaperclip} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Attachment Type:</strong> Filter by emails with specific attachment types (.pdf, .docx, etc.)</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaTag} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>Importance:</strong> Filter by priority flags or importance markers</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="bg.info" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                Filters can be combined to create highly specific queries, allowing you to target exactly the content you need.
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Advanced Query Syntax</Heading>
                <Code p={3} borderRadius="md" bg="bg.secondary" color="text.primary" display="block" whiteSpace="pre">
{`folder:"Projects" AND from:client@company.com
date:>2023-01-01 AND subject:"Quarterly Report"
hasAttachments:true AND attachmentType:.pdf
importance:high AND NOT from:internal@ourcompany.com`}
                </Code>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Filter Optimization</Heading>
              
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    <Heading size="sm" color="text.primary">Filter Performance Metrics</Heading>
                    <Table variant="simple" size="sm">
                      <Thead>
                        <Tr>
                          <Th color="text.secondary">Filter Type</Th>
                          <Th color="text.secondary">Processing Speed</Th>
                          <Th color="text.secondary">Precision</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        <Tr>
                          <Td color="text.primary">Folder-based</Td>
                          <Td color="text.primary">Very Fast</Td>
                          <Td color="text.primary">High</Td>
                        </Tr>
                        <Tr>
                          <Td color="text.primary">Date Range</Td>
                          <Td color="text.primary">Very Fast</Td>
                          <Td color="text.primary">High</Td>
                        </Tr>
                        <Tr>
                          <Td color="text.primary">Sender/Recipient</Td>
                          <Td color="text.primary">Fast</Td>
                          <Td color="text.primary">High</Td>
                        </Tr>
                        <Tr>
                          <Td color="text.primary">Keyword Search</Td>
                          <Td color="text.primary">Moderate</Td>
                          <Td color="text.primary">Medium</Td>
                        </Tr>
                        <Tr>
                          <Td color="text.primary">Attachment Type</Td>
                          <Td color="text.primary">Fast</Td>
                          <Td color="text.primary">High</Td>
                        </Tr>
                        <Tr>
                          <Td color="text.primary">Combined Filters</Td>
                          <Td color="text.primary">Varies</Td>
                          <Td color="text.primary">Very High</Td>
                        </Tr>
                      </Tbody>
                    </Table>
                  </VStack>
                </CardBody>
              </Card>
              
              <SimpleGrid columns={1} spacing={4}>
                <FilterTipCard 
                  icon={FaInfoCircle}
                  title="Start Broad, Then Refine"
                  description="Begin with wider filters and gradually narrow down as you review results"
                />
                
                <FilterTipCard 
                  icon={FaInfoCircle}
                  title="Combine Filter Types"
                  description="Using multiple filter types together yields more precise results"
                />
                
                <FilterTipCard 
                  icon={FaInfoCircle}
                  title="Optimize for Speed"
                  description="When processing large mailboxes, start with the fastest filter types"
                />
              </SimpleGrid>
            </VStack>
          </SimpleGrid>
          
          <Divider borderColor="border.primary" />
          
          {/* Workflow Section */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Filtering Workflow</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <WorkflowStepCard 
                number="1"
                title="Define Your Knowledge Goals"
                description="Identify what types of information you want to extract and preserve from emails"
              />
              
              <WorkflowStepCard 
                number="2"
                title="Set Up Initial Filters"
                description="Configure broad filters to capture potentially relevant content"
              />
              
              <WorkflowStepCard 
                number="3"
                title="Review & Refine"
                description="Analyze initial results and adjust filters to improve precision"
              />
              
              <WorkflowStepCard 
                number="4"
                title="Save Filter Templates"
                description="Store successful filter combinations as templates for future use"
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="border.primary" />
          
          {/* Use Cases Section */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Common Use Cases</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <UseCaseCard 
                title="Project Documentation"
                description="Capture all project-related communications for future reference and onboarding"
                tags={["Project Management", "Documentation", "Onboarding"]}
              />
              
              <UseCaseCard 
                title="Client Knowledge Base"
                description="Build comprehensive profiles of client preferences, history, and requirements"
                tags={["Client Relations", "Sales", "Support"]}
              />
              
              <UseCaseCard 
                title="Technical Solutions"
                description="Preserve technical solutions, workarounds, and troubleshooting steps"
                tags={["IT Support", "Engineering", "Troubleshooting"]}
              />
            </SimpleGrid>
          </Box>
        </VStack>
      </Container>
      
      <Footer />
    </Box>
  );
};

export default SmartFiltering;
