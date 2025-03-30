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
} from '@chakra-ui/react';
import { CheckIcon, CloseIcon, ViewIcon } from '@chakra-ui/icons';

import axios from 'axios';
import { ReviewStatus, SensitivityLevel, Department, EmailReviewItem, EmailApproval } from '../types/email';

// Mock API functions (in a real app, these would be in the API directory)
const getPendingReviews = async (filters: any = {}) => {
  // Mock data for demonstration
  return Array(8).fill(0).map((_, i) => ({
    email_id: `email_${i}`,
    content: {
      id: `email_${i}`,
      internet_message_id: `message_${i}`,
      subject: `Sample Email ${i + 1} for Review`,
      sender: 'John Doe',
      sender_email: 'john.doe@example.com',
      recipients: ['user@example.com'],
      cc_recipients: [],
      received_date: new Date().toISOString(),
      body: `This is the full content of sample email ${i + 1}. It contains information that needs to be reviewed before adding to the knowledge base.`,
      is_html: false,
      folder_id: 'inbox',
      folder_name: 'Inbox',
      attachments: i % 3 === 0 ? [{
        id: `attachment_${i}`,
        name: 'document.pdf',
        content_type: 'application/pdf',
        size: 1024 * 1024,
      }] : [],
      importance: i % 4 === 0 ? 'high' : 'normal'
    },
    analysis: {
      sensitivity: Object.values(SensitivityLevel)[i % 4],
      department: Object.values(Department)[i % 9],
      tags: [`tag${i}`, 'knowledge', i % 2 === 0 ? 'important' : 'routine'],
      is_private: i % 3 === 0,
      pii_detected: i % 3 === 0 ? ['email', 'name'] : [],
      recommended_action: i % 3 === 0 ? 'exclude' : 'store',
      summary: `This is a summary of email ${i + 1} that was analyzed by the AI.`,
      key_points: [
        `Key point 1 from email ${i + 1}`,
        `Key point 2 from email ${i + 1}`,
        `Key point 3 from email ${i + 1}`
      ]
    },
    status: ReviewStatus.PENDING
  }));
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
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  
  // State
  const [reviews, setReviews] = useState<EmailReviewItem[]>([]);
  const [filteredReviews, setFilteredReviews] = useState<EmailReviewItem[]>([]);
  const [selectedReviews, setSelectedReviews] = useState<string[]>([]);
  const [currentReview, setCurrentReview] = useState<EmailReviewItem | null>(null);
  const [approvalNotes, setApprovalNotes] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Filters
  const [filters, setFilters] = useState({
    department: '',
    sensitivity: '',
    isPrivate: '',
  });
  
  // Load reviews on component mount
  useEffect(() => {
    const loadReviews = async () => {
      setIsLoading(true);
      try {
        const reviewData = await getPendingReviews();
        setReviews(reviewData);
        setFilteredReviews(reviewData);
      } catch (error) {
        console.error('Error loading reviews:', error);
        toast({
          title: 'Error loading reviews',
          status: 'error',
          duration: 3000,
        });
      } finally {
        setIsLoading(false);
      }
    };
    
    loadReviews();
  }, [toast]);
  
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
        title: `Email ${approved ? 'approved' : 'rejected'}`,
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
        title: 'Error updating review',
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
        title: 'No emails selected',
        description: 'Please select at least one email',
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
        title: `${selectedReviews.length} emails ${approved ? 'approved' : 'rejected'}`,
        status: approved ? 'success' : 'info',
        duration: 3000,
      });
      
      // Clear selection and notes
      setSelectedReviews([]);
      setApprovalNotes('');
    } catch (error) {
      console.error('Error updating reviews:', error);
      toast({
        title: 'Error updating reviews',
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
  
  return (
    <Container maxW="container.xl" py={6}>
      <VStack spacing={8} align="stretch">
        <Heading size="lg">Review Analyzed Emails</Heading>
        
        {/* Filters */}
        <Card>
          <CardHeader>
            <Heading size="md">Filters</Heading>
          </CardHeader>
          <CardBody>
            <Flex gap={4} wrap="wrap">
              <Box minW="200px">
                <Select
                  name="department"
                  value={filters.department}
                  onChange={handleFilterChange}
                  placeholder="All Departments"
                >
                  {Object.values(Department).map(dept => (
                    <option key={dept} value={dept}>
                      {dept.charAt(0).toUpperCase() + dept.slice(1)}
                    </option>
                  ))}
                </Select>
              </Box>
              
              <Box minW="200px">
                <Select
                  name="sensitivity"
                  value={filters.sensitivity}
                  onChange={handleFilterChange}
                  placeholder="All Sensitivity Levels"
                >
                  {Object.values(SensitivityLevel).map(level => (
                    <option key={level} value={level}>
                      {level.charAt(0).toUpperCase() + level.slice(1)}
                    </option>
                  ))}
                </Select>
              </Box>
              
              <Box minW="200px">
                <Select
                  name="isPrivate"
                  value={filters.isPrivate}
                  onChange={handleFilterChange}
                  placeholder="All Privacy Levels"
                >
                  <option value="true">Private</option>
                  <option value="false">Not Private</option>
                </Select>
              </Box>
            </Flex>
          </CardBody>
        </Card>
        
        {/* Review Table */}
        <Card>
          <CardHeader>
            <Flex justify="space-between" align="center">
              <Heading size="md">Pending Reviews ({filteredReviews.length})</Heading>
              
              <HStack>
                <Button 
                  size="sm" 
                  onClick={selectAllReviews}
                  variant="outline"
                >
                  {selectedReviews.length === filteredReviews.length ? 'Deselect All' : 'Select All'}
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
                      Approve Selected
                    </Button>
                    
                    <Button 
                      size="sm"
                      colorScheme="red"
                      leftIcon={<CloseIcon />}
                      onClick={() => handleBulkDecision(false)}
                      isLoading={isSubmitting}
                    >
                      Reject Selected
                    </Button>
                  </>
                )}
              </HStack>
            </Flex>
          </CardHeader>
          <CardBody>
            {isLoading ? (
              <Flex justify="center" py={8}>
                <Spinner size="xl" />
              </Flex>
            ) : filteredReviews.length === 0 ? (
              <Text textAlign="center" py={8}>No pending reviews match your filters</Text>
            ) : (
              <>
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th width="50px"></Th>
                      <Th>Subject</Th>
                      <Th>Department</Th>
                      <Th>Sensitivity</Th>
                      <Th>Tags</Th>
                      <Th>Private</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {filteredReviews.map(review => (
                      <Tr key={review.email_id}>
                        <Td>
                          <Checkbox 
                            isChecked={selectedReviews.includes(review.email_id)}
                            onChange={() => toggleReviewSelection(review.email_id)}
                          />
                        </Td>
                        <Td fontWeight="medium">{review.content.subject}</Td>
                        <Td>
                          <Badge>
                            {review.analysis.department}
                          </Badge>
                        </Td>
                        <Td>
                          <Badge colorScheme={getSensitivityColor(review.analysis.sensitivity)}>
                            {review.analysis.sensitivity}
                          </Badge>
                        </Td>
                        <Td>
                          <HStack>
                            {review.analysis.tags.slice(0, 2).map(tag => (
                              <Badge key={tag} colorScheme="blue" variant="outline">
                                {tag}
                              </Badge>
                            ))}
                            {review.analysis.tags.length > 2 && (
                              <Badge colorScheme="blue" variant="outline">
                                +{review.analysis.tags.length - 2}
                              </Badge>
                            )}
                          </HStack>
                        </Td>
                        <Td>
                          <Badge colorScheme={review.analysis.is_private ? 'red' : 'green'}>
                            {review.analysis.is_private ? 'Yes' : 'No'}
                          </Badge>
                        </Td>
                        <Td>
                          <HStack>
                            <IconButton
                              aria-label="View details"
                              icon={<ViewIcon />}
                              size="sm"
                              onClick={() => openReviewDetails(review)}
                            />
                            <IconButton
                              aria-label="Approve"
                              icon={<CheckIcon />}
                              colorScheme="green"
                              size="sm"
                              onClick={() => handleReviewDecision(review.email_id, true)}
                              isLoading={isSubmitting}
                            />
                            <IconButton
                              aria-label="Reject"
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
                
                <Box mt={4}>
                  <FormLabel htmlFor="approval-notes">Notes for selected emails:</FormLabel>
                  <Textarea
                    id="approval-notes"
                    value={approvalNotes}
                    onChange={(e) => setApprovalNotes(e.target.value)}
                    placeholder="Add optional notes about your decision..."
                    size="sm"
                  />
                </Box>
              </>
            )}
          </CardBody>
        </Card>
      </VStack>
      
      {/* Review Details Drawer */}
      <Drawer isOpen={isOpen} placement="right" onClose={onClose} size="lg">
        <DrawerOverlay />
        <DrawerContent>
          <DrawerCloseButton />
          <DrawerHeader borderBottomWidth="1px">
            Email Details
          </DrawerHeader>
          
          <DrawerBody>
            {currentReview && (
              <VStack spacing={6} align="stretch">
                <Box>
                  <Heading size="md">{currentReview.content.subject}</Heading>
                  <Text color="gray.600">
                    From: {currentReview.content.sender} ({currentReview.content.sender_email})
                  </Text>
                  <Text color="gray.600">
                    Date: {new Date(currentReview.content.received_date).toLocaleString()}
                  </Text>
                </Box>
                
                <Divider />
                
                <Box>
                  <Heading size="sm" mb={2}>AI Analysis</Heading>
                  
                  <HStack wrap="wrap" mb={2}>
                    <Badge colorScheme={getSensitivityColor(currentReview.analysis.sensitivity)}>
                      {currentReview.analysis.sensitivity}
                    </Badge>
                    <Badge>{currentReview.analysis.department}</Badge>
                    {currentReview.analysis.is_private && (
                      <Badge colorScheme="red">Private</Badge>
                    )}
                    {currentReview.analysis.pii_detected.length > 0 && (
                      <Badge colorScheme="orange">Contains PII</Badge>
                    )}
                  </HStack>
                  
                  <HStack wrap="wrap" mb={4}>
                    {currentReview.analysis.tags.map(tag => (
                      <Badge key={tag} colorScheme="blue" variant="outline">
                        {tag}
                      </Badge>
                    ))}
                  </HStack>
                  
                  <Text fontWeight="bold">Summary:</Text>
                  <Text mb={2}>{currentReview.analysis.summary}</Text>
                  
                  <Text fontWeight="bold">Key Points:</Text>
                  <VStack align="start" mb={2}>
                    {currentReview.analysis.key_points.map((point, i) => (
                      <Text key={i}>• {point}</Text>
                    ))}
                  </VStack>
                  
                  {currentReview.analysis.pii_detected.length > 0 && (
                    <>
                      <Text fontWeight="bold">PII Detected:</Text>
                      <HStack mb={2}>
                        {currentReview.analysis.pii_detected.map(pii => (
                          <Badge key={pii} colorScheme="orange">
                            {pii}
                          </Badge>
                        ))}
                      </HStack>
                    </>
                  )}
                  
                  <Text fontWeight="bold">Recommended Action:</Text>
                  <Badge colorScheme={currentReview.analysis.recommended_action === 'store' ? 'green' : 'red'}>
                    {currentReview.analysis.recommended_action}
                  </Badge>
                </Box>
                
                <Divider />
                
                <Accordion allowToggle>
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                          Email Content
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
                        {currentReview.content.body}
                      </Box>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {currentReview.content.attachments && currentReview.content.attachments.length > 0 && (
                    <AccordionItem>
                      <h2>
                        <AccordionButton>
                          <Box flex="1" textAlign="left">
                            Attachments ({currentReview.content.attachments.length})
                          </Box>
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
                            >
                              <Text fontWeight="bold">{attachment.name}</Text>
                              <Text fontSize="sm">
                                Type: {attachment.content_type}
                              </Text>
                              <Text fontSize="sm">
                                Size: {Math.round(attachment.size / 1024)} KB
                              </Text>
                            </Box>
                          ))}
                        </VStack>
                      </AccordionPanel>
                    </AccordionItem>
                  )}
                </Accordion>
                
                <Divider />
                
                <Box>
                  <Textarea
                    value={approvalNotes}
                    onChange={(e) => setApprovalNotes(e.target.value)}
                    placeholder="Add notes about your decision..."
                    mb={4}
                  />
                  
                  <HStack>
                    <Button
                      colorScheme="green"
                      leftIcon={<CheckIcon />}
                      onClick={() => handleReviewDecision(currentReview.email_id, true)}
                      isLoading={isSubmitting}
                      flex="1"
                    >
                      Approve
                    </Button>
                    
                    <Button
                      colorScheme="red"
                      leftIcon={<CloseIcon />}
                      onClick={() => handleReviewDecision(currentReview.email_id, false)}
                      isLoading={isSubmitting}
                      flex="1"
                    >
                      Reject
                    </Button>
                  </HStack>
                </Box>
              </VStack>
            )}
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Container>
  );
};

export default EmailReview;
