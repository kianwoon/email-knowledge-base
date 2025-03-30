import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  Container,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Select,
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
  Spinner,
  Icon,
  InputGroup,
  InputRightElement,
  Tag,
  TagLabel,
  TagCloseButton,
  Grid,
  GridItem,
  useColorMode,
  IconButton,
} from '@chakra-ui/react';
import { ChevronRightIcon, SearchIcon, AddIcon } from '@chakra-ui/icons';
import { FaFilter, FaSearch, FaEnvelope, FaCalendarAlt, FaTag, FaUserAlt } from 'react-icons/fa';

import { getEmailFolders, getEmailPreviews, analyzeEmails } from '../api/email';
import { EmailPreview, EmailFilter } from '../types/email';

const FilterSetup: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToast();
  const { colorMode } = useColorMode();
  
  // State
  const [folders, setFolders] = useState<any[]>([]);
  const [filter, setFilter] = useState<EmailFilter>({
    folder_id: '',
    keywords: [],
  });
  const [keywordInput, setKeywordInput] = useState('');
  const [previews, setPreviews] = useState<EmailPreview[]>([]);
  const [selectedEmails, setSelectedEmails] = useState<string[]>([]);
  const [isLoadingFolders, setIsLoadingFolders] = useState(false);
  const [isLoadingPreviews, setIsLoadingPreviews] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Load folders on component mount
  useEffect(() => {
    const loadFolders = async () => {
      setIsLoadingFolders(true);
      try {
        const folderData = await getEmailFolders();
        setFolders(folderData);
      } catch (error) {
        console.error('Error loading folders:', error);
        toast({
          title: 'Error loading folders',
          status: 'error',
          duration: 3000,
        });
      } finally {
        setIsLoadingFolders(false);
      }
    };
    
    loadFolders();
  }, [toast]);
  
  // Handle filter changes
  const handleFilterChange = (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
    const { name, value } = e.target;
    setFilter(prev => ({ ...prev, [name]: value }));
  };
  
  // Add keyword to filter
  const handleAddKeyword = () => {
    if (keywordInput.trim() && !filter.keywords?.includes(keywordInput.trim())) {
      setFilter(prev => ({
        ...prev,
        keywords: [...(prev.keywords || []), keywordInput.trim()],
      }));
      setKeywordInput('');
    }
  };
  
  // Remove keyword from filter
  const handleRemoveKeyword = (keyword: string) => {
    setFilter(prev => ({
      ...prev,
      keywords: prev.keywords?.filter(k => k !== keyword) || [],
    }));
  };
  
  // Preview emails based on filter
  const handlePreviewEmails = async () => {
    setIsLoadingPreviews(true);
    setPreviews([]);
    setSelectedEmails([]);
    
    try {
      const previewData = await getEmailPreviews(filter);
      setPreviews(previewData);
    } catch (error) {
      console.error('Error loading previews:', error);
      toast({
        title: 'Error loading email previews',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsLoadingPreviews(false);
    }
  };
  
  // Toggle email selection
  const toggleEmailSelection = (emailId: string) => {
    setSelectedEmails(prev => 
      prev.includes(emailId)
        ? prev.filter(id => id !== emailId)
        : [...prev, emailId]
    );
  };
  
  // Select all emails
  const selectAllEmails = () => {
    if (selectedEmails.length === previews.length) {
      setSelectedEmails([]);
    } else {
      setSelectedEmails(previews.map(email => email.id));
    }
  };
  
  // Submit selected emails for analysis
  const handleSubmitForAnalysis = async () => {
    if (selectedEmails.length === 0) {
      toast({
        title: 'No emails selected',
        description: 'Please select at least one email for analysis',
        status: 'warning',
        duration: 3000,
      });
      return;
    }
    
    setIsSubmitting(true);
    try {
      await analyzeEmails(selectedEmails);
      toast({
        title: 'Emails submitted for analysis',
        description: `${selectedEmails.length} emails are being processed`,
        status: 'success',
        duration: 3000,
      });
      navigate('/review');
    } catch (error) {
      console.error('Error submitting emails:', error);
      toast({
        title: 'Error submitting emails',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <Box bg={colorMode === 'dark' ? 'dark.bg' : 'gray.50'} minH="calc(100vh - 64px)" py={8}>
      <Container maxW="container.xl">
        <VStack spacing={8} align="stretch">
          <Box>
            <Heading size="lg" mb={2}>Select Emails to Analyze</Heading>
            <Text color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>Filter and select emails to process for your knowledge base</Text>
          </Box>
          
          {/* Filter Card */}
          <Card borderRadius="xl" boxShadow="md" bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} overflow="hidden" borderTop="4px solid" borderTopColor="primary.500">
            <CardHeader bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} pb={0}>
              <Flex align="center">
                <Icon as={FaFilter} color="primary.500" mr={2} />
                <Heading size="md">Email Filters</Heading>
              </Flex>
            </CardHeader>
            <CardBody>
              <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" }} gap={6}>
                <GridItem>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaEnvelope} color="primary.500" mr={2} />
                      Folder
                    </FormLabel>
                    {isLoadingFolders ? (
                      <Spinner size="sm" color="primary.500" />
                    ) : (
                      <Select 
                        name="folder_id" 
                        value={filter.folder_id} 
                        onChange={handleFilterChange}
                        placeholder="Select folder"
                        focusBorderColor="primary.400"
                        bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                        borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                      >
                        {folders.map(folder => (
                          <option key={folder.id} value={folder.id}>
                            {folder.displayName}
                          </option>
                        ))}
                      </Select>
                    )}
                  </FormControl>
                </GridItem>
                
                <GridItem>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaUserAlt} color="primary.500" mr={2} />
                      Sender
                    </FormLabel>
                    <Input 
                      name="sender" 
                      value={filter.sender || ''} 
                      onChange={handleFilterChange}
                      placeholder="Enter sender email"
                      focusBorderColor="primary.400"
                      bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                      borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                    />
                  </FormControl>
                </GridItem>
                
                <GridItem>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaCalendarAlt} color="primary.500" mr={2} />
                      Start Date
                    </FormLabel>
                    <Input 
                      name="start_date" 
                      type="date" 
                      value={filter.start_date || ''} 
                      onChange={handleFilterChange}
                      focusBorderColor="primary.400"
                      bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                      borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                    />
                  </FormControl>
                </GridItem>
                
                <GridItem>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaCalendarAlt} color="primary.500" mr={2} />
                      End Date
                    </FormLabel>
                    <Input 
                      name="end_date" 
                      type="date" 
                      value={filter.end_date || ''} 
                      onChange={handleFilterChange}
                      focusBorderColor="primary.400"
                      bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                      borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                    />
                  </FormControl>
                </GridItem>
                
                <GridItem colSpan={{ base: 1, md: 2 }}>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaTag} color="primary.500" mr={2} />
                      Keywords
                    </FormLabel>
                    <InputGroup>
                      <Input 
                        value={keywordInput} 
                        onChange={(e) => setKeywordInput(e.target.value)}
                        placeholder="Add keyword"
                        onKeyPress={(e) => e.key === 'Enter' && handleAddKeyword()}
                        focusBorderColor="primary.400"
                        bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                        borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                      />
                      <InputRightElement>
                        <IconButton
                          aria-label="Add keyword"
                          icon={<AddIcon />}
                          size="sm"
                          colorScheme="primary"
                          variant="ghost"
                          onClick={handleAddKeyword}
                        />
                      </InputRightElement>
                    </InputGroup>
                    
                    {filter.keywords && filter.keywords.length > 0 && (
                      <Box mt={2}>
                        <HStack spacing={2} flexWrap="wrap">
                          {filter.keywords.map(keyword => (
                            <Tag
                              key={keyword}
                              size="md"
                              borderRadius="full"
                              variant="solid"
                              colorScheme="primary"
                              my={1}
                            >
                              <TagLabel>{keyword}</TagLabel>
                              <TagCloseButton onClick={() => handleRemoveKeyword(keyword)} />
                            </Tag>
                          ))}
                        </HStack>
                      </Box>
                    )}
                  </FormControl>
                </GridItem>
              </Grid>
              
              <Flex justify="flex-end" mt={6}>
                <Button
                  leftIcon={<SearchIcon />}
                  colorScheme="primary"
                  onClick={handlePreviewEmails}
                  isLoading={isLoadingPreviews}
                  loadingText="Searching..."
                  size="md"
                >
                  Search Emails
                </Button>
              </Flex>
            </CardBody>
          </Card>
          
          {/* Results Card */}
          {(previews.length > 0 || isLoadingPreviews) && (
            <Card borderRadius="xl" boxShadow="md" bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} overflow="hidden" borderTop="4px solid" borderTopColor="primary.500">
              <CardHeader bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} pb={0}>
                <Flex align="center" justify="space-between">
                  <Flex align="center">
                    <Icon as={FaSearch} color="primary.500" mr={2} />
                    <Heading size="md">Search Results</Heading>
                  </Flex>
                  <HStack>
                    <Button
                      size="sm"
                      variant="outline"
                      colorScheme="primary"
                      onClick={selectAllEmails}
                    >
                      {selectedEmails.length === previews.length ? 'Deselect All' : 'Select All'}
                    </Button>
                    <Button
                      size="sm"
                      colorScheme="primary"
                      leftIcon={<ChevronRightIcon />}
                      onClick={handleSubmitForAnalysis}
                      isLoading={isSubmitting}
                      loadingText="Submitting..."
                      isDisabled={selectedEmails.length === 0}
                    >
                      Analyze Selected
                    </Button>
                  </HStack>
                </Flex>
              </CardHeader>
              <CardBody>
                {isLoadingPreviews ? (
                  <Flex justify="center" align="center" py={10}>
                    <Spinner size="xl" color="primary.500" thickness="4px" />
                  </Flex>
                ) : (
                  <Box overflowX="auto">
                    <Table variant="simple">
                      <Thead bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'gray.50'}>
                        <Tr>
                          <Th width="50px" px={2}>
                            <Checkbox
                              isChecked={selectedEmails.length === previews.length && previews.length > 0}
                              isIndeterminate={selectedEmails.length > 0 && selectedEmails.length < previews.length}
                              onChange={selectAllEmails}
                              colorScheme="primary"
                            />
                          </Th>
                          <Th>Subject</Th>
                          <Th>Sender</Th>
                          <Th>Date</Th>
                          <Th>Preview</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {previews.map(email => (
                          <Tr 
                            key={email.id}
                            _hover={{ bg: colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'gray.50' }}
                            cursor="pointer"
                            onClick={() => toggleEmailSelection(email.id)}
                          >
                            <Td px={2}>
                              <Checkbox
                                isChecked={selectedEmails.includes(email.id)}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  toggleEmailSelection(email.id);
                                }}
                                colorScheme="primary"
                              />
                            </Td>
                            <Td fontWeight={selectedEmails.includes(email.id) ? "bold" : "normal"}>
                              {email.subject}
                            </Td>
                            <Td>{email.sender}</Td>
                            <Td>{new Date(email.received_date).toLocaleDateString()}</Td>
                            <Td>
                              <Text noOfLines={1} fontSize="sm" color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>
                                {email.snippet}
                              </Text>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                )}
                
                {previews.length > 0 && (
                  <Flex justify="space-between" align="center" mt={4}>
                    <Text color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>
                      {selectedEmails.length} of {previews.length} emails selected
                    </Text>
                    <Button
                      colorScheme="primary"
                      rightIcon={<ChevronRightIcon />}
                      onClick={handleSubmitForAnalysis}
                      isLoading={isSubmitting}
                      loadingText="Submitting..."
                      isDisabled={selectedEmails.length === 0}
                    >
                      Analyze Selected Emails
                    </Button>
                  </Flex>
                )}
              </CardBody>
            </Card>
          )}
        </VStack>
      </Container>
    </Box>
  );
};

export default FilterSetup;
