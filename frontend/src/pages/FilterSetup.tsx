import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  FaChartPie,
} from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { v4 as uuidv4 } from 'uuid';
import LanguageSwitcher from '../components/LanguageSwitcher';
import SubjectSunburstChart from '../components/SubjectSunburstChart';
import { saveFilteredEmailsToKnowledgeBase } from '../api/vector';

import { getEmailFolders, getEmailPreviews, submitFilterForAnalysis } from '../api/email';
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

// Type for cache entries
interface PageCacheEntry {
  previews: EmailPreview[];
  nextLink?: string;
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

// Get backend URL from environment variables (using Vite's convention)
// Ensure VITE_BACKEND_URL is defined in your .env file
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'; 

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
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [nextLink, setNextLink] = useState<string | undefined>(undefined);
  const [pageCache, setPageCache] = useState<Map<number, PageCacheEntry>>(new Map());
  const pageSizeOptions = [10, 25, 50, 100];
  const [isEndDateDisabled, setIsEndDateDisabled] = useState(true);
  const [dateError, setDateError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisData, setAnalysisData] = useState<any | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisJobId, setAnalysisJobId] = useState<string | null>(null);
  const [isSavingToKB, setIsSavingToKB] = useState(false);
  const [searchPerformedSuccessfully, setSearchPerformedSuccessfully] = useState(false);
  
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
  
  // Load previews
  const loadPreviews = useCallback(async (options?: { size?: number }) => {
    // Use the explicitly passed size, otherwise default to the current state
    const currentSize = options?.size ?? itemsPerPage;
    console.log(`loadPreviews called. Effective size: ${currentSize}`);

    if (isInitialLoad) {
      setIsInitialLoad(false);
    }

    setIsLoadingPreviews(true);
    setSearchPerformedSuccessfully(false);
    try {
      // If using next_link, use it directly (size doesn't apply to next_link requests)
      if (nextLink) {
        // This block is typically hit during forward pagination handled by handlePageChange,
        // but keeping it here for potential direct calls to loadPreviews with nextLink.
        console.log('Using next_link for pagination:', nextLink);
        // Pass only the next_link, backend handles the rest
        const previewData = await getEmailPreviews({ next_link: nextLink }); 
        console.log('Next link response:', previewData);
        
        const currentPreviews = previewData.items || [];
        const currentNextLink = previewData.next_link ?? undefined;

        // Update Cache for the *next* page (currentPage + 1 because nextLink loads the next page)
        const cacheData: PageCacheEntry = { previews: currentPreviews, nextLink: currentNextLink };
        setPageCache(prevCache => new Map(prevCache).set(currentPage + 1, cacheData));

        // Update state
        setPreviews(currentPreviews);
        setTotalEmails(previewData.total);
        const totalPagesFromNextLink = previewData.total > 0 ? Math.ceil(previewData.total / currentSize) : 1;
        setTotalPages(totalPagesFromNextLink); 
        setNextLink(currentNextLink);
        // setCurrentPage(currentPage + 1); // This should be handled by the caller (e.g., handlePageChange)

      } else {
        // Initial Load / Non-pagination request (Search or first load)
        // Resetting page to 1 and clearing cache should be done *before* calling loadPreviews
        // setCurrentPage(1); // Reset to page 1 on new filter/search - MOVED TO CALLERS

        // Prepare base parameters for the API call
        const apiParams: any = {
          folder_id: filter.folder_id || undefined, 
          per_page: currentSize, // Use currentSize determined above
          start_date: filter.start_date || undefined,
          end_date: filter.end_date || undefined,
          keywords: filter.keywords && filter.keywords.length > 0 ? filter.keywords : undefined,
        };

        // Clean parameters: remove undefined/null keys and empty arrays
        const cleanParams = Object.entries(apiParams)
          .filter(([_, v]) => v !== undefined && v !== null && (!Array.isArray(v) || v.length > 0))
          .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {});
          
        console.log('Sending request with filter (non-pagination):', cleanParams);
        const previewData = await getEmailPreviews(cleanParams as EmailFilter & { per_page?: number });
        console.log('Received preview data (non-pagination):', previewData);
        console.log(`[FilterSetup] Received ${previewData?.items?.length ?? 0} items from API (non-pagination).`);

        const currentPreviews = previewData.items || [];
        const currentNextLink = previewData.next_link ?? undefined;
        
        // Update Cache for page 1
        const cacheData: PageCacheEntry = { previews: currentPreviews, nextLink: currentNextLink };
        setPageCache(new Map().set(1, cacheData)); // Reset cache and set page 1

        // Update state with data from API
        setPreviews(currentPreviews);
        setTotalEmails(previewData.total);
        const totalPagesFromInitial = previewData.total > 0 ? Math.ceil(previewData.total / currentSize) : 1;
        setTotalPages(totalPagesFromInitial);
        setNextLink(currentNextLink);
        setSearchPerformedSuccessfully(true);

        console.log('Updated state (non-pagination):', {
          items: currentPreviews.length,
          total: previewData.total,
          pages: totalPagesFromInitial,
          nextLink: currentNextLink,
        } as any);
      }
    } catch (error: any) {
      console.error("Error loading email previews:", error);
      toast({
        title: t('errors.errorLoadingPreviews'),
        description: error.message || t('errors.unknownError'),
        status: "error",
        duration: 5000,
        isClosable: true,
      });
      // Reset state on error
      setPreviews([]);
      setTotalEmails(0);
      setTotalPages(1);
      setNextLink(undefined);
      setPageCache(new Map()); // Clear cache on error
    } finally {
      setIsLoadingPreviews(false);
    }
  }, [filter, itemsPerPage, isInitialLoad, toast, t, nextLink, currentPage]);

  // Log previews state changes
  useEffect(() => {
    console.log('[PREVIEWS_EFFECT] Previews state updated. Length:', previews.length);
  }, [previews]);

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

  // Handler for general filter changes (e.g., folder select)
  const handleFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFilter(prev => ({ ...prev, [name]: value }));
    // Reset pagination and cache on filter change
    setNextLink(undefined);
    setCurrentPage(1);
    setPageCache(new Map());
  };

  // Function to handle page changes (Previous/Next buttons)
  const handlePageChange = async (newPage: number) => {
    // Basic validation
    if (newPage < 1 || newPage > totalPages || newPage === currentPage) {
      console.log(`handlePageChange: Invalid page requested (${newPage}). Current: ${currentPage}, Total: ${totalPages}`);
      return;
    }

    // --- Handle Forward Pagination (using nextLink) ---
    if (newPage > currentPage) {
      if (!nextLink) {
        console.error(`handlePageChange: Trying to go to next page (${newPage}), but nextLink is missing.`);
        toast({ title: "Pagination Error", description: "Cannot load next page: link is missing.", status: "error", duration: 3000 });
        return;
      }

      console.log(`handlePageChange: Moving forward. CurrentPage: ${currentPage}, TargetPage: ${newPage}, NextLink available: ${!!nextLink}`);
      setIsLoadingPreviews(true);
      try {
        console.log(`handlePageChange: Calling getEmailPreviews with next_link: ${nextLink} and current filters`);
        // Pass arguments according to the function signature
        const previewData = await getEmailPreviews(filter, newPage, itemsPerPage, nextLink);

        console.log('handlePageChange: Received previewData:', previewData);
        
        if (previewData && previewData.items) {
            const newPreviews = previewData.items;
            const newNextLink = previewData.next_link ?? undefined;
            const newTotal = previewData.total;

            // --- Cache the new page data BEFORE setting state ---
            const cacheData: PageCacheEntry = { previews: newPreviews, nextLink: newNextLink };
            setPageCache(prevCache => new Map(prevCache).set(newPage, cacheData));
            console.log(`handlePageChange: Cached data for page ${newPage}.`);
            // --- End Cache Update ---

            console.log(`handlePageChange: Calling setPreviews with ${newPreviews.length} items.`);
            setPreviews(newPreviews);
            console.log('handlePageChange: Calling setTotalEmails:', newTotal);
            setTotalEmails(newTotal);

            // Correct totalPages calculation
            const newTotalPages = newTotal === -1
                                    ? (newNextLink ? newPage + 1 : newPage) // If unknown total, assume at least one more page if nextLink exists
                                    : (newTotal > 0 ? Math.ceil(newTotal / itemsPerPage) : 1);
            console.log('handlePageChange: Calling setTotalPages:', newTotalPages);
            setTotalPages(newTotalPages);
            console.log('handlePageChange: Calling setNextLink:', newNextLink);
            setNextLink(newNextLink);
            console.log('handlePageChange: Calling setCurrentPage:', newPage);
            setCurrentPage(newPage);
        } else {
            console.error('handlePageChange: Received invalid previewData:', previewData);
            toast({ title: "API Error", description: "Received invalid data for next page.", status: "error", duration: 3000 });
        }

      } catch (error: any) {
        console.error("handlePageChange: Error loading next page:", error);
        toast({
          title: t('errors.errorLoadingPreviews'),
          description: error.message || t('errors.unknownError'),
          status: "error",
          duration: 5000,
          isClosable: true,
        });
        // Do not change page number on error
      } finally {
        setIsLoadingPreviews(false);
      }
    } else {
      // --- Handle Backward Pagination (Using Cache) ---
      if (pageCache.has(newPage)) {
        const cachedPage = pageCache.get(newPage)!;
        console.log(`handlePageChange: Loading page ${newPage} from cache.`, cachedPage);
        // No need to set loading state when loading from cache
        setPreviews(cachedPage.previews);
        setNextLink(cachedPage.nextLink); // Restore nextLink for the *target* page
        setCurrentPage(newPage);
        console.log(`handlePageChange: State updated for cached page ${newPage}.`);
      } else {
        // This case should ideally not happen with sequential back clicks,
        // but handle it defensively.
        console.warn(`handlePageChange: Page ${newPage} not found in cache. Cannot go back.`);
        toast({ 
            title: "Cache Miss", 
            description: `Page ${newPage} is not cached. Cannot go back further. Please perform a new search if needed.`, 
            status: "warning", 
            duration: 4000 
        });
      }
    }
  };

  // Handle search
  const handleSearchClick = useCallback(async () => {
    // Reset pagination state AND cache
    setCurrentPage(1);
    setNextLink(undefined);
    setPageCache(new Map());
    setIsInitialLoad(false);
    setPreviews([]); // Clear existing previews before new search
    setTotalEmails(0); // Reset total count before new search
    loadPreviews();
  }, [loadPreviews]);
  
  // Handler for adding a keyword
  const handleAddKeyword = () => {
    if (keywordInput.trim()) {
      // Handle potentially undefined keywords array
      setFilter(prev => ({ ...prev, keywords: [...(prev.keywords ?? []), keywordInput.trim()] }));
      setKeywordInput('');
      // Reset pagination and cache
      setNextLink(undefined);
      setCurrentPage(1);
      setPageCache(new Map());
    }
  };
  
  // Handler for removing a keyword
  const handleRemoveKeyword = (keywordToRemove: string) => {
    // Handle potentially undefined keywords array
    setFilter(prev => ({ ...prev, keywords: (prev.keywords ?? []).filter(kw => kw !== keywordToRemove) }));
    // Reset pagination and cache
    setNextLink(undefined);
    setCurrentPage(1);
    setPageCache(new Map());
  };
  
  // Handler for folder select change
  const handleFolderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilter(prev => ({ ...prev, folder_id: e.target.value }));
    // Reset pagination and cache
    setNextLink(undefined);
    setCurrentPage(1);
    setPageCache(new Map());
  };

  // Handler for basic input/textarea changes that update the filter state
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFilter(prev => ({ ...prev, [name]: value }));
    // Reset pagination and cache if these inputs should trigger a re-filter
    setNextLink(undefined); 
    setCurrentPage(1);
    setPageCache(new Map());
  };

  // Handler for date input changes (Specific because it handles isEndDateDisabled)
  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFilter(prev => ({ ...prev, [name]: value }));
    // Reset pagination and cache
    setNextLink(undefined); 
    setCurrentPage(1);
    setPageCache(new Map());
    
    if (name === 'start_date') {
      setIsEndDateDisabled(!value);
    } 
    // validateDates still commented out
  };
  
  // Handler for changing items per page
  const handleItemsPerPageChange = (value: string) => {
    const newSize = parseInt(value, 10);
    if (isNaN(newSize) || newSize <= 0) return; 
    setItemsPerPage(newSize);
    // Reset pagination and cache
    setNextLink(undefined);
    setCurrentPage(1);
    setPageCache(new Map());
    // Trigger reload with new size, passing it explicitly
    loadPreviews({ size: newSize }); // <-- Pass newSize here
  };

  // Calculation for displaying email range
  const firstEmailIndex = totalEmails > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0;
  const lastEmailIndex = Math.min(currentPage * itemsPerPage, totalEmails);

  // Placeholder for missing function to resolve linter error
  const handleSaveTemplate = () => {
    // Basic implementation: Just close the modal
    // Actual save logic would go here
    setShowSaveTemplateModal(false); 
    toast({ title: "Save Template (Not Implemented)", status: "info", duration: 2000 });
  };

  // Handler for Analyze Data button (Reverted)
  const handleAnalyzeClick = async () => {
    setIsAnalyzing(true); 
    setAnalysisJobId(null); 
    setAnalysisData(null); // Clear previous results
    setAnalysisError(null); // Clear previous error
    try {
      const response = await submitFilterForAnalysis(filter);
      setAnalysisJobId(response.job_id);
      toast({ title: t('emailProcessing.notifications.analysisSubmitted.title'), description: `${t('emailProcessing.notifications.analysisSubmitted.description')} Job ID: ${response.job_id}`, status: 'success', duration: 5000, });
      console.log('Analysis submitted successfully, Job ID:', response.job_id);
    } catch (error: any) { 
      console.error('Error submitting analysis:', error);
      const errorMessage = error.response?.data?.detail || error.message || t('errors.unknownError');
      setAnalysisError(errorMessage); 
      setIsAnalyzing(false); // Stop loading on submit error
      toast({ title: t('errors.errorSubmittingAnalysis'), description: errorMessage, status: 'error', duration: 7000, });
    }
  };

  // Handler for the "Save to Knowledge Base" button (Now uses new endpoint)
  const handleSaveToKnowledgeBase = async () => {
    if (!searchPerformedSuccessfully || previews.length === 0) {
      toast({ title: "No email previews to process.", status: "warning", duration: 3000 });
      return;
    }

    // No need to check for analysisJobId anymore
    setIsSavingToKB(true); // Indicate the saving process
    
    try {
      console.log(`Attempting to save emails using current filter...`, filter);
      // Call the new API function with the current filter state
      const result = await saveFilteredEmailsToKnowledgeBase(filter); 

      toast({
        title: t('emailProcessing.notifications.knowledgeBaseSaveSubmitted.title'), // Use appropriate translation key
        description: result.message || t('emailProcessing.notifications.knowledgeBaseSaveSubmitted.description'),
        status: result.status === 'success' || result.status === 'partial_success' ? 'success' : 'warning', // Adjust status based on response
        duration: 5000,
      });
      console.log('Save filtered emails to knowledge base result:', result);

    } catch (error: any) {
      console.error(`Error saving filtered emails to knowledge base:`, error);
      const errorMessage = error.message || t('errors.unknownError'); // Error now comes from the API function
      toast({
        title: t('errors.errorSavingToKB'), // Use appropriate translation key
        description: errorMessage,
        status: 'error',
        duration: 7000,
      });
    } finally {
      setIsSavingToKB(false); // Saving finished (success or fail)
      // Reset isAnalyzing state as well if it was potentially set by previous logic (cleanup)
      setIsAnalyzing(false); 
    }
  };
  
  // --- Derived State and Tooltips (Reverted) --- 
  const isProcessing = isAnalyzing || isSavingToKB; 
  const canClickButtons = searchPerformedSuccessfully && previews.length > 0 && !isProcessing;
  const analyzeButtonTooltip = t('emailProcessing.tooltips.analyze'); 
  const proceedButtonTooltip = t('emailProcessing.tooltips.proceedDirectSave'); 

  // WebSocket connection effect (Reverted to use analysisData/Error)
  useEffect(() => {
    const wsUrlFromEnv = import.meta.env.VITE_WEBSOCKET_URL;
    if (!wsUrlFromEnv) { 
      console.error("[WebSocket] VITE_WEBSOCKET_URL is not defined.");
      setAnalysisError("WebSocket URL not configured.");
      return; 
    }
    const wsUrl = wsUrlFromEnv;
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => console.log('[WebSocket] Connection opened.');
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('[WebSocket] Message received:', message);
        if (message?.job_id && message.job_id === analysisJobId) {
          if (message.payload?.results) { 
            setAnalysisData(message.payload.results);
            setAnalysisError(null);
            setIsAnalyzing(false); // Analysis complete
            toast({ title: t('emailProcessing.analysis.completeTitle'), status: "success", duration: 3000 });
          } else if (message.payload?.error || message.error) {
            setAnalysisData(null);
            const errorMsg = message.payload?.error || message.error || "Analysis failed.";
            setAnalysisError(errorMsg);
            setIsAnalyzing(false); // Analysis complete (with error)
            toast({ title: t('emailProcessing.analysis.failedTitle'), description: errorMsg, status: "error" });
          } else {
             console.log('[WebSocket] Received unhandled message for job:', message);
          }
        }
      } catch (error) {
        console.error('[WebSocket] Error parsing message:', error);
        setAnalysisError("Error processing WebSocket message.");
        setIsAnalyzing(false); 
      }
    };
    ws.onerror = (event) => { 
      console.error('[WebSocket] Error:', event);
      setAnalysisError("WebSocket connection error.");
      setIsAnalyzing(false); 
    };
    ws.onclose = (event) => console.log('[WebSocket] Closed:', event.code, event.reason);
    return () => { 
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [analysisJobId, toast, t]); // Reverted dependencies

  // Restore transformedChartData useMemo hook
  const transformedChartData = useMemo(() => {
    if (!analysisData || !Array.isArray(analysisData)) return null;
    const root: { name: string, children: any[] } = { name: "Subjects", children: [] };
    const tagMap = new Map<string, { name: string, children: any[] }>();
    analysisData.forEach((item: any) => {
      if (!item.tag || !item.cluster) return;
      let tagNode = tagMap.get(item.tag);
      if (!tagNode) {
        tagNode = { name: item.tag, children: [] };
        tagMap.set(item.tag, tagNode);
        root.children.push(tagNode);
      }
      let clusterNode = tagNode.children.find(c => c.name === item.cluster);
      if (!clusterNode) {
        clusterNode = { name: item.cluster, value: 0 };
        tagNode.children.push(clusterNode);
      }
      clusterNode.value += 1; 
    });
    root.children = root.children.filter(tag => tag.children.length > 0);
    return root.children.length > 0 ? root : null;
  }, [analysisData]);

  // Component Render
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
                        id="folder_id"
                        name="folder_id"
                        value={filter.folder_id || ''} 
                        onChange={handleFolderChange}
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
                      <Tooltip label={t('emailProcessing.tooltips.dateHelp')} placement="top">
                        <QuestionIcon ml={1} boxSize={3} color="gray.500" />
                      </Tooltip>
                    </FormLabel>
                    <VStack spacing={2} align="stretch">
                      <ButtonGroup size="sm" isAttached variant="outline">
                        <Button
                          onClick={() => {
                            const endDate = new Date();
                            const startDate = new Date();
                            startDate.setMonth(endDate.getMonth() - 1);
                            const startDateStr = startDate.toISOString().split('T')[0];
                            const endDateStr = endDate.toISOString().split('T')[0];
                            setFilter(prev => ({
                              ...prev,
                              start_date: startDateStr,
                              end_date: endDateStr
                            }));
                            setNextLink(undefined); // Reset pagination
                            setCurrentPage(1);      // Go back to page 1
                          }}
                        >
                          1 {t('emailProcessing.filters.month')}
                        </Button>
                        <Button
                          onClick={() => {
                            const endDate = new Date();
                            const startDate = new Date();
                            startDate.setMonth(endDate.getMonth() - 3);
                            const startDateStr = startDate.toISOString().split('T')[0];
                            const endDateStr = endDate.toISOString().split('T')[0];
                            setFilter(prev => ({
                              ...prev,
                              start_date: startDateStr,
                              end_date: endDateStr
                            }));
                            setNextLink(undefined); // Reset pagination
                            setCurrentPage(1);      // Go back to page 1
                          }}
                        >
                          3 {t('emailProcessing.filters.months')}
                        </Button>
                        <Button
                          onClick={() => {
                            const endDate = new Date();
                            const startDate = new Date();
                            startDate.setMonth(endDate.getMonth() - 6);
                            const startDateStr = startDate.toISOString().split('T')[0];
                            const endDateStr = endDate.toISOString().split('T')[0];
                            setFilter(prev => ({
                              ...prev,
                              start_date: startDateStr,
                              end_date: endDateStr
                            }));
                            setNextLink(undefined); // Reset pagination
                            setCurrentPage(1);      // Go back to page 1
                          }}
                        >
                          6 {t('emailProcessing.filters.months')}
                        </Button>
                      </ButtonGroup>
                      <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                        <Input
                          type="date"
                          name="start_date"
                          value={filter.start_date || ''}
                          onChange={handleDateChange}
                          placeholder={t('emailProcessing.filters.startDate')}
                          focusBorderColor="primary.400"
                          bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                          borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                        />
                        <Input
                          type="date"
                          name="end_date"
                          value={filter.end_date || ''}
                          onChange={handleDateChange}
                          placeholder={t('emailProcessing.filters.endDate')}
                          min={filter.start_date || undefined}
                          focusBorderColor="primary.400"
                          bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                          borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                          isDisabled={isEndDateDisabled}
                        />
                      </Grid>
                      {dateError && (
                        <Text color="red.500" fontSize="sm" mt={1}>
                          {dateError}
                        </Text>
                      )}
                    </VStack>
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
                        id="keywords"
                        value={keywordInput} 
                        onChange={(e) => setKeywordInput(e.target.value)}
                        onKeyPress={(e) => { if (e.key === 'Enter') handleAddKeyword(); }}
                        placeholder={t('emailProcessing.filters.addKeywords')}
                        focusBorderColor="primary.400"
                        bg={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'white'}
                        borderColor={colorMode === 'dark' ? 'rgba(255, 255, 255, 0.16)' : 'gray.200'}
                      />
                      <InputRightElement>
                        <IconButton
                          aria-label={t('common.add')}
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
                  {/* Hide show advanced filters button */}
                  {/* <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                    leftIcon={showAdvancedFilters ? <ChevronUpIcon /> : <ChevronDownIcon />}
                  >
                    {showAdvancedFilters
                      ? t('emailProcessing.filters.hideAdvanced')
                      : t('emailProcessing.filters.showAdvanced')
                    }
                  </Button> */}
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
                          onChange={handleInputChange}
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
                  onClick={handleSearchClick}
                  isLoading={isLoadingPreviews}
                  loadingText={t('emailProcessing.actions.searching')}
                  size="md"
                  w="full"
                >
                  {/* Restore original key */}
                  {t('emailProcessing.actions.search')}
                </Button>
              </Flex>
            </CardBody>
          </Card>
          
          {/* Results Card */}
          {(searchPerformedSuccessfully || isLoadingPreviews) && (
             <Card variant="outline" mb={6}>
               <CardHeader>
                 <Flex justify="space-between" align="center">
                   <Heading size="md" display="flex" alignItems="center">
                     <Icon as={FaEnvelope} mr={2} />
                     {t('emailProcessing.results.title')} 
                     {totalEmails > 0 && (
                       <Tag ml={2} colorScheme="primary" size="sm">
                         {totalEmails === -1 ? `${(currentPage - 1) * itemsPerPage + previews.length}+` : totalEmails} {t('emailProcessing.results.found')}
                       </Tag>
                     )}
                   </Heading>
                   {/* Action Buttons & Pagination */}
                   <Flex gap={2} align="center">
                       {/* Analyze Button (Reverted) */} 
                       {canClickButtons && (
                          <Tooltip label={analyzeButtonTooltip} placement="top">
                             <Button
                                leftIcon={<FaChartPie />} // Icon restored
                                size="sm" 
                                variant="outline"
                                onClick={handleAnalyzeClick} 
                                isLoading={isAnalyzing} // Use isAnalyzing state
                                loadingText={t('emailProcessing.actions.analyzing')}
                                isDisabled={isProcessing} // Use isProcessing derived state
                              >
                                {t('emailProcessing.actions.analyze')} {/* Reverted text */}
                           </Button>
                          </Tooltip>
                       )}
                       
                       {/* Proceed Button */} 
                       {canClickButtons && (
                          <Tooltip label={proceedButtonTooltip} placement="top">
                             <Box as="span" display="inline-block"> 
                              <Button
                                  leftIcon={<FaSave />} size="sm" colorScheme="teal"
                                  onClick={handleSaveToKnowledgeBase}
                                  isLoading={isSavingToKB}
                                  loadingText={t('emailProcessing.actions.saving')}
                                  isDisabled={isProcessing} 
                              >
                                  {t('emailProcessing.actions.proceedGenerateKB')}
                              </Button>
                             </Box>
                          </Tooltip>
                       )}
                       {/* Pagination (Update isDisabled for Previous button) */}
                       {previews.length > 0 && !isLoadingPreviews && totalPages > 1 && (
                           <ButtonGroup size="sm" isAttached variant="outline">
                              <IconButton
                                aria-label={t('common.previousPage')}
                                icon={<ChevronLeftIcon />}
                                onClick={() => handlePageChange(currentPage - 1)}
                                // Disable Previous if on page 1 OR if the previous page isn't in cache (belt-and-suspenders)
                                isDisabled={currentPage === 1 || isProcessing || !pageCache.has(currentPage - 1)} 
                              />
                              <IconButton
                                aria-label={t('common.nextPage')}
                                icon={<ChevronRightIconSolid />}
                                onClick={() => handlePageChange(currentPage + 1)}
                                // Disable Next if nextLink is missing OR if on last page (when total is known) OR if processing
                                isDisabled={currentPage >= totalPages || !nextLink || isProcessing} 
                              />
                            </ButtonGroup>
                       )}
                   </Flex>
                 </Flex>
               </CardHeader>
               <CardBody>
                 <Box overflowX="auto">
                   {isLoadingPreviews ? (
                     <EmailTableSkeleton />
                   ) : previews.length > 0 ? (
                     <>
                       <Table variant="simple">
                         <Thead>
                           <Tr>
                             {/* Hide checkbox column */}
                             {/* <Th width="40px" px={2}>
                               <Checkbox
                                 isChecked={selectedEmails.length === previews.length && previews.length > 0}
                                 onChange={selectAllEmails}
                                 colorScheme="primary"
                               />
                             </Th> */}
                             <Th>{t('emailProcessing.results.sender')}</Th>
                             <Th>{t('emailProcessing.results.subject')}</Th>
                             <Th width="120px">{t('emailProcessing.results.date')}</Th>
                             <Th width="100px" textAlign="center">{t('emailProcessing.results.hasAttachments')}</Th>
                             <Th width="100px">{t('emailProcessing.results.importance')}</Th>
                           </Tr>
                         </Thead>
                         <Tbody>
                           {previews.map(email => (
                             <Tr key={email.id} height="48px">
                               {/* Hide checkbox column */}
                               {/* <Td>
                                 <Checkbox 
                                   isChecked={selectedEmails.includes(email.id)}
                                   onChange={() => toggleEmailSelection(email.id)}
                                   colorScheme="primary"
                                 />
                               </Td> */}
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
                       <Flex justify="center" mt={4}>
                         <Text color="gray.500" fontSize="sm">
                           {totalEmails === -1 
                             ? t('emailProcessing.results.showingSome', {
                                 start: (currentPage - 1) * itemsPerPage + 1,
                                 end: currentPage * itemsPerPage, // Show the end of the current page
                               }) + (nextLink ? ` (${t('emailProcessing.results.moreAvailable')})` : '')
                             : t('emailProcessing.results.showing', {
                                 start: firstEmailIndex, // Use calculated firstEmailIndex
                                 end: lastEmailIndex, // Use calculated lastEmailIndex
                                 total: totalEmails
                               })
                           }
                         </Text>
                       </Flex>
                     </>
                   ) : (
                     <Flex 
                       direction="column" 
                       align="center" 
                       justify="center" 
                       py={8}
                       color="gray.500"
                     >
                       <Icon as={FaSearch} boxSize={8} mb={4} />
                       <Text fontSize="lg" mb={2}>
                         {t('emailProcessing.results.noResults')}
                       </Text>
                       <Text fontSize="sm">
                         {t('emailProcessing.results.tryDifferentFilters')}
                       </Text>
                     </Flex>
                   )}
                 </Box>
                 
                 {/* Add pagination controls (Update isDisabled for Previous button) */}
                 {previews.length > 0 && (
                   <Flex justify="space-between" align="center" mt={4}>
                     {/* <Select 
                       width="120px" 
                       size="sm" 
                       value={itemsPerPage}
                       onChange={(e) => handleItemsPerPageChange(e.target.value)}
                     >
                       {pageSizeOptions.map(size => (
                         <option key={size} value={size}>
                           {t('emailProcessing.results.showPerPage', { count: size })}
                         </option>
                       ))}
                     </Select> */} 
                     {/* Empty Box to push pagination to the right if Select is hidden */}
                     <Box width="120px"></Box> 
                     
                     <ButtonGroup size="sm">
                       <IconButton
                         aria-label={t('common.previousPage')}
                         icon={<ChevronLeftIcon />}
                         onClick={() => handlePageChange(currentPage - 1)}
                         // Disable Previous if on page 1 OR if the previous page isn't in cache
                         isDisabled={currentPage === 1 || !pageCache.has(currentPage - 1)}
                         variant="outline"
                       />
                       <Button variant="outline" isDisabled>
                         {t('emailProcessing.results.page', { currentPage: currentPage, totalPages: totalEmails === -1 ? '?' : totalPages })}
                       </Button>
                       <IconButton
                         aria-label={t('common.nextPage')}
                         icon={<ChevronRightIconSolid />}
                         onClick={() => handlePageChange(currentPage + 1)}
                         // Disable Next if nextLink is missing OR if on last page (when total is known)
                         isDisabled={totalEmails === -1 ? !nextLink : currentPage >= totalPages}
                         variant="outline"
                       />
                     </ButtonGroup>
                   </Flex>
                 )}
               </CardBody>
             </Card>
          )}

          {/* --- RESTORED: Analysis Results Card --- */}
          {/* Show this card if analysis was started (jobId exists) OR if it's currently in progress */} 
          {(analysisJobId || isAnalyzing) && (
            <Card variant="outline" mb={6}>
              <CardHeader>
                <Heading size="md" display="flex" alignItems="center">
                  <Icon as={FaChartPie} mr={2} />
                  {t('emailProcessing.analysis.title')}
                  {/* Show Job ID and Status derived from state */} 
                  {analysisJobId && (
                    <Tag ml={2} colorScheme={analysisError ? "red" : (analysisData ? "green" : "blue")}>
                      Job ID: {analysisJobId} - {analysisError ? "Error" : (analysisData ? "Complete" : "Processing")}
                    </Tag>
                  )}
                </Heading>
              </CardHeader>
              <CardBody>
                {/* Display Error */} 
                {analysisError && (
                  <Text color="red.500">Error: {analysisError}</Text>
                )}
                {/* Display Chart if data exists and no error */} 
                {!analysisError && analysisData && transformedChartData && (
                   <SubjectSunburstChart data={transformedChartData} />
                )}
                {/* Display message if analysis complete but no chart data */} 
                {!analysisError && analysisData && !transformedChartData && (
                  <Text>Analysis complete, but no data suitable for charting.</Text>
                )}
                {/* Display loading spinner if processing (isAnalyzing is true) and no error/data yet */} 
                {isAnalyzing && !analysisData && !analysisError && (
                  <Flex align="center">
                    <Spinner size="sm" mr={2} />
                    <Text>{t('emailProcessing.analysis.processingPrompt')}</Text>
                  </Flex>
                )}
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