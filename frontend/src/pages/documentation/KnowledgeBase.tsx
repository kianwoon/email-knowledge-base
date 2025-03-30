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
  Button,
  Badge,
} from '@chakra-ui/react';
import { FaDatabase, FaSearch, FaNetworkWired, FaChartLine, FaLock, FaCheckCircle, FaFileExport, FaCode } from 'react-icons/fa';
import DocumentationHeader from '../../components/DocumentationHeader';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

const KnowledgeBase: React.FC = () => {
  return (
    <Box bg="#050a30" minH="100vh" color="white">
      <DocumentationHeader />
      <PageBanner 
        title="Centralized Knowledge Base" 
        subtitle="Store all extracted knowledge in a searchable, secure database accessible to your entire team."
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaDatabase} w={8} h={8} color="neon.blue" />
            <Heading 
              size="xl" 
              bgGradient="linear(to-r, #3ef2f2, #f72585)" 
              bgClip="text"
            >
              Knowledge Base
            </Heading>
          </HStack>
          
          <Text fontSize="lg">
            Transform your organization's email communications into a structured, searchable knowledge repository
            that preserves institutional memory and enables powerful insights discovery.
          </Text>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color="neon.blue">Vector Database Technology</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaNetworkWired} color="neon.blue" />
                    <Text><strong>Qdrant Vector Database:</strong> High-performance vector similarity search engine</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaSearch} color="neon.blue" />
                    <Text><strong>Semantic Search:</strong> Find content based on meaning, not just keywords</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaChartLine} color="neon.blue" />
                    <Text><strong>Scalable Architecture:</strong> Handles millions of documents with sub-second query times</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaLock} color="neon.blue" />
                    <Text><strong>Secure Storage:</strong> Encrypted at rest and in transit with access controls</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="rgba(62, 242, 242, 0.1)" color="white" borderRadius="md">
                <AlertIcon color="neon.blue" />
                Vector embeddings capture the semantic meaning of your content, enabling powerful similarity searches and knowledge discovery.
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color="neon.blue">Embedding Specifications</Heading>
                <Card bg="whiteAlpha.100" borderRadius="md">
                  <CardBody>
                    <SimpleGrid columns={2} spacing={4}>
                      <VStack align="start">
                        <Text color="whiteAlpha.700">Model</Text>
                        <Text fontWeight="bold">OpenAI text-embedding-3-small</Text>
                      </VStack>
                      
                      <VStack align="start">
                        <Text color="whiteAlpha.700">Dimensions</Text>
                        <Text fontWeight="bold">1536</Text>
                      </VStack>
                      
                      <VStack align="start">
                        <Text color="whiteAlpha.700">Distance Metric</Text>
                        <Text fontWeight="bold">Cosine Similarity</Text>
                      </VStack>
                      
                      <VStack align="start">
                        <Text color="whiteAlpha.700">Indexing</Text>
                        <Text fontWeight="bold">HNSW Algorithm</Text>
                      </VStack>
                    </SimpleGrid>
                  </CardBody>
                </Card>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color="neon.blue">Knowledge Structure</Heading>
              
              <SimpleGrid columns={1} spacing={4}>
                <KnowledgeStructureCard 
                  title="Email Documents"
                  description="Complete email content with metadata, structured for retrieval"
                  fields={['Subject', 'Sender', 'Recipients', 'Date', 'Body Text', 'Importance']}
                />
                
                <KnowledgeStructureCard 
                  title="Attachments"
                  description="Parsed content from email attachments with file metadata"
                  fields={['File Name', 'File Type', 'Size', 'Creation Date', 'Extracted Text']}
                />
                
                <KnowledgeStructureCard 
                  title="AI Analysis"
                  description="AI-generated tags, classifications, and insights"
                  fields={['Department', 'Topic', 'Sensitivity', 'Key Insights', 'Summary']}
                />
                
                <KnowledgeStructureCard 
                  title="Human Review"
                  description="Reviewer annotations, approvals, and modifications"
                  fields={['Reviewer', 'Approval Status', 'Modified Tags', 'Notes', 'Review Date']}
                />
              </SimpleGrid>
              
              <Alert status="warning" bg="rgba(247, 37, 133, 0.1)" color="white" borderRadius="md">
                <AlertIcon color="neon.pink" />
                All exported knowledge maintains references to source emails for compliance and audit purposes.
              </Alert>
            </VStack>
          </SimpleGrid>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Search Capabilities */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Search Capabilities</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <SearchFeatureCard 
                icon={FaSearch}
                title="Semantic Search"
                description="Find content based on meaning and context, not just exact keyword matches"
                example="Show me all discussions about the Johnson project budget concerns"
              />
              
              <SearchFeatureCard 
                icon={FaNetworkWired}
                title="Relationship Discovery"
                description="Identify connections between topics, people, and decisions across emails"
                example="What decisions were made about the marketing strategy by the executive team?"
              />
              
              <SearchFeatureCard 
                icon={FaChartLine}
                title="Trend Analysis"
                description="Track how topics and sentiments evolve over time within communications"
                example="How has our approach to customer feedback changed over the past year?"
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Integration Options */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Integration Options</Heading>
            
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
                      <Icon as={FaFileExport} color="neon.blue" w={6} h={6} />
                      <Heading size="md">Export Formats</Heading>
                    </HStack>
                    
                    <Text>Export your knowledge base in multiple formats:</Text>
                    
                    <SimpleGrid columns={2} spacing={3}>
                      <ExportFormatTag format="Qdrant Cloud" />
                      <ExportFormatTag format="Weaviate" />
                      <ExportFormatTag format="Pinecone" />
                      <ExportFormatTag format="Elasticsearch" />
                      <ExportFormatTag format="JSON" />
                      <ExportFormatTag format="CSV" />
                    </SimpleGrid>
                    
                    <Text>Custom export formats available for enterprise customers.</Text>
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
                      <Icon as={FaCode} color="neon.blue" w={6} h={6} />
                      <Heading size="md">API Access</Heading>
                    </HStack>
                    
                    <Text>Connect to your knowledge base programmatically:</Text>
                    
                    <List spacing={2}>
                      <ListItem>
                        <HStack>
                          <ListIcon as={FaCheckCircle} color="neon.blue" />
                          <Text><strong>REST API:</strong> Standard HTTP endpoints for all operations</Text>
                        </HStack>
                      </ListItem>
                      
                      <ListItem>
                        <HStack>
                          <ListIcon as={FaCheckCircle} color="neon.blue" />
                          <Text><strong>GraphQL:</strong> Flexible querying for complex data needs</Text>
                        </HStack>
                      </ListItem>
                      
                      <ListItem>
                        <HStack>
                          <ListIcon as={FaCheckCircle} color="neon.blue" />
                          <Text><strong>SDK Support:</strong> Client libraries for Python, JavaScript, Java</Text>
                        </HStack>
                      </ListItem>
                      
                      <ListItem>
                        <HStack>
                          <ListIcon as={FaCheckCircle} color="neon.blue" />
                          <Text><strong>Webhooks:</strong> Event-driven integration with your systems</Text>
                        </HStack>
                      </ListItem>
                    </List>
                    
                    <Button size="sm" variant="glass" leftIcon={<FaCode />}>View API Documentation</Button>
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* Example Code */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Example API Usage</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <Box>
                <Heading size="sm" mb={3}>Python Query Example</Heading>
                <Code p={4} borderRadius="md" bg="whiteAlpha.100" color="white" display="block" whiteSpace="pre" fontSize="sm">
{`import requests

# Connect to your knowledge base
api_key = "your_api_key"
base_url = "https://api.emailkb.com/v1"

# Perform a semantic search
response = requests.post(
    f"{base_url}/search",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "query": "marketing strategy Q3 2023",
        "limit": 10,
        "filter": {
            "date_range": {
                "start": "2023-01-01",
                "end": "2023-12-31"
            },
            "departments": ["Marketing", "Executive"]
        }
    }
)

# Process results
results = response.json()
for item in results["items"]:
    print(f"Score: {item['score']}")
    print(f"Title: {item['metadata']['subject']}")
    print(f"Content: {item['content'][:100]}...")`}
                </Code>
              </Box>
              
              <Box>
                <Heading size="sm" mb={3}>JavaScript Integration Example</Heading>
                <Code p={4} borderRadius="md" bg="whiteAlpha.100" color="white" display="block" whiteSpace="pre" fontSize="sm">
{`// Initialize the Email KB client
const EmailKB = require('emailkb-client');

const client = new EmailKB.Client({
  apiKey: 'your_api_key',
  baseUrl: 'https://api.emailkb.com/v1'
});

// Create a custom dashboard widget
async function loadRelatedDocuments(topic) {
  try {
    const results = await client.search({
      query: topic,
      limit: 5,
      includeMetadata: true
    });
    
    // Render results in your application
    const container = document.getElementById('related-docs');
    container.innerHTML = '';
    
    results.items.forEach(item => {
      const element = document.createElement('div');
      element.className = 'document-card';
      element.innerHTML = \`
        <h3>\${item.metadata.subject}</h3>
        <p>\${item.content.substring(0, 150)}...</p>
        <span>Relevance: \${Math.round(item.score * 100)}%</span>
      \`;
      container.appendChild(element);
    });
  } catch (error) {
    console.error('Failed to load documents:', error);
  }
}`}
                </Code>
              </Box>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="whiteAlpha.300" />
          
          {/* FAQ Section */}
          <Box>
            <Heading size="md" mb={4} color="neon.blue">Frequently Asked Questions</Heading>
            
            <VStack spacing={4} align="stretch">
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>How is the knowledge base different from just searching my emails?</Heading>
                <Text>Unlike standard email search, our knowledge base uses vector embeddings to understand the semantic meaning of content, allowing you to find information based on concepts rather than exact keywords. It also includes AI-generated tags, classifications, and insights that aren't available in standard email systems.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Can I control who has access to the knowledge base?</Heading>
                <Text>Yes, the system includes comprehensive role-based access controls. You can restrict access by department, user role, content sensitivity, and other parameters to ensure information is only available to authorized personnel.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>What happens if I need to delete information from the knowledge base?</Heading>
                <Text>The platform includes comprehensive data management tools that allow you to remove specific content, update classifications, or implement retention policies. All deletions are logged for compliance purposes.</Text>
              </Box>
              
              <Box p={4} bg="rgba(255, 255, 255, 0.05)" borderRadius="md">
                <Heading size="sm" mb={2}>Can the knowledge base be integrated with our existing systems?</Heading>
                <Text>Yes, our API and export options allow for seamless integration with your existing knowledge management systems, intranets, CRMs, and custom applications. Enterprise customers receive dedicated integration support.</Text>
              </Box>
            </VStack>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

// Knowledge Structure Card Component
const KnowledgeStructureCard = ({ title, description, fields }: { 
  title: string, 
  description: string,
  fields: string[]
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
        <VStack align="flex-start" spacing={3}>
          <Heading size="md">{title}</Heading>
          <Text color="whiteAlpha.800">{description}</Text>
          
          <Flex flexWrap="wrap" gap={2} pt={1}>
            {fields.map((field, index) => (
              <Badge 
                key={index} 
                bg="rgba(62, 242, 242, 0.1)" 
                color="neon.blue"
                borderRadius="md"
                px={2}
                py={1}
              >
                {field}
              </Badge>
            ))}
          </Flex>
        </VStack>
      </CardBody>
    </Card>
  );
};

// Search Feature Card Component
const SearchFeatureCard = ({ icon, title, description, example }: { 
  icon: any, 
  title: string, 
  description: string,
  example: string
}) => {
  return (
    <Card 
      bg="rgba(255, 255, 255, 0.05)" 
      borderRadius="lg" 
      border="1px solid rgba(255, 255, 255, 0.1)"
      overflow="hidden"
      h="100%"
      transition="all 0.3s"
      _hover={{ 
        transform: 'translateY(-5px)', 
        boxShadow: '0 8px 30px rgba(62, 242, 242, 0.2)',
        borderColor: 'rgba(62, 242, 242, 0.3)'
      }}
    >
      <CardBody>
        <VStack align="flex-start" spacing={4} h="100%">
          <Box
            p={2}
            bg="rgba(62, 242, 242, 0.2)"
            color="neon.blue"
            borderRadius="md"
            boxShadow="0 0 10px rgba(62, 242, 242, 0.3)"
          >
            <Icon as={icon} w={5} h={5} />
          </Box>
          
          <Heading size="md">{title}</Heading>
          <Text color="whiteAlpha.800">{description}</Text>
          
          <Box 
            mt="auto" 
            pt={2} 
            w="100%" 
            borderTop="1px solid" 
            borderColor="whiteAlpha.200"
          >
            <Text fontSize="sm" fontStyle="italic" color="whiteAlpha.700">Example:</Text>
            <Text fontSize="sm" color="neon.blue">"{example}"</Text>
          </Box>
        </VStack>
      </CardBody>
    </Card>
  );
};

// Export Format Tag Component
const ExportFormatTag = ({ format }: { format: string }) => {
  return (
    <HStack 
      bg="rgba(62, 242, 242, 0.1)" 
      color="white" 
      borderRadius="md" 
      px={3} 
      py={1}
      border="1px solid rgba(62, 242, 242, 0.3)"
    >
      <Icon as={FaFileExport} w={3} h={3} color="neon.blue" />
      <Text fontSize="sm">{format}</Text>
    </HStack>
  );
};

export default KnowledgeBase;
