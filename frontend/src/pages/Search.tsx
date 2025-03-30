import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Container,
  Divider,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  InputGroup,
  InputRightElement,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Text,
  useToast,
  VStack,
  HStack,
  Badge,
  Spinner,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
} from '@chakra-ui/react';
import { SearchIcon, ViewIcon } from '@chakra-ui/icons';

// Define types for search results
interface SearchResult {
  id: string;
  subject: string;
  sender: string;
  date: string;
  snippet: string;
  score: number;
  tags: string[];
  department: string;
}

interface SearchResponse {
  results: SearchResult[];
  total: number;
}

// Mock search function (in a real app, this would be in the API directory)
const searchKnowledgeBase = async (query: string): Promise<SearchResponse> => {
  // Simulate API call delay
  await new Promise(resolve => setTimeout(resolve, 800));
  
  // Mock data
  return {
    total: 12,
    results: Array(8).fill(0).map((_, i) => ({
      id: `result_${i}`,
      subject: `Search Result ${i + 1} for "${query}"`,
      sender: 'John Doe',
      date: new Date(Date.now() - i * 86400000).toISOString(),
      snippet: `This is a snippet of content that matches your search query "${query}". It contains relevant information about the topic you're interested in...`,
      score: 0.95 - (i * 0.05),
      tags: [`tag${i}`, 'knowledge', i % 2 === 0 ? 'important' : 'routine'],
      department: ['engineering', 'product', 'marketing', 'sales'][i % 4]
    }))
  };
};

// Mock function to get full content
const getFullContent = async (id: string) => {
  // Simulate API call delay
  await new Promise(resolve => setTimeout(resolve, 500));
  
  // Mock data
  return {
    id,
    subject: `Full Content for ${id}`,
    sender: 'John Doe',
    sender_email: 'john.doe@example.com',
    recipients: ['user@example.com'],
    date: new Date().toISOString(),
    body: `This is the full content of the knowledge item with ID ${id}. It contains more detailed information than what was shown in the search results snippet.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam auctor, nisl eget ultricies tincidunt, nisl nisl aliquam nisl, eget ultricies nisl nisl eget nisl. Nullam auctor, nisl eget ultricies tincidunt, nisl nisl aliquam nisl, eget ultricies nisl nisl eget nisl.

The knowledge item contains important information about the topic you searched for. It was extracted from an email and approved for inclusion in the knowledge base.`,
    tags: ['important', 'knowledge', 'email'],
    department: 'engineering',
    extracted_date: new Date(Date.now() - 7 * 86400000).toISOString(),
    source: 'Email',
  };
};

const Search: React.FC = () => {
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  
  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [isLoadingItem, setIsLoadingItem] = useState(false);
  
  // Handle search
  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      toast({
        title: 'Search query is empty',
        status: 'warning',
        duration: 3000,
      });
      return;
    }
    
    setIsSearching(true);
    setResults([]);
    
    try {
      const response = await searchKnowledgeBase(searchQuery);
      setResults(response.results);
      setTotalResults(response.total);
    } catch (error) {
      console.error('Error searching:', error);
      toast({
        title: 'Error searching knowledge base',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsSearching(false);
    }
  };
  
  // Handle view item
  const handleViewItem = async (id: string) => {
    setIsLoadingItem(true);
    setSelectedItem(null);
    
    try {
      const content = await getFullContent(id);
      setSelectedItem(content);
      onOpen();
    } catch (error) {
      console.error('Error loading content:', error);
      toast({
        title: 'Error loading content',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsLoadingItem(false);
    }
  };
  
  return (
    <Container maxW="container.xl" py={6}>
      <VStack spacing={8} align="stretch">
        <Heading size="lg">Search Knowledge Base</Heading>
        
        {/* Search Box */}
        <Card>
          <CardBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Search Query</FormLabel>
                <InputGroup size="lg">
                  <Input
                    placeholder="Enter search terms..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  />
                  <InputRightElement width="4.5rem">
                    <Button 
                      h="1.75rem" 
                      size="sm" 
                      onClick={handleSearch}
                      isLoading={isSearching}
                    >
                      <SearchIcon />
                    </Button>
                  </InputRightElement>
                </InputGroup>
              </FormControl>
              
              <Text fontSize="sm" color="gray.500">
                Search for knowledge extracted from your approved emails
              </Text>
            </VStack>
          </CardBody>
        </Card>
        
        {/* Search Results */}
        {(results.length > 0 || isSearching) && (
          <Card>
            <CardHeader>
              <Heading size="md">
                {isSearching 
                  ? 'Searching...' 
                  : `Search Results (${results.length} of ${totalResults})`}
              </Heading>
            </CardHeader>
            <CardBody>
              {isSearching ? (
                <Flex justify="center" py={8}>
                  <Spinner size="xl" />
                </Flex>
              ) : (
                <VStack spacing={4} align="stretch">
                  {results.map((result) => (
                    <Box 
                      key={result.id} 
                      p={4} 
                      borderWidth="1px" 
                      borderRadius="md"
                      _hover={{ bg: 'gray.50', _dark: { bg: 'gray.700' } }}
                    >
                      <Flex justify="space-between" align="start">
                        <VStack align="start" spacing={1}>
                          <Heading size="sm">{result.subject}</Heading>
                          <HStack>
                            <Text fontSize="sm" color="gray.500">
                              From: {result.sender}
                            </Text>
                            <Text fontSize="sm" color="gray.500">
                              • {new Date(result.date).toLocaleDateString()}
                            </Text>
                          </HStack>
                        </VStack>
                        <Badge colorScheme="green">
                          {Math.round(result.score * 100)}% match
                        </Badge>
                      </Flex>
                      
                      <Text mt={2} noOfLines={2}>
                        {result.snippet}
                      </Text>
                      
                      <Flex mt={3} justify="space-between" align="center">
                        <HStack>
                          {result.tags.map(tag => (
                            <Badge key={tag} colorScheme="blue" variant="outline">
                              {tag}
                            </Badge>
                          ))}
                          <Badge colorScheme="purple" variant="outline">
                            {result.department}
                          </Badge>
                        </HStack>
                        
                        <Button
                          size="sm"
                          leftIcon={<ViewIcon />}
                          onClick={() => handleViewItem(result.id)}
                          variant="ghost"
                        >
                          View
                        </Button>
                      </Flex>
                    </Box>
                  ))}
                </VStack>
              )}
            </CardBody>
          </Card>
        )}
      </VStack>
      
      {/* Content Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="xl" scrollBehavior="inside">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Knowledge Item</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            {isLoadingItem ? (
              <Flex justify="center" py={8}>
                <Spinner size="xl" />
              </Flex>
            ) : selectedItem && (
              <VStack spacing={4} align="stretch">
                <Heading size="md">{selectedItem.subject}</Heading>
                
                <HStack wrap="wrap">
                  <Badge colorScheme="purple">{selectedItem.department}</Badge>
                  {selectedItem.tags.map((tag: string) => (
                    <Badge key={tag} colorScheme="blue" variant="outline">
                      {tag}
                    </Badge>
                  ))}
                </HStack>
                
                <Divider />
                
                <Box>
                  <Text fontWeight="bold">Source:</Text>
                  <Text>{selectedItem.source}</Text>
                  
                  <Text fontWeight="bold" mt={2}>From:</Text>
                  <Text>{selectedItem.sender} ({selectedItem.sender_email})</Text>
                  
                  <Text fontWeight="bold" mt={2}>Date:</Text>
                  <Text>{new Date(selectedItem.date).toLocaleString()}</Text>
                  
                  <Text fontWeight="bold" mt={2}>Added to Knowledge Base:</Text>
                  <Text>{new Date(selectedItem.extracted_date).toLocaleString()}</Text>
                </Box>
                
                <Divider />
                
                <Accordion defaultIndex={[0]} allowToggle>
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                          Content
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <Box 
                        p={3} 
                        borderWidth="1px" 
                        borderRadius="md"
                        bg="gray.50"
                        _dark={{ bg: "gray.700" }}
                        whiteSpace="pre-wrap"
                      >
                        {selectedItem.body}
                      </Box>
                    </AccordionPanel>
                  </AccordionItem>
                </Accordion>
              </VStack>
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </Container>
  );
};

export default Search;
