import React, { useState, useEffect, useCallback } from 'react';
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
  Grid,
  GridItem,
  Heading,
  HStack,
  Icon,
  IconButton,
  Input,
  InputGroup,
  InputRightElement,
  Select,
  Spinner,
  Stack,
  Tag,
  TagCloseButton,
  TagLabel,
  Text,
  Textarea,
  Tooltip,
  useColorMode,
  useToast,
  Radio,
  RadioGroup,
  VStack,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  ButtonGroup,
  Collapse,
  Skeleton,
  SkeletonText,
} from '@chakra-ui/react';
import { 
  AddIcon, 
  ChevronRightIcon, 
  QuestionIcon,
  SearchIcon,
  MoonIcon,
  SunIcon,
  ChevronLeftIcon,
  ChevronRightIcon as ChevronRightIconSolid,
} from '@chakra-ui/icons';
import {
  FaEnvelope,
  FaUserAlt,
  FaCalendarAlt,
  FaTag,
  FaFilter,
  FaSearch,
  FaExclamationCircle,
  FaPaperclip,
  FaCode,
  FaSave,
} from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { v4 as uuidv4 } from 'uuid';
import LanguageSwitcher from '../components/LanguageSwitcher';

import { getEmailFolders, getEmailPreviews, analyzeEmails } from '../api/email';
import { EmailFilter, EmailPreview } from '../types/email';

interface EmailFolder {
  id: string;
  displayName: string;
}

interface FilterTemplate {
  id: string;
  name: string;
  filter: EmailFilter;
}

const EmailTableSkeleton = () => (
  <Table variant="simple">
    <Thead>
      <Tr height="48px">
        <Th width="40px">
          <Skeleton height="20px" width="20px" />
        </Th>
        <Th width="200px">
          <Skeleton height="20px" />
        </Th>
        <Th width="300px">
          <Skeleton height="20px" />
        </Th>
        <Th width="120px">
          <Skeleton height="20px" />
        </Th>
        <Th width="120px">
          <Skeleton height="20px" />
        </Th>
        <Th width="120px">
          <Skeleton height="20px" />
        </Th>
      </Tr>
    </Thead>
    <Tbody>
      {[...Array(10)].map((_, index) => (
        <Tr key={index} height="48px">
          <Td>
            <Skeleton height="20px" width="20px" />
          </Td>
          <Td>
            <Skeleton height="20px" width="180px" />
          </Td>
          <Td>
            <Skeleton height="20px" width="280px" />
          </Td>
          <Td>
            <Skeleton height="20px" width="100px" />
          </Td>
          <Td>
            <Skeleton height="20px" width="40px" />
          </Td>
          <Td>
            <Skeleton height="20px" width="80px" />
          </Td>
        </Tr>
      ))}
    </Tbody>
  </Table>
);

const FilterSetup: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { colorMode, toggleColorMode } = useColorMode();
  const toast = useToast();
  
  // State
  const [folders, setFolders] = useState<EmailFolder[]>([]);
  const [filter, setFilter] = useState<EmailFilter>({
    folder_id: '',
    keywords: [],
  });
  const [keywordInput, setKeywordInput] = useState('');
  const [previews, setPreviews] = useState<EmailPreview[]>([]);
  const [selectedEmails, setSelectedEmails] = useState<string[]>([]);
  const [isLoadingFolders, setIsLoadingFolders] = useState(false);
  const [isLoadingPreviews, setIsLoadingPreviews] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [filterTemplates, setFilterTemplates] = useState<FilterTemplate[]>([]);
  const [templateName, setTemplateName] = useState('');
  const [showSaveTemplateModal, setShowSaveTemplateModal] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalEmails, setTotalEmails] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const itemsPerPage = 10;
  const [isEndDateDisabled, setIsEndDateDisabled] = useState(true);
  const [dateError, setDateError] = useState<string | null>(null);
  
  // Attachment types
  const attachmentTypes = [
    { value: 'pdf', label: 'PDF' },
    { value: 'doc', label: t('emailProcessing.filters.wordDocument') },
    { value: 'xls', label: t('emailProcessing.filters.excelSpreadsheet') },
    { value: 'ppt', label: t('emailProcessing.filters.powerPoint') },
    { value: 'image', label: t('emailProcessing.filters.image') },
    { value: 'zip', label: t('emailProcessing.filters.archive') },
  ];
  
  // Importance levels
  const importanceLevels = [
    { value: 'high', label: t('emailProcessing.filters.high') },
    { value: 'normal', label: t('emailProcessing.filters.normal') },
    { value: 'low', label: t('emailProcessing.filters.low') },
  ];
  
  // Handle filter change
  const handleFilterChange = useCallback((e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    
    if (name === 'start_date' || name === 'end_date') {
      // Clear any existing date errors
      setDateError(null);
      
      if (value) {
        try {
          // Create date object and format it correctly for Microsoft Graph API
          const date = new Date(value);
          let formattedDate: string;
          
          if (name === 'start_date') {
            // Set to start of day (00:00:00) UTC
            date.setUTCHours(0, 0, 0, 0);
            formattedDate = date.toISOString().replace(/\.\d{3}Z$/, 'Z');
          } else {
            // Set to end of day (23:59:59) UTC
            date.setUTCHours(23, 59, 59, 999);
            formattedDate = date.toISOString().replace(/\.\d{3}Z$/, 'Z');
          }
          
          // Validate date range if both dates are set
          if (name === 'start_date' && filter.end_date) {
            const endDate = new Date(filter.end_date);
            if (date > endDate) {
              setDateError('Start date cannot be after end date');
              return;
            }
          } else if (name === 'end_date' && filter.start_date) {
            const startDate = new Date(filter.start_date);
            if (date < startDate) {
              setDateError('End date cannot be before start date');
              return;
            }
          }
          
          setFilter(prev => ({ ...prev, [name]: formattedDate }));
        } catch (error) {
          console.error('Error parsing date:', error);
          setDateError('Invalid date format');
        }
      } else {
        setFilter(prev => ({ ...prev, [name]: undefined }));
      }
      return;
    }

    setFilter(prev => ({ ...prev, [name]: value }));
  }, [filter.end_date, filter.start_date]);

  // Load previews
  const loadPreviews = useCallback(async () => {
    if (isInitialLoad) {
      setIsInitialLoad(false);
      return;
    }

    setIsLoadingPreviews(true);
    try {
      // Format the filter with proper date handling for Microsoft Graph API
      const formattedFilter = {
        ...filter,
        // Dates are already in the correct format from handleFilterChange
        start_date: filter.start_date,
        end_date: filter.end_date,
        page: currentPage,
        per_page: itemsPerPage
      };

      console.log('Sending filter with dates:', {
        start_date: formattedFilter.start_date,
        end_date: formattedFilter.end_date
      });

      const previewData = await getEmailPreviews(formattedFilter);

      // Update state with response data
      setPreviews(previewData.items || []);
      setTotalEmails(previewData.total);
      setTotalPages(previewData.total_pages);
    } catch (error: any) {
      console.error('Error loading previews:', error);
      // Extract error message properly
      let errorMessage = 'Failed to load email previews';
      if (error.response?.data?.detail) {
        errorMessage = typeof error.response.data.detail === 'string' 
          ? error.response.data.detail 
          : 'Server error occurred';
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast({
        title: 'Error loading email previews',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setPreviews([]);
      setTotalEmails(0);
      setTotalPages(0);
    } finally {
      setIsLoadingPreviews(false);
    }
  }, [currentPage, filter, itemsPerPage, isInitialLoad, toast]);

  // Remove the useEffect that watches filter changes
  useEffect(() => {
    const loadFolders = async () => {
      setIsLoadingFolders(true);
      try {
        const folderData = await getEmailFolders();
        setFolders(folderData);
      } catch (error) {
        console.error('Error loading folders:', error);
        toast({
          title: t('common.error'),
          description: t('Error loading email folders'),
          status: 'error',
          duration: 3000,
        });
      } finally {
        setIsLoadingFolders(false);
      }
    };
    
    loadFolders();
  }, [t, toast]);

  // Add pagination handlers
  const handlePageChange = useCallback((newPage: number) => {
    setCurrentPage(newPage);
    loadPreviews();
  }, [loadPreviews]);

  // Define handleSearch with useCallback
  const handleSearch = useCallback(async () => {
    // Reset error state
    setDateError(null);

    // Validate dates if either is set
    if (filter.start_date || filter.end_date) {
      // Both dates must be set if one is set
      if (!filter.start_date || !filter.end_date) {
        setDateError('Please select both start and end dates');
        return;
      }

      const startDate = new Date(filter.start_date);
      const endDate = new Date(filter.end_date);
      
      // Validate date range
      if (endDate < startDate) {
        setDateError('End date cannot be before start date');
        return;
      }
    }

    setCurrentPage(1); // Reset to first page on new search
    loadPreviews();
  }, [filter.start_date, filter.end_date, loadPreviews]);
  
  // Add keyword to filter
  const handleAddKeyword = () => {
    if (keywordInput.trim() && !filter.keywords?.includes(keywordInput.trim())) {
      setFilter((prev: EmailFilter) => ({
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
  
  // Toggle email selection
  const toggleEmailSelection = (emailId: string) => {
    setSelectedEmails(prev => 
      prev.includes(emailId)
        ? prev.filter(id => id !== emailId)
        : [...prev, emailId]
    );
  };
  
  // Select or deselect all emails
  const selectAllEmails = () => {
    if (selectedEmails.length === previews.length) {
      // Deselect all
      setSelectedEmails([]);
    } else {
      // Select all
      setSelectedEmails(previews.map(email => email.id));
    }
  };
  
  // Submit selected emails for analysis
  const handleAnalyzeEmails = async () => {
    if (selectedEmails.length === 0) {
      toast({
        title: t('emailProcessing.notifications.noEmailsSelected.title'),
        description: t('emailProcessing.notifications.noEmailsSelected.description'),
        status: 'warning',
        duration: 3000,
      });
      return;
    }
    
    setIsSubmitting(true);
    try {
      await analyzeEmails(selectedEmails);
      toast({
        title: t('emailProcessing.notifications.emailsSubmitted.title'),
        description: t('emailProcessing.notifications.emailsSubmitted.description'),
        status: 'success',
        duration: 3000,
      });
      navigate('/review');
    } catch (error) {
      console.error('Error submitting emails for analysis:', error);
      toast({
        title: t('common.error'),
        description: t('Error submitting emails for analysis'),
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Handle saving filter template
  const handleSaveTemplate = useCallback(() => {
    if (!templateName.trim()) {
      toast({
        title: t('emailProcessing.notifications.templateError.title'),
        description: t('emailProcessing.notifications.templateError.description'),
        status: 'error',
        duration: 3000,
      });
      return;
    }
    
    const newTemplate = {
      id: uuidv4(),
      name: templateName,
      filter: { ...filter }
    };
    
    setFilterTemplates(prev => [...prev, newTemplate]);
    setTemplateName('');
    setShowSaveTemplateModal(false);
    
    toast({
      title: t('emailProcessing.notifications.templateSaved.title'),
      description: t('emailProcessing.notifications.templateSaved.description'),
      status: 'success',
      duration: 3000,
    });
    
    // Save to localStorage
    try {
      const existingTemplates = JSON.parse(localStorage.getItem('emailFilterTemplates') || '[]');
      localStorage.setItem('emailFilterTemplates', JSON.stringify([...existingTemplates, newTemplate]));
    } catch (error) {
      console.error('Error saving template to localStorage:', error);
    }
  }, [filter, templateName, toast, t]);
  
  // Load templates from localStorage on component mount
  useEffect(() => {
    try {
      const savedTemplates = localStorage.getItem('emailFilterTemplates');
      if (savedTemplates) {
        setFilterTemplates(JSON.parse(savedTemplates));
      }
    } catch (error) {
      console.error('Error loading templates from localStorage:', error);
    }
  }, []);
  
  return (
    <Box bg={colorMode === 'dark' ? 'dark.bg' : 'gray.50'} minH="calc(100vh - 64px)" py={8}>
      <Container maxW="1400px" py={8}>
        <VStack spacing={6} align="stretch">
          <Flex justify="space-between" align="center">
            <Heading size="lg" fontWeight="bold">
              {t('emailProcessing.filters.title')}
            </Heading>
          </Flex>
          
          {/* Filter Card */}
          <Card borderRadius="xl" boxShadow="md" bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} overflow="hidden" borderTop="4px solid" borderTopColor="primary.500">
            <CardHeader bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} pb={0}>
              <Flex align="center">
                <Icon as={FaFilter} color="primary.500" mr={2} />
                <Heading size="md">{t('emailProcessing.filters.title')}</Heading>
              </Flex>
            </CardHeader>
            <CardBody>
              <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" }} gap={6}>
                <GridItem>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaEnvelope} color="primary.500" mr={2} />
                      {t('emailProcessing.filters.folder')}
                      <Tooltip label={t('emailProcessing.tooltips.folderHelp')} placement="top">
                        <QuestionIcon ml={1} boxSize={3} color="gray.500" />
                      </Tooltip>
                    </FormLabel>
                    {isLoadingFolders ? (
                      <Spinner size="sm" color="primary.500" />
                    ) : (
                      <Select 
                        name="folder_id" 
                        value={filter.folder_id} 
                        onChange={handleFilterChange}
                        placeholder={t('emailProcessing.filters.selectFolder')}
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
                
                {/* Hide sender filter */}
                {/* <GridItem>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaUserAlt} color="primary.500" mr={2} />
                      {t('emailProcessing.filters.sender')}
                      <Tooltip label={t('emailProcessing.tooltips.senderHelp')} placement="top">
                        <QuestionIcon ml={1} boxSize={3} color="gray.500" />
                      </Tooltip>
                    </FormLabel>
                    <Input 
                      name="sender" 
                      value={filter.sender || ''} 
                      onChange={handleFilterChange}
                      placeholder={t('emailProcessing.filters.enterSender')}
                      focusBorderColor="primary.400"
                      bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                      borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                    />
                  </FormControl>
                </GridItem> */}
                
                <GridItem>
                  <FormControl isInvalid={!!dateError}>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaCalendarAlt} color="primary.500" mr={2} />
                      {t('emailProcessing.filters.dateRange')}
                    </FormLabel>
                    <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                      <Input
                        type="date"
                        name="start_date"
                        value={filter.start_date ? filter.start_date.split('T')[0] : ''}
                        onChange={handleFilterChange}
                        placeholder={t('emailProcessing.filters.startDate')}
                        max={filter.end_date ? filter.end_date.split('T')[0] : undefined}
                        focusBorderColor="primary.400"
                        bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                        borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                      />
                      <Input
                        type="date"
                        name="end_date"
                        value={filter.end_date ? filter.end_date.split('T')[0] : ''}
                        onChange={handleFilterChange}
                        placeholder={t('emailProcessing.filters.endDate')}
                        min={filter.start_date ? filter.start_date.split('T')[0] : undefined}
                        focusBorderColor="primary.400"
                        bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                        borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                      />
                    </Grid>
                    {dateError && (
                      <Text color="red.500" fontSize="sm" mt={1}>
                        {dateError}
                      </Text>
                    )}
                  </FormControl>
                </GridItem>
                
                <GridItem colSpan={{ base: 1, md: 2 }}>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaTag} color="primary.500" mr={2} />
                      {t('emailProcessing.filters.keywords')}
                      <Tooltip label={t('emailProcessing.tooltips.keywordsHelp')} placement="top">
                        <QuestionIcon ml={1} boxSize={3} color="gray.500" />
                      </Tooltip>
                    </FormLabel>
                    <InputGroup>
                      <Input 
                        value={keywordInput} 
                        onChange={(e) => setKeywordInput(e.target.value)}
                        placeholder={t('emailProcessing.filters.addKeyword')}
                        onKeyPress={(e) => e.key === 'Enter' && handleAddKeyword()}
                        focusBorderColor="primary.400"
                        bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                        borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                      />
                      <InputRightElement>
                        <IconButton
                          aria-label={t('emailProcessing.filters.addKeyword')}
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
                
                {/* Hide Advanced Filters Toggle */}
                {/* <GridItem colSpan={{ base: 1, md: 3 }}>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                    leftIcon={showAdvancedFilters ? <ChevronRightIcon transform="rotate(90deg)" /> : <ChevronRightIcon />}
                    color="primary.500"
                  >
                    {showAdvancedFilters ? t('Hide Advanced Filters') : t('Show Advanced Filters')}
                  </Button>
                </GridItem> */}
                
                {/* Hide Advanced Filters Section */}
                {/* {showAdvancedFilters && (
                  <>
                    <GridItem>
                      <FormControl>
                        <FormLabel fontWeight="medium" display="flex" alignItems="center">
                          <Icon as={FaExclamationCircle} color="primary.500" mr={2} />
                          {t('emailProcessing.filters.importance')}
                          <Tooltip label={t('emailProcessing.tooltips.importanceHelp')} placement="top">
                            <QuestionIcon ml={1} boxSize={3} color="gray.500" />
                          </Tooltip>
                        </FormLabel>
                        <Select
                          name="importance"
                          value={filter.importance || ''}
                          onChange={handleFilterChange}
                          placeholder={t('emailProcessing.filters.selectImportance')}
                          focusBorderColor="primary.400"
                          bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                          borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                        >
                          {importanceLevels.map(level => (
                            <option key={level.value} value={level.value}>
                              {level.label}
                            </option>
                          ))}
                        </Select>
                      </FormControl>
                    </GridItem>
                  </>
                )} */}
              </Grid>
              
              <Flex justify="flex-end" mt={6}>
                <Button
                  leftIcon={<SearchIcon />}
                  colorScheme="primary"
                  onClick={handleSearch}
                  isLoading={isLoadingPreviews}
                  loadingText={t('emailProcessing.actions.searching')}
                  size="md"
                  w="full"
                >
                  {t('emailProcessing.actions.search')}
                </Button>
              </Flex>
            </CardBody>
          </Card>
          
          {/* Results Card */}
          {(previews.length > 0 || isLoadingPreviews) && (
            <Card borderRadius="xl" boxShadow="md" bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} overflow="hidden">
              <CardHeader bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} pb={0}>
                <Flex justify="space-between" align="center">
                  <Flex align="center">
                    <Icon as={FaSearch} color="primary.500" mr={2} />
                    <Heading size="md">{t('emailProcessing.results.title')}</Heading>
                  </Flex>
                  <Text color="gray.500">
                    {t('emailProcessing.results.viewing')} {(currentPage - 1) * itemsPerPage + 1} - {Math.min(currentPage * itemsPerPage, totalEmails)} {t('emailProcessing.results.of')} {totalEmails}
                  </Text>
                </Flex>
              </CardHeader>
              <CardBody>
                <Box overflowX="auto">
                  {isLoadingPreviews ? (
                    <EmailTableSkeleton />
                  ) : previews.length > 0 ? (
                    <Table variant="simple">
                      <Thead>
                        <Tr height="48px">
                          <Th width="40px">
                            <Checkbox
                              isChecked={selectedEmails.length === previews.length && previews.length > 0}
                              onChange={selectAllEmails}
                              colorScheme="primary"
                            />
                          </Th>
                          <Th width="200px">{t('emailProcessing.results.sender')}</Th>
                          <Th width="300px">{t('emailProcessing.results.subject')}</Th>
                          <Th width="120px">{t('emailProcessing.results.date')}</Th>
                          <Th width="120px">{t('emailProcessing.results.hasAttachments')}</Th>
                          <Th width="120px">{t('emailProcessing.results.importance')}</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {previews.map(email => (
                          <Tr key={email.id} height="48px">
                            <Td>
                              <Checkbox 
                                isChecked={selectedEmails.includes(email.id)}
                                onChange={() => toggleEmailSelection(email.id)}
                                colorScheme="primary"
                              />
                            </Td>
                            <Td>
                              <Text noOfLines={1} title={email.sender}>
                                {email.sender}
                              </Text>
                            </Td>
                            <Td>
                              <Text noOfLines={1} title={email.subject}>
                                {email.subject}
                              </Text>
                            </Td>
                            <Td>
                              <Text noOfLines={1}>
                                {new Date(email.received_date).toLocaleDateString()}
                              </Text>
                            </Td>
                            <Td>
                              <Text noOfLines={1}>
                                {email.has_attachments ? t('common.yes') : t('common.no')}
                              </Text>
                            </Td>
                            <Td>
                              <Text noOfLines={1}>
                                {email.importance}
                              </Text>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  ) : (
                    <Text textAlign="center" py={4} color="gray.500">
                      {t('emailProcessing.results.noEmails')}
                    </Text>
                  )}
                </Box>
                
                {/* Add pagination controls */}
                <Flex justify="space-between" align="center" mt={4}>
                  <Text fontSize="sm">
                    {selectedEmails.length} {t('emailProcessing.results.selected')}
                  </Text>
                  <HStack spacing={2}>
                    <ButtonGroup variant="outline" size="sm" isAttached>
                      <Button
                        onClick={() => handlePageChange(1)}
                        isDisabled={currentPage === 1 || isLoadingPreviews}
                      >
                        <ChevronLeftIcon />
                        <ChevronLeftIcon ml="-1.5" />
                      </Button>
                      <Button
                        onClick={() => handlePageChange(currentPage - 1)}
                        isDisabled={currentPage === 1 || isLoadingPreviews}
                      >
                        <ChevronLeftIcon />
                      </Button>
                      <Button
                        onClick={() => handlePageChange(currentPage + 1)}
                        isDisabled={currentPage === totalPages || isLoadingPreviews}
                      >
                        <ChevronRightIconSolid />
                      </Button>
                      <Button
                        onClick={() => handlePageChange(totalPages)}
                        isDisabled={currentPage === totalPages || isLoadingPreviews}
                      >
                        <ChevronRightIconSolid />
                        <ChevronRightIconSolid ml="-1.5" />
                      </Button>
                    </ButtonGroup>
                    <Text fontSize="sm" minW="100px" textAlign="center">
                      {t('emailProcessing.results.page')} {currentPage} {t('emailProcessing.results.of')} {totalPages}
                    </Text>
                  </HStack>
                  <Button
                    colorScheme="primary"
                    leftIcon={<Icon as={FaExclamationCircle} />}
                    onClick={handleAnalyzeEmails}
                    isLoading={isSubmitting}
                    loadingText={t('emailProcessing.actions.analyzing')}
                    isDisabled={selectedEmails.length === 0}
                  >
                    {t('emailProcessing.actions.analyze')}
                  </Button>
                </Flex>
              </CardBody>
            </Card>
          )}
        </VStack>
      </Container>
      
      {/* Save Template Modal */}
      <Modal isOpen={showSaveTemplateModal} onClose={() => setShowSaveTemplateModal(false)}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('emailProcessing.filters.saveTemplateTitle')}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>{t('emailProcessing.filters.templateName')}</FormLabel>
              <Input 
                value={templateName} 
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder={t('emailProcessing.filters.enterTemplateName')}
              />
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={() => setShowSaveTemplateModal(false)}>
              {t('Cancel')}
            </Button>
            <Button colorScheme="primary" onClick={handleSaveTemplate}>
              {t('Save')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default FilterSetup;
