import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Container,
  Divider,
  Flex,
  FormLabel,
  Heading,
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
  Checkbox,
  Select,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Textarea,
  useDisclosure,
  IconButton,
  useColorMode,
  ButtonGroup,
  List,
  ListItem,
  ListIcon,
} from '@chakra-ui/react';
import { CheckIcon, CloseIcon, ViewIcon, ChevronLeftIcon, ChevronRightIcon, InfoIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';

import axios from 'axios';
import { ReviewStatus, SensitivityLevel, Department, EmailReviewItem, EmailApproval, PIIType } from '../types/email';

// Mock API functions (in a real app, these would be in the API directory)
const getPendingReviews = async (params: { page?: number; per_page?: number } = {}) => {
  // Get translation function
  const { t } = useTranslation();
  
  // Mock data for demonstration
  const itemsPerPage = params.per_page || 10;
  const currentPage = params.page || 1;
  const totalItems = 28; // Total number of items in the mock data
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  
  // Calculate start and end indices for the current page
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = Math.min(startIndex + itemsPerPage, totalItems);
  
  // Generate mock data for the current page
  const items = Array(endIndex - startIndex).fill(0).map((_, i) => {
    const itemIndex = startIndex + i;
    return {
      email_id: `email_${itemIndex}`,
      content: {
        id: `email_${itemIndex}`,
        internet_message_id: `message_${itemIndex}`,
        subject: t('emailReview.sampleEmails.subject', { number: itemIndex + 1 }),
        sender: 'John Doe',
        sender_email: 'john.doe@example.com',
        recipients: ['user@example.com'],
        cc_recipients: [],
        received_date: new Date().toISOString(),
        body: t('emailReview.sampleEmails.body', { number: itemIndex + 1 }),
        is_html: false,
        folder_id: 'inbox',
        folder_name: 'Inbox',
        attachments: itemIndex % 3 === 0 ? [{
          id: `attachment_${itemIndex}`,
          name: 'document.pdf',
          content_type: 'application/pdf',
          size: 1024 * 1024,
        }] : [],
        importance: itemIndex % 4 === 0 ? 'high' : 'normal'
      },
      analysis: {
        sensitivity: Object.values(SensitivityLevel)[itemIndex % 4],
        department: Object.values(Department)[itemIndex % 9],
        tags: [`tag${itemIndex}`, 'knowledge', itemIndex % 2 === 0 ? 'important' : 'routine'],
        is_private: itemIndex % 3 === 0,
        pii_detected: itemIndex % 3 === 0 ? [PIIType.EMAIL, PIIType.NAME] : [],
        recommended_action: itemIndex % 3 === 0 ? 'exclude' : 'store',
        summary: t('emailReview.sampleEmails.summary', { number: itemIndex + 1 }),
        key_points: [
          t('emailReview.sampleEmails.keyPoint1', { number: itemIndex + 1 }),
          t('emailReview.sampleEmails.keyPoint2', { number: itemIndex + 1 }),
          t('emailReview.sampleEmails.keyPoint3', { number: itemIndex + 1 })
        ]
      },
      status: ReviewStatus.PENDING
    };
  });
  
  return {
    items,
    total: totalItems,
    total_pages: totalPages,
    current_page: currentPage,
    per_page: itemsPerPage
  };
};

const approveReview = async (emailId: string, approval: EmailApproval) => {
  // Mock API call
  console.log(`Approving email ${emailId} with notes: ${approval.notes}`);
  return { success: true };
};

const bulkApprove = async (emailIds: string[], approval: EmailApproval) => {
  // Mock API call
  console.log(`Bulk approving ${emailIds.length} emails with notes: ${approval.notes}`);
  return { success: true };
};

const EmailReview: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const { colorMode } = useColorMode();
  
  // State
  const [reviews, setReviews] = useState<EmailReviewItem[]>([]);
  const [filteredReviews, setFilteredReviews] = useState<EmailReviewItem[]>([]);
  const [selectedReviews, setSelectedReviews] = useState<string[]>([]);
  const [currentReview, setCurrentReview] = useState<EmailReviewItem | null>(null);
  const [approvalNotes, setApprovalNotes] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const itemsPerPage = 10;
  
  // Filters
  const [filters, setFilters] = useState({
    department: '',
    sensitivity: '',
    isPrivate: '',
  });
  
  // Load reviews on component mount and when page changes
  useEffect(() => {
    const loadReviews = async () => {
      setIsLoading(true);
      try {
        const response = await getPendingReviews({
          page: currentPage,
          per_page: itemsPerPage
        });
        setReviews(response.items);
        setFilteredReviews(response.items);
        setTotalPages(response.total_pages);
        setTotalItems(response.total);
      } catch (error) {
        console.error('Error loading reviews:', error);
        toast({
          title: t('emailReview.toast.loadErrorTitle'),
          status: 'error',
          duration: 3000,
        });
      } finally {
        setIsLoading(false);
      }
    };
    
    loadReviews();
  }, [toast, currentPage, t]);
  
  // Apply filters
  useEffect(() => {
    let filtered = [...reviews];
    
    if (filters.department) {
      filtered = filtered.filter(review => 
        review.analysis.department === filters.department
      );
    }
    
    if (filters.sensitivity) {
      filtered = filtered.filter(review => 
        review.analysis.sensitivity === filters.sensitivity
      );
    }
    
    if (filters.isPrivate !== '') {
      const isPrivate = filters.isPrivate === 'true';
      filtered = filtered.filter(review => 
        review.analysis.is_private === isPrivate
      );
    }
    
    setFilteredReviews(filtered);
  }, [reviews, filters]);
  
  // Handle filter changes
  const handleFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };
  
  // Toggle review selection
  const toggleReviewSelection = (emailId: string) => {
    setSelectedReviews(prev => 
      prev.includes(emailId)
        ? prev.filter(id => id !== emailId)
        : [...prev, emailId]
    );
  };
  
  // Select all reviews
  const selectAllReviews = () => {
    if (selectedReviews.length === filteredReviews.length) {
      setSelectedReviews([]);
    } else {
      setSelectedReviews(filteredReviews.map(review => review.email_id));
    }
  };
  
  // Open review details
  const openReviewDetails = (review: EmailReviewItem) => {
    setCurrentReview(review);
    onOpen();
  };
  
  // Handle approval/rejection of a single review
  const handleReviewDecision = async (emailId: string, approved: boolean) => {
    setIsSubmitting(true);
    try {
      await approveReview(emailId, { approved, notes: approvalNotes });
      
      // Update local state
      setReviews(prev => 
        prev.map(review => 
          review.email_id === emailId
            ? {
                ...review,
                status: approved ? ReviewStatus.APPROVED : ReviewStatus.REJECTED,
                reviewed_at: new Date().toISOString(),
                review_notes: approvalNotes
              }
            : review
        )
      );
      
      toast({
        title: approved ? t('emailReview.toast.approvedSuccess') : t('emailReview.toast.rejectedSuccess'),
        status: approved ? 'success' : 'info',
        duration: 3000,
      });
      
      // Close drawer if open
      if (currentReview?.email_id === emailId) {
        onClose();
        setCurrentReview(null);
      }
      
      // Clear selection
      setSelectedReviews(prev => prev.filter(id => id !== emailId));
      setApprovalNotes('');
    } catch (error) {
      console.error('Error updating review:', error);
      toast({
        title: t('emailReview.toast.updateErrorTitle'),
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Handle bulk approval/rejection
  const handleBulkDecision = async (approved: boolean) => {
    if (selectedReviews.length === 0) {
      toast({
        title: t('emailReview.toast.noSelectionTitle'),
        description: t('emailReview.toast.noSelectionDescription'),
        status: 'warning',
        duration: 3000,
      });
      return;
    }
    
    setIsSubmitting(true);
    try {
      await bulkApprove(selectedReviews, { approved, notes: approvalNotes });
      
      // Update local state
      setReviews(prev => 
        prev.map(review => 
          selectedReviews.includes(review.email_id)
            ? {
                ...review,
                status: approved ? ReviewStatus.APPROVED : ReviewStatus.REJECTED,
                reviewed_at: new Date().toISOString(),
                review_notes: approvalNotes
              }
            : review
        )
      );
      
      toast({
        title: approved
                 ? t('emailReview.toast.bulkApprovedSuccess', { count: selectedReviews.length })
                 : t('emailReview.toast.bulkRejectedSuccess', { count: selectedReviews.length }),
        status: approved ? 'success' : 'info',
        duration: 3000,
      });
      
      // Clear selection and notes
      setSelectedReviews([]);
      setApprovalNotes('');
    } catch (error) {
      console.error('Error updating reviews:', error);
      toast({
        title: t('emailReview.toast.bulkUpdateErrorTitle'),
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Get badge color based on sensitivity
  const getSensitivityColor = (sensitivity: SensitivityLevel) => {
    switch (sensitivity) {
      case SensitivityLevel.LOW:
        return 'green';
      case SensitivityLevel.MEDIUM:
        return 'blue';
      case SensitivityLevel.HIGH:
        return 'orange';
      case SensitivityLevel.CRITICAL:
        return 'red';
      default:
        return 'gray';
    }
  };
  
  // Handle page change
  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
    setSelectedReviews([]); // Clear selections when changing pages
  };
  
  return (
    <Box bg={colorMode === 'dark' ? 'dark.bg' : 'gray.50'} minH="calc(100vh - 64px)" py={8}>
      <Container maxW="container.xl">
        <VStack spacing={8} align="stretch">
          <Box>
            <Heading size="lg" mb={2}>{t('emailReview.pageTitle')}</Heading>
            <Text color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>{t('emailReview.pageDescription')}</Text>
          </Box>
          
          {/* Filters */}
          <Card borderRadius="xl" boxShadow="md" bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} overflow="hidden">
            <CardHeader bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'}>
              <Heading size="md">{t('emailReview.filters.title')}</Heading>
            </CardHeader>
            <CardBody>
              <Flex gap={4} wrap="wrap">
                <Box minW="200px">
                  <Select
                    name="department"
                    value={filters.department}
                    onChange={handleFilterChange}
                    placeholder={t('emailReview.filters.allDepartments')}
                    bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                    borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                  >
                    {Object.values(Department).map(dept => (
                      <option key={dept} value={dept}>
                        {t(`common.departments.${dept.toLowerCase()}`, dept.charAt(0).toUpperCase() + dept.slice(1))}
                      </option>
                    ))}
                  </Select>
                </Box>
                
                <Box minW="200px">
                  <Select
                    name="sensitivity"
                    value={filters.sensitivity}
                    onChange={handleFilterChange}
                    placeholder={t('emailReview.filters.allSensitivityLevels')}
                    bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                    borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                  >
                    {Object.values(SensitivityLevel).map(level => (
                      <option key={level} value={level}>
                        {t(`common.sensitivityLevels.${level.toLowerCase()}`, level.charAt(0).toUpperCase() + level.slice(1))}
                      </option>
                    ))}
                  </Select>
                </Box>
                
                <Box minW="200px">
                  <Select
                    name="isPrivate"
                    value={filters.isPrivate}
                    onChange={handleFilterChange}
                    placeholder={t('emailReview.filters.allPrivacyLevels')}
                    bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                    borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                  >
                    <option value="true">{t('emailReview.privacy.private')}</option>
                    <option value="false">{t('emailReview.privacy.notPrivate')}</option>
                  </Select>
                </Box>
              </Flex>
            </CardBody>
          </Card>
          
          {/* Review Table */}
          <Card borderRadius="xl" boxShadow="md" bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'} overflow="hidden">
            <CardHeader bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'white'}>
              <Flex justify="space-between" align="center">
                <Heading size="md">{t('emailReview.table.title')} ({totalItems})</Heading>
                
                <HStack>
                  <Text fontSize="sm">
                    {t('emailReview.pagination.showingRangeOfTotal', {
                        start: ((currentPage - 1) * itemsPerPage) + 1,
                        end: Math.min(currentPage * itemsPerPage, totalItems),
                        total: totalItems
                    })}
                  </Text>
                  <Button 
                    size="sm" 
                    onClick={selectAllReviews}
                    variant="outline"
                    colorScheme="primary"
                  >
                    {selectedReviews.length === filteredReviews.length ? t('emailReview.actions.deselectAll') : t('emailReview.actions.selectAll')}
                  </Button>
                  
                  {selectedReviews.length > 0 && (
                    <>
                      <Button 
                        size="sm"
                        colorScheme="green"
                        leftIcon={<CheckIcon />}
                        onClick={() => handleBulkDecision(true)}
                        isLoading={isSubmitting}
                      >
                        {t('emailReview.actions.approveSelected')}
                      </Button>
                      
                      <Button 
                        size="sm"
                        colorScheme="red"
                        leftIcon={<CloseIcon />}
                        onClick={() => handleBulkDecision(false)}
                        isLoading={isSubmitting}
                      >
                        {t('emailReview.actions.rejectSelected')}
                      </Button>
                    </>
                  )}
                </HStack>
              </Flex>
            </CardHeader>
            <CardBody>
              {isLoading ? (
                <Flex justify="center" py={8}>
                  <Spinner size="xl" color="primary.500" />
                </Flex>
              ) : filteredReviews.length === 0 ? (
                <Text textAlign="center" py={8} color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>{t('emailReview.table.noResults')}</Text>
              ) : (
                <>
                  <Box overflowX="auto">
                    <Table variant="simple">
                      <Thead bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'gray.100'}>
                        <Tr>
                          <Th width="50px">
                            <Checkbox
                              isChecked={selectedReviews.length === filteredReviews.length && filteredReviews.length > 0}
                              onChange={selectAllReviews}
                              isDisabled={filteredReviews.length === 0}
                            />
                          </Th>
                          <Th>{t('emailReview.table.subject')}</Th>
                          <Th>{t('emailReview.table.department')}</Th>
                          <Th>{t('emailReview.table.sensitivity')}</Th>
                          <Th>{t('emailReview.table.tags')}</Th>
                          <Th>{t('emailReview.table.private')}</Th>
                          <Th>{t('emailReview.table.actions')}</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {filteredReviews.map(review => (
                          <Tr 
                            key={review.email_id}
                            _hover={{ bg: colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'gray.50' }}
                          >
                            <Td>
                              <Checkbox 
                                isChecked={selectedReviews.includes(review.email_id)}
                                onChange={() => toggleReviewSelection(review.email_id)}
                                colorScheme="primary"
                              />
                            </Td>
                            <Td fontWeight="medium">{review.content.subject}</Td>
                            <Td>
                              <Badge>
                                {t(`common.departments.${review.analysis.department.toLowerCase()}`, review.analysis.department)}
                              </Badge>
                            </Td>
                            <Td>
                              <Badge colorScheme={getSensitivityColor(review.analysis.sensitivity)}>
                                {t(`common.sensitivityLevels.${review.analysis.sensitivity.toLowerCase()}`, review.analysis.sensitivity)}
                              </Badge>
                            </Td>
                            <Td>
                              <HStack>
                                {review.analysis.tags.map(tag => (
                                  <Badge key={tag} colorScheme="blue" variant="outline" mx="1">
                                    {t(`common.tags.${tag.toLowerCase()}`, tag)}
                                  </Badge>
                                ))}
                              </HStack>
                            </Td>
                            <Td>
                              <Badge colorScheme={review.analysis.is_private ? 'red' : 'green'}>
                                {review.analysis.is_private ? t('common.yes') : t('common.no')}
                              </Badge>
                            </Td>
                            <Td>
                              <HStack>
                                <IconButton
                                  aria-label={t('emailReview.actions.viewDetails')}
                                  icon={<ViewIcon />}
                                  size="sm"
                                  onClick={() => openReviewDetails(review)}
                                />
                                <IconButton
                                  aria-label={t('emailReview.actions.approve')}
                                  icon={<CheckIcon />}
                                  colorScheme="green"
                                  size="sm"
                                  onClick={() => handleReviewDecision(review.email_id, true)}
                                  isLoading={isSubmitting}
                                />
                                <IconButton
                                  aria-label={t('emailReview.actions.reject')}
                                  icon={<CloseIcon />}
                                  colorScheme="red"
                                  size="sm"
                                  onClick={() => handleReviewDecision(review.email_id, false)}
                                  isLoading={isSubmitting}
                                />
                              </HStack>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                  
                  <Box mt={4}>
                    <FormLabel htmlFor="approval-notes" color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}>{t('emailReview.notes.label')}</FormLabel>
                    <Textarea
                      id="approval-notes"
                      value={approvalNotes}
                      onChange={(e) => setApprovalNotes(e.target.value)}
                      placeholder={t('emailReview.notes.placeholder')}
                      size="sm"
                      bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                      borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                    />
                  </Box>
                  
                  {/* Pagination Controls */}
                  <Flex justify="space-between" align="center" mt={4}>
                    <Text fontSize="sm">
                      {t('emailReview.pagination.selectedCount', { count: selectedReviews.length })}
                    </Text>
                    <HStack spacing={2}>
                      <ButtonGroup variant="outline" size="sm" isAttached>
                        <Button
                          onClick={() => handlePageChange(1)}
                          isDisabled={currentPage === 1 || isLoading}
                        >
                          <ChevronLeftIcon />
                          <ChevronLeftIcon ml="-1.5" />
                        </Button>
                        <Button
                          onClick={() => handlePageChange(currentPage - 1)}
                          isDisabled={currentPage === 1 || isLoading}
                        >
                          <ChevronLeftIcon />
                        </Button>
                        <Button
                          onClick={() => handlePageChange(currentPage + 1)}
                          isDisabled={currentPage === totalPages || isLoading}
                        >
                          <ChevronRightIcon />
                        </Button>
                        <Button
                          onClick={() => handlePageChange(totalPages)}
                          isDisabled={currentPage === totalPages || isLoading}
                        >
                          <ChevronRightIcon />
                          <ChevronRightIcon ml="-1.5" />
                        </Button>
                      </ButtonGroup>
                      <Text fontSize="sm" minW="100px" textAlign="center">
                        {t('emailReview.pagination.pageInfo', { currentPage: currentPage, totalPages: totalPages })}
                      </Text>
                    </HStack>
                  </Flex>
                </>
              )}
            </CardBody>
          </Card>
        </VStack>
      </Container>
      
      {/* Review Details Drawer */}
      <Drawer isOpen={isOpen} placement="right" onClose={onClose} size="lg">
        <DrawerOverlay />
        <DrawerContent bg={colorMode === 'dark' ? 'dark.bg' : 'white'}>
          <DrawerCloseButton />
          <DrawerHeader borderBottomWidth="1px" borderBottomColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}>
            {t('emailReview.drawer.title')}
          </DrawerHeader>
          
          <DrawerBody>
            {currentReview && (
              <VStack spacing={6} align="stretch">
                <Box>
                  <Heading size="md">{currentReview.content.subject}</Heading>
                  <Text color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>
                    {t('emailReview.drawer.from', { sender: currentReview.content.sender, email: currentReview.content.sender_email })}
                  </Text>
                  <Text color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>
                    {t('emailReview.drawer.date', { date: new Date(currentReview.content.received_date).toLocaleString() })}
                  </Text>
                </Box>
                
                <Divider borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'} />
                
                <Box>
                  <Heading size="sm" mb={2}>{t('emailReview.drawer.analysisTitle')}</Heading>
                  
                  <HStack wrap="wrap" mb={2}>
                    <Badge colorScheme={getSensitivityColor(currentReview.analysis.sensitivity)}>
                      {t(`common.sensitivityLevels.${currentReview.analysis.sensitivity.toLowerCase()}`, currentReview.analysis.sensitivity)}
                    </Badge>
                    <Badge>
                      {t(`common.departments.${currentReview.analysis.department.toLowerCase()}`, currentReview.analysis.department)}
                    </Badge>
                    {currentReview.analysis.is_private && (
                      <Badge colorScheme="red">{t('emailReview.privacy.private')}</Badge>
                    )}
                    {currentReview.analysis.pii_detected.length > 0 && (
                      <Badge colorScheme="orange">{t('emailReview.drawer.containsPII')}</Badge>
                    )}
                  </HStack>
                  
                  <HStack wrap="wrap" mb={4}>
                    {currentReview.analysis.tags.map(tag => (
                      <Badge key={tag} colorScheme="blue" variant="outline" mx="1">
                        {t(`common.tags.${tag.toLowerCase()}`, tag)}
                      </Badge>
                    ))}
                  </HStack>
                  
                  <Text fontWeight="bold" color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}>{t('emailReview.drawer.summary')}</Text>
                  <Text mb={2} color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>{currentReview.analysis.summary}</Text>
                  
                  <Text fontWeight="bold" color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}>{t('emailReview.drawer.keyPoints')}</Text>
                  <VStack align="start" mb={2}>
                    {currentReview.analysis.key_points.map((point, i) => (
                      <Text key={i} color={colorMode === 'dark' ? 'gray.300' : 'gray.600'}>• {point}</Text>
                    ))}
                  </VStack>
                  
                  {currentReview.analysis.pii_detected.length > 0 && (
                    <>
                      <Text fontWeight="bold" color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}>{t('emailReview.drawer.piiDetected')}</Text>
                      <List spacing={1}>
                        {currentReview.analysis.pii_detected.map(pii => (
                          <ListItem key={pii}>
                            <ListIcon as={InfoIcon} color="yellow.500" />
                            {t(`common.piiTypes.${pii.toLowerCase()}`, pii)}
                          </ListItem>
                        ))}
                      </List>
                    </>
                  )}
                  
                  <Text fontWeight="bold" color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}>{t('emailReview.drawer.recommendedAction')}</Text>
                  <Badge colorScheme={currentReview.analysis.recommended_action === 'store' ? 'green' : 'red'}>
                    {t(`common.recommendedActions.${currentReview.analysis.recommended_action.toLowerCase()}`, currentReview.analysis.recommended_action)}
                  </Badge>
                </Box>
                
                <Divider borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'} />
                
                <Accordion allowToggle>
                  <AccordionItem borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}>
                    <h2>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">{t('emailReview.drawer.emailContent')}</Box>
                        <AccordionIcon />
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <Box 
                        p={3} 
                        borderWidth="1px" 
                        borderRadius="md"
                        bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'gray.50'}
                        borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                        color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}
                        whiteSpace="pre-wrap"
                      >
                        {currentReview.content.body}
                      </Box>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {currentReview.content.attachments && currentReview.content.attachments.length > 0 && (
                    <AccordionItem borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}>
                      <h2>
                        <AccordionButton>
                          <Box flex="1" textAlign="left">{t('emailReview.drawer.attachmentsCount', { count: currentReview.content.attachments.length })}</Box>
                          <AccordionIcon />
                        </AccordionButton>
                      </h2>
                      <AccordionPanel pb={4}>
                        <VStack align="stretch">
                          {currentReview.content.attachments.map(attachment => (
                            <Box 
                              key={attachment.id}
                              p={3}
                              borderWidth="1px"
                              borderRadius="md"
                              bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                              borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                            >
                              <Text fontWeight="bold" color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}>{attachment.name}</Text>
                              <Text fontSize="sm" color={colorMode === 'dark' ? 'gray.400' : 'gray.600'}>
                                {t('emailReview.drawer.attachmentType', { type: attachment.content_type })}
                              </Text>
                              <Text fontSize="sm" color={colorMode === 'dark' ? 'gray.400' : 'gray.600'}>
                                {t('emailReview.drawer.attachmentSize', { size: Math.round(attachment.size / 1024) })} KB
                              </Text>
                            </Box>
                          ))}
                        </VStack>
                      </AccordionPanel>
                    </AccordionItem>
                  )}
                </Accordion>
                
                <Divider borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'} />
                
                <Box>
                  <Textarea
                    value={approvalNotes}
                    onChange={(e) => setApprovalNotes(e.target.value)}
                    placeholder={t('emailReview.notes.placeholder')}
                    mb={4}
                    bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                    borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                    color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}
                  />
                  
                  <HStack>
                    <Button
                      colorScheme="green"
                      leftIcon={<CheckIcon />}
                      onClick={() => handleReviewDecision(currentReview.email_id, true)}
                      isLoading={isSubmitting}
                      flex="1"
                    >
                      {t('emailReview.actions.approve')}
                    </Button>
                    
                    <Button
                      colorScheme="red"
                      leftIcon={<CloseIcon />}
                      onClick={() => handleReviewDecision(currentReview.email_id, false)}
                      isLoading={isSubmitting}
                      flex="1"
                    >
                      {t('emailReview.actions.reject')}
                    </Button>
                  </HStack>
                </Box>
              </VStack>
            )}
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Box>
  );
};

export default EmailReview;
