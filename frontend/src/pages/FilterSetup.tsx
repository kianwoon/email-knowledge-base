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
  
  // Load folders on component mount
  useEffect(() => {
    const loadFolders = async () => {
      setIsLoadingFolders(true);
      try {
        const folderData = await getEmailFolders();
        setFolders(folderData);
        
        // Set default folder to Inbox
        const inboxFolder = folderData.find((folder: EmailFolder) => 
          folder.displayName.toLowerCase() === 'inbox'
        );
        if (inboxFolder) {
          setFilter((prev: EmailFilter) => ({ ...prev, folder_id: inboxFolder.id }));
        }
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
  
  // Load previews when folder changes
  useEffect(() => {
    const loadPreviews = async () => {
      if (!filter.folder_id) return;
      
      setIsLoadingPreviews(true);
      setPreviews([]);
      setSelectedEmails([]);
      try {
        const previewData = await getEmailPreviews(filter);
        if (Array.isArray(previewData)) {
          setPreviews(previewData);
        }
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
    
    loadPreviews();
  }, [filter, toast]);
  
  // Handle filter change
  const handleFilterChange = useCallback((e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFilter((prev: EmailFilter) => ({ ...prev, [name]: value }));
  }, []);
  
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
  
  // Add pagination handlers
  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
  };
  
  // Update the handleSearch function
  const handleSearch = async () => {
    setCurrentPage(1); // Reset to first page on new search
    setIsLoadingPreviews(true);
    setPreviews([]);
    try {
      const previewData = await getEmailPreviews({
        ...filter,
        page: 1,
        per_page: itemsPerPage
      });
      setPreviews(previewData.items || []);
      setTotalEmails(previewData.total);
      setTotalPages(previewData.total_pages);
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
                
                <GridItem>
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
                </GridItem>
                
                <GridItem>
                  <FormControl>
                    <FormLabel fontWeight="medium" display="flex" alignItems="center">
                      <Icon as={FaCalendarAlt} color="primary.500" mr={2} />
                      {t('emailProcessing.filters.startDate')}
                      <Tooltip label={t('emailProcessing.tooltips.dateRangeHelp')} placement="top">
                        <QuestionIcon ml={1} boxSize={3} color="gray.500" />
                      </Tooltip>
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
                      {t('emailProcessing.filters.endDate')}
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
                
                {/* Advanced Filters Toggle */}
                <GridItem colSpan={{ base: 1, md: 3 }}>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                    leftIcon={showAdvancedFilters ? <ChevronRightIcon transform="rotate(90deg)" /> : <ChevronRightIcon />}
                    color="primary.500"
                  >
                    {showAdvancedFilters ? t('Hide Advanced Filters') : t('Show Advanced Filters')}
                  </Button>
                </GridItem>
                
                {/* Advanced Filters */}
                {showAdvancedFilters && (
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
                    
                    <GridItem>
                      <FormControl>
                        <FormLabel fontWeight="medium" display="flex" alignItems="center">
                          <Icon as={FaPaperclip} color="primary.500" mr={2} />
                          {t('emailProcessing.filters.hasAttachments')}
                          <Tooltip label={t('emailProcessing.tooltips.attachmentsHelp')} placement="top">
                            <QuestionIcon ml={1} boxSize={3} color="gray.500" />
                          </Tooltip>
                        </FormLabel>
                        <RadioGroup 
                          onChange={(value) => setFilter(prev => ({ ...prev, has_attachments: value === 'true' ? true : value === 'false' ? false : undefined }))}
                          value={filter.has_attachments === undefined ? '' : String(filter.has_attachments)}
                        >
                          <Stack direction="row">
                            <Radio value="true">{t('emailProcessing.filters.withAttachments')}</Radio>
                            <Radio value="false">{t('emailProcessing.filters.withoutAttachments')}</Radio>
                            <Radio value="">{t('emailProcessing.filters.any')}</Radio>
                          </Stack>
                        </RadioGroup>
                      </FormControl>
                    </GridItem>
                    
                    <GridItem>
                      <FormControl>
                        <FormLabel fontWeight="medium" display="flex" alignItems="center">
                          <Icon as={FaPaperclip} color="primary.500" mr={2} />
                          {t('emailProcessing.filters.attachmentType')}
                        </FormLabel>
                        <Select
                          name="attachment_type"
                          value={filter.attachment_type || ''}
                          onChange={handleFilterChange}
                          placeholder={t('emailProcessing.filters.selectAttachmentType')}
                          focusBorderColor="primary.400"
                          bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                          borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                          isDisabled={filter.has_attachments === false}
                        >
                          {attachmentTypes.map(type => (
                            <option key={type.value} value={type.value}>
                              {type.label}
                            </option>
                          ))}
                        </Select>
                      </FormControl>
                    </GridItem>
                    
                    <GridItem colSpan={{ base: 1, md: 3 }}>
                      <FormControl>
                        <FormLabel fontWeight="medium" display="flex" alignItems="center">
                          <Icon as={FaCode} color="primary.500" mr={2} />
                          {t('emailProcessing.filters.advancedQuery')}
                          <Tooltip label={t('emailProcessing.tooltips.advancedQueryHelp')} placement="top">
                            <QuestionIcon ml={1} boxSize={3} color="gray.500" />
                          </Tooltip>
                        </FormLabel>
                        <Textarea
                          name="advanced_query"
                          value={filter.advanced_query || ''}
                          onChange={handleFilterChange}
                          placeholder={t('emailProcessing.filters.enterQuery')}
                          focusBorderColor="primary.400"
                          bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                          borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                          size="sm"
                          rows={3}
                        />
                        <Text fontSize="xs" color="gray.500" mt={1}>
                          {t('emailProcessing.tooltips.queryExample')}
                        </Text>
                      </FormControl>
                    </GridItem>
                    
                    {/* Filter Templates */}
                    <GridItem colSpan={{ base: 1, md: 3 }}>
                      <FormControl>
                        <FormLabel fontWeight="medium" display="flex" alignItems="center">
                          <Icon as={FaSave} color="primary.500" mr={2} />
                          {t('emailProcessing.filters.templates')}
                        </FormLabel>
                        <Flex gap={2}>
                          <Button
                            leftIcon={<FaSave />}
                            colorScheme="primary"
                            variant="outline"
                            size="sm"
                            onClick={() => setShowSaveTemplateModal(true)}
                          >
                            {t('emailProcessing.filters.saveTemplate')}
                          </Button>
                          <Select
                            placeholder={t('emailProcessing.filters.loadTemplate')}
                            size="sm"
                            onChange={(e) => {
                              if (e.target.value) {
                                const template = filterTemplates.find(t => t.id === e.target.value);
                                if (template) {
                                  setFilter(template.filter);
                                  toast({
                                    title: t('emailProcessing.notifications.templateLoaded.title'),
                                    description: t('emailProcessing.notifications.templateLoaded.description'),
                                    status: 'success',
                                    duration: 3000,
                                  });
                                }
                              }
                            }}
                            focusBorderColor="primary.400"
                            bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                            borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                          >
                            {filterTemplates.map(template => (
                              <option key={template.id} value={template.id}>
                                {template.name}
                              </option>
                            ))}
                          </Select>
                        </Flex>
                      </FormControl>
                    </GridItem>
                  </>
                )}
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
          {previews.length > 0 && (
            <Card borderRadius="xl" boxShadow="md" bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} overflow="hidden">
              <CardHeader bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} pb={0}>
                <Flex justify="space-between" align="center">
                  <Flex align="center">
                    <Icon as={FaSearch} color="primary.500" mr={2} />
                    <Heading size="md">{t('emailProcessing.results.title')}</Heading>
                  </Flex>
                  <HStack>
                    <Text fontSize="sm">
                      {t('emailProcessing.results.showing')} {(currentPage - 1) * itemsPerPage + 1}-{Math.min(currentPage * itemsPerPage, totalEmails)} {t('emailProcessing.results.of')} {totalEmails}
                    </Text>
                    <Button
                      colorScheme="primary"
                      variant="outline"
                      leftIcon={<SearchIcon />}
                      onClick={handleSearch}
                      isLoading={isLoadingPreviews}
                    >
                      {t('emailProcessing.actions.refresh')}
                    </Button>
                  </HStack>
                </Flex>
              </CardHeader>
              <CardBody>
                {previews.length === 0 ? (
                  <Flex direction="column" align="center" justify="center" py={10}>
                    <Text color="gray.500">{t('emailProcessing.results.noResults')}</Text>
                  </Flex>
                ) : (
                  <Box overflowX="auto">
                    <Table variant="simple" size="sm">
                      <Thead>
                        <Tr>
                          <Th width="40px">
                            <Checkbox 
                              isChecked={selectedEmails.length === previews.length && previews.length > 0}
                              isIndeterminate={selectedEmails.length > 0 && selectedEmails.length < previews.length}
                              onChange={selectAllEmails}
                              colorScheme="primary"
                            />
                          </Th>
                          <Th>{t('emailProcessing.results.sender')}</Th>
                          <Th>{t('emailProcessing.results.subject')}</Th>
                          <Th>{t('emailProcessing.results.date')}</Th>
                          <Th>{t('emailProcessing.results.hasAttachments')}</Th>
                          <Th>{t('emailProcessing.results.importance')}</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {previews.map(email => (
                          <Tr key={email.id}>
                            <Td>
                              <Checkbox 
                                isChecked={selectedEmails.includes(email.id)}
                                onChange={() => toggleEmailSelection(email.id)}
                                colorScheme="primary"
                              />
                            </Td>
                            <Td>{email.sender}</Td>
                            <Td>{email.subject}</Td>
                            <Td>{new Date(email.received_date).toLocaleDateString()}</Td>
                            <Td>{email.has_attachments ? t('common.yes') : t('common.no')}</Td>
                            <Td>{email.importance}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                )}
                
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
