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
} from '@chakra-ui/react';
import { FaSearch, FaFilter, FaCalendarAlt, FaUser, FaTag, FaFolder, FaPaperclip, FaInfoCircle } from 'react-icons/fa';
import DocumentationHeader from '../../components/DocumentationHeader';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

const SmartFiltering: React.FC = () => {
  return (
    <Box bg="#050a30" minH="100vh" color="white">
      <DocumentationHeader />
      <PageBanner 
        title="Smart Email Processing" 
        subtitle="Automatically filter and categorize emails based on content, priority, and knowledge value."
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaFilter} w={8} h={8} color="neon.blue" />
            <Heading 
              size="xl" 
              bgGradient="linear(to-r, #3ef2f2, #f72585)" 
              bgClip="text"
            >
              Smart Filtering
            </Heading>
          </HStack>
          
          <Text fontSize="lg">
            Our advanced filtering system helps you precisely target the most valuable emails in your organization's
            mailboxes, ensuring you only process the content that matters most.
          </Text>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color="neon.blue">Filter Categories</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaFolder} color="neon.blue" />
                    <Text><strong>Folder-based:</strong> Target specific Outlook folders and subfolders</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaCalendarAlt} color="neon.blue" />
                    <Text><strong>Date Range:</strong> Filter by specific time periods (last week, month, custom range)</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaUser} color="neon.blue" />
                    <Text><strong>Sender/Recipient:</strong> Filter by specific contacts or domains</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaSearch} color="neon.blue" />
                    <Text><strong>Keyword Search:</strong> Find emails containing specific terms or phrases</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaPaperclip} color="neon.blue" />
                    <Text><strong>Attachment Type:</strong> Filter by emails with specific attachment types (.pdf, .docx, etc.)</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaTag} color="neon.blue" />
                    <Text><strong>Importance:</strong> Filter by priority flags or importance markers</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="rgba(62, 242, 242, 0.1)" color="white" borderRadius="md">
                <AlertIcon color="neon.blue" />
                Filters can be combined to create highly specific queries, allowing you to target exactly the content you need.
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color="neon.blue">Advanced Query Syntax</Heading>
                <Code p={3} borderRadius="md" bg="whiteAlpha.100" color="white" display="block" whiteSpace="pre">
{`folder:"Projects" AND from:client@company.com
date:>2023-01-01 AND subject:"Quarterly Report"
hasAttachments:true AND attachmentType:.pdf
importance:high AND NOT from:internal@ourcompany.com`}
                </Code>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color="neon.blue">Filter Optimization</Heading>
              
              <Card 
                bg="rgba(255, 255, 255, 0.05)" 
                borderRadius="lg" 
                border="1px solid rgba(255, 255, 255, 0.1)"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    <Heading size="sm">Filter Performance Metrics</Heading>
                    <Table variant="simple" size="sm">
                      <Thead>
                        <Tr>
                          <Th color="whiteAlpha.700">Filter Type</Th>
                          <Th color="whiteAlpha.700">Processing Speed</Th>
                          <Th color="whiteAlpha.700">Precision</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        <Tr>
                          <Td>Folder-based</Td>
                          <Td>Very Fast</Td>
                          <Td>High</Td>
                        </Tr>
                        <Tr>
                          <Td>Date Range</Td>
                          <Td>Very Fast</Td>
                          <Td>High</Td>
                        </Tr>
                        <Tr>
                          <Td>Sender/Recipient</Td>
                          <Td>Fast</Td>
                          <Td>High</Td>
                        </Tr>
                        <Tr>
                          <Td>Keyword Search</Td>
                          <Td>Moderate</Td>
                          <Td>Medium</Td>
                        </Tr>
                        <Tr>
                          <Td>Attachment Type</Td>
                          <Td>Fast</Td>
                          <Td>High</Td>
                        </Tr>
                        <Tr>
                          <Td>Combined Filters</Td>
                          <Td>Varies</Td>
                          <Td>Very High</Td>
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
                  title="Save Common Filters"
                  description="Save frequently used filter combinations as templates for future use"
                />
              </SimpleGrid>
              
              <Alert status="warning" bg="rgba(247, 37, 133, 0.1)" color="white" borderRadius="md">
                <AlertIcon color="neon.pink" />
                Very broad filters on large mailboxes may take longer to process. We recommend starting with specific folders.
              </Alert>
            </VStack>
          </SimpleGrid>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Filter Workflow */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Filter Workflow</Heading>
            
            <Box 
              p={6} 
              bg="rgba(255, 255, 255, 0.05)" 
              borderRadius="lg" 
              border="1px solid rgba(255, 255, 255, 0.1)"
            >
              <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
                <WorkflowStepCard 
                  number="01"
                  title="Select Filter Criteria"
                  description="Choose folders, date ranges, senders, keywords, and other parameters"
                />
                
                <WorkflowStepCard 
                  number="02"
                  title="Preview Results"
                  description="View matching email count and metadata before processing"
                />
                
                <WorkflowStepCard 
                  number="03"
                  title="Refine & Confirm"
                  description="Adjust filters if needed, then confirm selection for analysis"
                />
              </SimpleGrid>
            </Box>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Example Use Cases */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Example Use Cases</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <UseCaseCard 
                title="Project Documentation"
                description="Filter emails from a specific client domain within the 'Projects' folder that contain PDF attachments"
                tags={['folder:Projects', 'from:client.com', 'attachmentType:.pdf']}
              />
              
              <UseCaseCard 
                title="Policy Updates"
                description="Find all emails from the legal team containing 'policy update' in the subject line from the last quarter"
                tags={['from:legal@company.com', 'subject:policy update', 'date:last-3-months']}
              />
              
              <UseCaseCard 
                title="Client Feedback"
                description="Collect all emails with 'feedback' or 'review' keywords from external domains"
                tags={['keyword:feedback OR review', 'from:external', 'not:internal@company.com']}
              />
              
              <UseCaseCard 
                title="Executive Decisions"
                description="Filter high-importance emails from executive team members containing specific project codenames"
                tags={['from:executive-team', 'importance:high', 'keyword:project-alpha']}
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* FAQ Section */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Frequently Asked Questions</Heading>
            
            <VStack spacing={4} align="stretch">
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>How many filters can I combine at once?</Heading>
                <Text>You can combine up to 10 different filter criteria in a single query. This allows for highly specific targeting of emails.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Can I save my filter combinations for future use?</Heading>
                <Text>Yes, you can save filter templates in your account settings. This makes it easy to run the same queries on a regular basis.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Is there a limit to how many emails I can filter?</Heading>
                <Text>The system can handle filtering through tens of thousands of emails, but processing time will increase with volume. We recommend using date ranges to limit very large queries.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Can I filter based on email content, not just metadata?</Heading>
                <Text>Yes, the keyword search filter examines both subject lines and email body content. For more advanced content filtering, you can use the AI Analysis features after initial filtering.</Text>
              </Box>
            </VStack>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

// Filter Tip Card Component
const FilterTipCard = ({ icon, title, description }: { icon: any, title: string, description: string }) => {
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
          <Box
            p={2}
            bg="rgba(62, 242, 242, 0.2)"
            color="neon.blue"
            borderRadius="md"
            boxShadow="0 0 10px rgba(62, 242, 242, 0.3)"
          >
            <Icon as={icon} w={5} h={5} />
          </Box>
          <VStack align="start" spacing={1}>
            <Heading size="sm">{title}</Heading>
            <Text fontSize="sm" color="whiteAlpha.800">{description}</Text>
          </VStack>
        </HStack>
      </CardBody>
    </Card>
  );
};

// Workflow Step Card Component
const WorkflowStepCard = ({ number, title, description }: { number: string, title: string, description: string }) => {
  return (
    <VStack 
      p={4} 
      bg="rgba(255, 255, 255, 0.03)" 
      borderRadius="lg"
      spacing={4}
      align="flex-start"
      position="relative"
      overflow="hidden"
    >
      <Box 
        position="absolute" 
        top="-10px" 
        right="-10px" 
        fontSize="80px" 
        fontWeight="bold" 
        opacity="0.1"
        color="neon.blue"
      >
        {number}
      </Box>
      
      <Heading size="md">{title}</Heading>
      <Text color="whiteAlpha.800">{description}</Text>
    </VStack>
  );
};

// Use Case Card Component
const UseCaseCard = ({ title, description, tags }: { title: string, description: string, tags: string[] }) => {
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
        <VStack align="flex-start" spacing={3}>
          <Heading size="md">{title}</Heading>
          <Text color="whiteAlpha.800">{description}</Text>
          
          <HStack flexWrap="wrap" spacing={2} pt={2}>
            {tags.map((tag, index) => (
              <Tag 
                key={index} 
                size="sm" 
                bg="rgba(62, 242, 242, 0.2)" 
                color="neon.blue"
                borderRadius="full"
                my={1}
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

export default SmartFiltering;
