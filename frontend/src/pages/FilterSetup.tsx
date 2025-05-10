import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  Progress,
  Badge,
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
import { getTaskStatus, TaskStatus } from '../api/tasks';
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
  const [isKbGenerationRunning, setIsKbGenerationRunning] = useState(false);
  const [searchPerformedSuccessfully, setSearchPerformedSuccessfully] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [taskProgress, setTaskProgress] = useState<number | null>(null);
  const [taskStatus, setTaskStatus] = useState<string | null>(null);
  const [taskDetails, setTaskDetails] = useState<any | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
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
  
  // +++ ADDED: useEffect for state monitoring +++
  useEffect(() => {
    console.log('[STATE_EFFECT] State update detected:', {
      currentPage,
      totalPages,
      totalEmails,
      nextLinkState: nextLink, // Value of the separate nextLink state
      filterNextLink: filter.next_link, // Value within the filter object state
      pageCacheKeys: Array.from(pageCache.keys()),
      previewsLength: previews.length
    });
  }, [currentPage, totalPages, totalEmails, nextLink, filter.next_link, pageCache, previews]);
  // --- END Added Effect ---

  // --- Helper Function for Date Formatting ---
  const formatDisplayDate = (dateString: string | null | undefined): string => {
    if (!dateString) {
      return t('common.notAvailable', 'N/A'); // Handle null/undefined/empty
    }
    try {
      const date = new Date(dateString);
      // Check if the date object is valid
      if (isNaN(date.getTime())) {
        console.warn(`[FilterSetup] Could not parse date string: ${dateString}`);
        return t('common.invalidDate', 'Invalid Date'); // Return specific string for invalid dates
      }
      // Use options for a more consistent format if desired, otherwise default locale
      return date.toLocaleDateString(undefined, { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
      }); 
    } catch (e) {
      console.error(`[FilterSetup] Error formatting date string ${dateString}:`, e);
      return t('common.error', 'Error'); // Indicate an error occurred
    }
  };
  // --- End Helper Function ---

  // Load previews
  const loadPreviews = useCallback(async (options?: { size?: number; isFreshSearch?: boolean }) => {
    // Use the explicitly passed size, otherwise default to the current state
    const currentSize = options?.size ?? itemsPerPage;
    const isFreshSearch = options?.isFreshSearch ?? false;
    console.log(`loadPreviews called. Effective size: ${currentSize}, isFreshSearch: ${isFreshSearch}`);

    // Removed isInitialLoad check, handled by isFreshSearch logic now
    // if (isInitialLoad) {
    //   setIsInitialLoad(false);
    // }

    setIsLoadingPreviews(true);
    setSearchPerformedSuccessfully(false); // Reset this flag at the start of any load
    try {
      // Determine if we should use nextLink based on state AND isFreshSearch flag
      const shouldUseNextLink = !isFreshSearch && !!nextLink;
      console.log(`[loadPreviews] shouldUseNextLink determined as: ${shouldUseNextLink} (isFreshSearch: ${isFreshSearch}, nextLink exists: ${!!nextLink})`);

      // --- Use next_link for pagination (only if NOT a fresh search) --- 
      if (shouldUseNextLink) { 
        console.log('Using next_link for pagination:', nextLink);
        // Pass only the next_link, backend handles the rest
        const previewData = await getEmailPreviews({ next_link: nextLink! }); // Use non-null assertion as we checked !!nextLink
        console.log('Next link response:', previewData);
        
        const currentPreviews = previewData.items || [];
        const currentNextLink = previewData.next_link ?? undefined;

        // Update Cache for the *next* page (currentPage + 1 because nextLink loads the next page)
        // CAUTION: This assumes loadPreviews with nextLink is ONLY called by handlePageChange which manages currentPage correctly.
        // If called elsewhere, currentPage might be wrong here.
        const nextPageNumber = currentPage + 1;
        const cacheData: PageCacheEntry = { previews: currentPreviews, nextLink: currentNextLink };
        setPageCache(prevCache => new Map(prevCache).set(nextPageNumber, cacheData));
        console.log(`[loadPreviews - nextLink path] Cached data for potential next page ${nextPageNumber}`);

        // Update state
        setPreviews(currentPreviews);
        setTotalEmails(previewData.total ?? totalEmails); // Keep existing total if not provided
        // Recalculate total pages based on potentially updated total
        const effectiveTotal = previewData.total ?? totalEmails;
        const newTotalPages = effectiveTotal > 0 ? Math.ceil(effectiveTotal / currentSize) : (currentNextLink ? currentPage + 1 : currentPage);
        setTotalPages(newTotalPages);
        setNextLink(currentNextLink); // Update standalone nextLink state
        // setCurrentPage(currentPage + 1); // This must be handled by the caller (handlePageChange)

      } else {
        // --- Initial Load / Fresh Search (isFreshSearch is true or no nextLink exists) --- 
        console.log('[loadPreviews] Performing initial load or fresh search.');
        // Prepare base parameters for the API call, EXCLUDING next_link
        const apiParams: any = {
          folder_id: filter.folder_id || undefined, 
          per_page: currentSize, // Use currentSize determined above
          start_date: filter.start_date || undefined,
          end_date: filter.end_date || undefined,
          keywords: filter.keywords && filter.keywords.length > 0 ? filter.keywords : undefined,
          // DO NOT include filter.next_link here for a fresh search
        };

        // Clean parameters: remove undefined/null keys and empty arrays
        const cleanParams = Object.entries(apiParams)
          .filter(([_, v]) => v !== undefined && v !== null && (!Array.isArray(v) || v.length > 0))
          .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {});
          
        console.log('Sending request with filter (fresh search/initial):', cleanParams);
        const previewData = await getEmailPreviews(cleanParams as EmailFilter & { per_page?: number });
        console.log('Received preview data (fresh search/initial):', previewData);
        console.log(`[FilterSetup] Received ${previewData?.items?.length ?? 0} items from API (fresh search/initial).`);

        const currentPreviews = previewData.items || [];
        const currentNextLink = previewData.next_link ?? undefined;
        
        console.log('[loadPreviews - fresh search] Data received:', { 
            numItems: currentPreviews.length,
            rawTotal: previewData.total, 
            rawNextLink: currentNextLink 
        });

        // Update Cache for page 1
        const cacheData: PageCacheEntry = { previews: currentPreviews, nextLink: currentNextLink };
        // Clear previous cache and set page 1 data
        setPageCache(new Map().set(1, cacheData)); 
        console.log('[loadPreviews - fresh search] Cache reset and updated for page 1.');

        // Update state with data from API
        setPreviews(currentPreviews);
        console.log('[loadPreviews - fresh search] Previews state updated.');
        
        // Update totalEmails, handling null/undefined from API
        const newTotalEmails = (previewData.total === undefined || previewData.total === null) ? -1 : previewData.total;
        setTotalEmails(newTotalEmails);
        console.log(`[loadPreviews - fresh search] TotalEmails state updated to: ${newTotalEmails}`);
        
        // Calculate totalPages based on the newTotalEmails
        const newTotalPages = newTotalEmails === -1
                                ? (currentNextLink ? 2 : 1) // If total unknown, assume 2 pages if nextLink exists, else 1
                                : (newTotalEmails > 0 ? Math.ceil(newTotalEmails / currentSize) : 1);
        setTotalPages(newTotalPages);
        console.log(`[loadPreviews - fresh search] TotalPages state updated to: ${newTotalPages}`);
        
        // Update standalone nextLink state ONLY
        setNextLink(currentNextLink); 
        console.log(`[loadPreviews - fresh search] Standalone nextLink state updated to: ${currentNextLink}`);
        // Do NOT update filter.next_link here, as this path represents the result of page 1
        
        setSearchPerformedSuccessfully(true);

        console.log('Updated state (fresh search/initial):', {
          items: currentPreviews.length,
          total: newTotalEmails,
          pages: newTotalPages,
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
  }, [filter, itemsPerPage, isInitialLoad, toast, t, currentPage]);

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
    // +++ ADD LOGGING AT START +++
    console.log(`[handlePageChange START] CurrentPage: ${currentPage}, TargetPage: ${newPage}, Standalone nextLink state: ${nextLink}`);
    // --- END LOG ---

    // Basic validation
    if (newPage < 1 || (totalPages > 0 && newPage > totalPages) || newPage === currentPage) { // Added check for known totalPages
      console.log(`handlePageChange: Invalid page requested (${newPage}). Current: ${currentPage}, Total: ${totalPages}`);
      return;
    }

    // --- Handle Forward Pagination (using nextLink state variable) --- // MODIFIED HERE
    if (newPage > currentPage) {
      console.log(`[handlePageChange] Forward click detected. Checking standalone nextLink state.`);
      const nextLinkToUse = nextLink; // Use the standalone state variable
      console.log(`[handlePageChange] standalone nextLink state read as: ${nextLinkToUse}`);
      if (!nextLinkToUse) { // Check the standalone state variable
        console.error(`handlePageChange: Trying to go to next page (${newPage}), but standalone nextLink state is missing.`);
        toast({ title: "Pagination Error", description: "Cannot load next page: link is missing.", status: "error", duration: 3000 });
        return;
      }

      console.log(`handlePageChange: Moving forward. CurrentPage: ${currentPage}, TargetPage: ${newPage}, Using standalone NextLink: ${!!nextLinkToUse}`);
      setIsLoadingPreviews(true);
      try {
        console.log(`handlePageChange: Calling getEmailPreviews with filter containing next_link`);
        
        // Prepare the filter object specifically for the next_link call
        const nextLinkFilter: EmailFilter = { next_link: nextLinkToUse }; // Use the value read from state
        
        // Call correctly: pass the filter object containing the next_link,
        // page and itemsPerPage are technically ignored by backend when next_link is used.
        const previewData = await getEmailPreviews(nextLinkFilter); // Remove page/itemsPerPage for next_link call

        console.log('handlePageChange: Received previewData from next_link call:', previewData);
        
        if (previewData && previewData.items) {
            const newPreviews = previewData.items;
            const newNextLink = previewData.next_link ?? undefined;
            const newTotal = previewData.total; // May still be null/undefined from next_link calls

            // --- Cache the new page data BEFORE setting state ---
            const cacheData: PageCacheEntry = { previews: newPreviews, nextLink: newNextLink };
            setPageCache(prevCache => new Map(prevCache).set(newPage, cacheData));
            console.log(`handlePageChange: Cached data for page ${newPage}.`);
            // --- End Cache Update ---

            console.log(`handlePageChange: Calling setPreviews with ${newPreviews.length} items. First new ID: ${newPreviews[0]?.id}`); // LOG PREVIEWS
            setPreviews(newPreviews);

            // Update total if available, otherwise keep existing or handle -1
            if (newTotal !== undefined && newTotal !== null) {
              console.log('handlePageChange: Calling setTotalEmails:', newTotal);
              setTotalEmails(newTotal);
            } else {
              console.log('handlePageChange: TotalEmails not updated as it was null/undefined in response.');
              // Optionally set to -1 if needed, or keep previous value if known
              // setTotalEmails(-1); // Or keep existing if totalEmails > 0
            }

            // Correct totalPages calculation based on potentially updated totalEmails
            const currentTotal = newTotal !== undefined && newTotal !== null ? newTotal : totalEmails; // Use new total if available
            // Ensure itemsPerPage is positive before division
            const effectiveItemsPerPage = itemsPerPage > 0 ? itemsPerPage : 10;
            const newTotalPages = currentTotal === -1
                                    ? (newNextLink ? newPage + 1 : newPage)
                                    : (currentTotal > 0 ? Math.ceil(currentTotal / effectiveItemsPerPage) : 1);
            console.log('handlePageChange: Calling setTotalPages:', newTotalPages);
            setTotalPages(newTotalPages);

            // Update the filter state AND the main nextLink state with the new next_link for the *next* potential step
            setFilter(prev => ({ ...prev, next_link: newNextLink }));
            setNextLink(newNextLink);
            console.log('handlePageChange: Updated filter and nextLink state:', newNextLink); // LOG NEW NEXT LINK

            console.log('handlePageChange: Calling setCurrentPage:', newPage);
            setCurrentPage(newPage);
            // +++ ADDED LOGGING AFTER STATE UPDATES +++
            console.log('[POST-STATE UPDATE CHECK]', {
                currentPageAfterUpdate: newPage,
                nextLinkAfterUpdate: newNextLink, // Log the value we attempted to set
                firstPreviewIdAfterUpdate: newPreviews[0]?.id // Log first ID from the data we set
            });
            // --- END ADDED LOGGING ---
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
      // +++ ADDED: Log cache state on click +++
      console.log(`[handlePageChange] Backward click detected. Checking cache for page ${newPage}. Cache keys:`, Array.from(pageCache.keys()));
      // --- End Log ---
      if (pageCache.has(newPage)) {
        const cachedPage = pageCache.get(newPage)!;
        console.log(`handlePageChange: Loading page ${newPage} from cache.`, cachedPage);
        setPreviews(cachedPage.previews);
        // Restore the next_link associated with the page being loaded from cache
        const cachedNextLink = cachedPage.nextLink;
        // Update both states when loading from cache
        setFilter(prev => ({ ...prev, next_link: cachedNextLink }));
        setNextLink(cachedNextLink);
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
    // Reset pagination state AND cache AND filter's next_link
    setCurrentPage(1);
    setNextLink(undefined);
    setFilter(prev => ({ ...prev, next_link: undefined }));
    setPageCache(new Map());
    setIsInitialLoad(false);
    setPreviews([]); // Clear existing previews before new search
    setTotalEmails(0); // Reset total count before new search
    
    // Add debug logging for the selected folder
    if (filter.folder_id) {
      const selectedFolder = folders.find(f => f.id === filter.folder_id);
      console.log(`[DEBUG] Searching folder: "${selectedFolder?.displayName}" (ID: ${filter.folder_id})`);
    }
    
    // Explicitly tell loadPreviews this is a fresh search
    loadPreviews({ isFreshSearch: true }); 
  }, [loadPreviews, filter.folder_id, folders]);
  
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

  // Helper function to properly translate task status for all locales including Chinese
  const getTranslatedTaskStatus = useCallback((status: string | null): string => {
    if (!status) return t('common.notAvailable', { defaultValue: 'N/A' });
    
    // Use statusMessages namespace for translating task statuses
    try {
      // First try with statusMessages namespace which has direct translations
      const translated = t(`statusMessages.${status.toLowerCase()}`, { defaultValue: status });
      
      // Check if translated is an object (occurs with some i18next configurations/warnings)
      if (typeof translated === 'object') {
        // Log warning but don't display to user
        console.warn(`[FilterSetup] Translation returned an object for status key: statusMessages.${status.toLowerCase()}. Falling back to status string.`);
        // Return the original status string as a safe fallback.
        return status;
      }
      
      // If translated is a string, return it.
      return translated;
    } catch (error) {
      // Log error but don't display to user
      console.warn(`[FilterSetup] Translation error for status: ${status}`, error);
      // Return the status string directly without error message
      return status;
    }
  }, [t]);

  // Helper function to format task details for display
  const formatTaskDetails = useCallback((details: any): string => {
    if (!details) return '';
    
    if (typeof details === 'string') {
      return details;
    }
    
    // Try to extract useful information if it's an object
    if (typeof details === 'object') {
      // If there's a final_message, use that
      if (details.final_message && typeof details.final_message === 'string') {
        return details.final_message;
      }
      
      // If we have processing stats, format them
      const { emails_processed, emails_failed, attachments_processed, attachments_failed } = details;
      if ([emails_processed, emails_failed, attachments_processed, attachments_failed].some(count => typeof count === 'number')) {
        return t('kbGeneration.successDetails', 
          {
            processed: emails_processed ?? 0,
            failed: emails_failed ?? 0,
            attProcessed: attachments_processed ?? 0,
            attFailed: attachments_failed ?? 0
          }
        );
      }
      
      // Last resort: stringify the object
      try {
        return JSON.stringify(details);
      } catch (err) {
        console.error('[FilterSetup] Error stringifying task details:', err);
        return t('common.error', 'Error formatting details');
      }
    }
    
    return String(details);
  }, [t]);

  // --- Polling Logic (Defined inside component scope) --- 
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      console.log('[Polling] Stopping polling interval.');
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []); // No dependencies, interval ref managed internally

  const pollTaskStatus = useCallback(async (taskId: string) => {
    console.log(`[Polling] Checking status for task ${taskId}...`);
    try {
      const statusResult = await getTaskStatus(taskId);
      console.log(`[Polling] Status received:`, statusResult);
      
      // Update state based on response
      setTaskStatus(statusResult.status);
      
      // Ensure progress is calculated as 0-100, rounded up, and capped
      const newProgressValue = statusResult.progress !== undefined && statusResult.progress !== null
        ? Math.ceil(Math.min(Math.max(statusResult.progress * 100, 0), 100)) // Multiply, clamp 0-100, THEN round up
        : taskProgress; // Keep existing progress if API doesn't provide it
      setTaskProgress(newProgressValue);
      
      setTaskDetails(statusResult.details ?? 'No details provided.');

      // Check for final states
      if (statusResult.status === 'SUCCESS' || statusResult.status === 'FAILURE') {
        console.log(`[Polling] Task ${taskId} reached final state: ${statusResult.status}. Stopping polling.`);
        stopPolling();
        setIsKbGenerationRunning(false); // Task finished, allow button clicks again
        setActiveTaskId(null); // Clear active task ID
        
        // --- Determine Toast Description --- 
        let description = '';
        if (statusResult.status === 'SUCCESS') {
            // Check if details object has the expected counts
            const details = statusResult.details;
            if (typeof details === 'object' && details !== null && 
                (['emails_processed', 'emails_failed', 'attachments_processed', 'attachments_failed']
                .some(key => typeof details[key] === 'number'))
            ) {
                // Use counts from details for translation
                description = t('kbGeneration.successDetails', {
                    processed: details.emails_processed ?? 0,
                    failed: details.emails_failed ?? 0,
                    attProcessed: details.attachments_processed ?? 0,
                    attFailed: details.attachments_failed ?? 0
                });
            } else {
                // Details is a string or missing counts, use generic translated success message
                description = t('kbGeneration.successGeneric'); // <-- Use the new generic key
                // Optionally, log if details was unexpected string or object
                if (typeof details === 'string') {
                    console.warn(`[Polling] SUCCESS task ${taskId} returned details as a string: "${details}". Using generic translated message.`);
                } else if (details && typeof details === 'object') { // Check if details is an object but not the expected one
                    console.warn(`[Polling] SUCCESS task ${taskId} returned details in unexpected object format:`, details, ". Using generic translated message.");
                } else if (details) { // Handle other unexpected types
                     console.warn(`[Polling] SUCCESS task ${taskId} returned details in unexpected format (type: ${typeof details}):`, details, ". Using generic translated message.");
                }
            }
        } else { // status is FAILURE
            // For failure, attempt to format whatever details were provided
            description = formatTaskDetails(statusResult.details); 
        }
        // --- End Determine Toast Description --- 
        
        toast({
          title: statusResult.status === 'SUCCESS' ? t('common.success') : t('common.error'),
          description: description, // Use the determined description
          status: statusResult.status === 'SUCCESS' ? 'success' : 'error',
          duration: 7000,
          isClosable: true,
        });
      }
    } catch (error: any) {
      console.error(`[Polling] Error fetching status for task ${taskId}:`, error);
      setTaskStatus('POLLING_ERROR');
      setTaskDetails(`Error polling status: ${error.message}`);
      // Optionally stop polling on error, or let it retry
      stopPolling(); 
      setIsKbGenerationRunning(false); // Stop loading indicator on polling error
      setActiveTaskId(null);
       toast({
          title: t('errors.errorPollingStatus'),
          description: error.message,
          status: 'error',
          duration: 7000,
        });
    }
  }, [stopPolling, toast, t, taskProgress, formatTaskDetails]); // Added formatTaskDetails to dependencies

  const startPolling = useCallback((taskId: string) => {
    stopPolling(); // Ensure no previous interval is running
    console.log(`[Polling] Starting polling for task ${taskId}...`);
    // Initial check immediately
    pollTaskStatus(taskId);
    // Set interval for subsequent checks (e.g., every 3 seconds)
    pollingIntervalRef.current = setInterval(() => {
      // Pass taskId to the function inside interval
      pollTaskStatus(taskId);
    }, 3000); // Adjust interval as needed
  }, [stopPolling, pollTaskStatus]); // Include dependencies

  // Cleanup interval on component unmount
  useEffect(() => {
    // Return the cleanup function
    return () => {
      stopPolling();
    };
  }, [stopPolling]); // Dependency array ensures cleanup uses the latest stopPolling
  // --- End Polling Logic ---

  // Handler for the "Save to Knowledge Base" button (UPDATED for Async Task)
  const handleSaveToKnowledgeBase = async () => {
    if (!searchPerformedSuccessfully || previews.length === 0) {
      toast({ title: t('common.warning'), description: t('emailProcessing.notifications.noEmailsToProcess'), status: "warning", duration: 3000 });
      return;
    }

    console.log('[handleSaveToKnowledgeBase] Setting loading TRUE and submitting task...');
    setIsKbGenerationRunning(true); // Indicate the process has started (task submission)
    setActiveTaskId(null);
    setTaskProgress(0);
    setTaskStatus('SUBMITTING');
    setTaskDetails('Submitting task to backend...');

    try {
      // Call the API function that dispatches the task
      const response = await saveFilteredEmailsToKnowledgeBase(filter);
      
      // Task submitted successfully, store the task ID
      setActiveTaskId(response.task_id);
      setTaskStatus('PENDING'); // Initial status after successful submission
      setTaskDetails(`Task ${response.task_id} submitted. Waiting for progress...`);
      toast({
        title: t('emailProcessing.notifications.knowledgeBaseSaveSubmitted.title'),
        description: t('emailProcessing.notifications.knowledgeBaseSaveSubmitted.description', { taskId: response.task_id }), // Pass taskId for interpolation
        status: 'info', // Use info for submission, success comes later
        duration: 5000,
      });

      // Start polling for task status
      startPolling(response.task_id); // Use the function defined within component scope

    } catch (error: any) {
      console.error(`Error submitting KB generation task:`, error);
      const errorMessage = error.message || t('errors.unknownError'); 
      toast({
        title: t('errors.errorSubmittingTask'), // Specific error for submission failure
        description: errorMessage,
        status: 'error', duration: 7000,
      });
       // Reset states on submission failure
       console.log('[handleSaveToKnowledgeBase] Task submission failed. Setting loading FALSE');
       setIsKbGenerationRunning(false);
       setActiveTaskId(null);
       setTaskProgress(null);
       setTaskStatus('FAILED_SUBMISSION');
       setTaskDetails(`Failed to submit task: ${errorMessage}`);
    } 
    // NOTE: setIsKbGenerationRunning(false) is NOT called here immediately.
    // It will be set to false when polling indicates a final state (SUCCESS/FAILURE).
  };
  
  // --- Derived State and Tooltips (Update to use isKbGenerationRunning) --- 
  const isProcessing = isAnalyzing || isKbGenerationRunning; // Check if analyzing OR generating KB
  const canClickButtons = searchPerformedSuccessfully && previews.length > 0 && !isProcessing;
  const analyzeButtonTooltip = t('emailProcessing.tooltips.analyze'); 
  // Update tooltip if KB generation is running
  const proceedButtonTooltip = isKbGenerationRunning ? t('kbGeneration.tooltips.running') : t('emailProcessing.tooltips.proceedDirectSave'); 

  // WebSocket connection effect
  useEffect(() => {
    // --- Restore usage of VITE_WEBSOCKET_URL --- 
    const wsBaseUrlFromEnv = import.meta.env.VITE_WEBSOCKET_URL;
    let wsBaseUrl: string;

    if (wsBaseUrlFromEnv) {
        // Use env var, ensure it doesn't end with /analysis or /
        wsBaseUrl = wsBaseUrlFromEnv.replace(/\/analysis$|\/$/, ''); 
        console.log(`[WebSocket] Using base URL from VITE_WEBSOCKET_URL (cleaned): ${wsBaseUrl}`);
    } else {
        // Construct default base URL ( fallback if env var is missing )
        const host = window.location.hostname;
        const protocol = (host === 'localhost' || host === '127.0.0.1') ? 'ws' : (window.location.protocol === 'https:' ? 'wss' : 'ws');
        wsBaseUrl = `${protocol}://${host}:8000/api/v1/ws`; // Default to localhost:8000/api/v1/ws
        console.log(`[WebSocket] VITE_WEBSOCKET_URL not found. Using default base URL: ${wsBaseUrl}`);
    }
    
    if (!wsBaseUrl) { 
      console.error("[WebSocket] Base URL could not be determined.");
      setAnalysisError("WebSocket URL not configured.");
      return; 
    }

    // Append the endpoint path exactly once
    const wsUrl = `${wsBaseUrl}/analysis`; 
    console.log(`[WebSocket] Attempting to connect to FINAL URL (from Env/Default): ${wsUrl}`);
    // --- End Restore --- 

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
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        console.log('[WebSocket] Closing connection on cleanup.');
        ws.close();
      }
    };
  }, [toast, t]);

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
                       
                       {/* Proceed Button - Render unconditionally, rely on isDisabled */}
                          <Tooltip label={proceedButtonTooltip} placement="top">
                             {/* Wrap Box in Tooltip to ensure tooltip still works when button is disabled */} 
                             <Box as="span" display="inline-block"> 
                                <Button
                                  leftIcon={<FaSave />} size="sm" colorScheme="teal"
                                  onClick={handleSaveToKnowledgeBase}
                                  isLoading={isKbGenerationRunning} // Spinner based on this state
                                  loadingText={t('emailProcessing.actions.proceedGenerateKB')}
                                  isDisabled={isProcessing} // Disable based on combined state
                                >
                                  {t('emailProcessing.actions.proceedGenerateKB')}
                                </Button>
                             </Box>
                          </Tooltip>
                       
                       {/* Pagination (Update isDisabled for Previous button) */}
                       {previews.length > 0 && !isLoadingPreviews && totalPages > 1 && (
                           <ButtonGroup size="sm" isAttached variant="outline">
                              <IconButton
                                aria-label={t('common.previousPage')}
                                icon={<ChevronLeftIcon />}
                                onClick={() => handlePageChange(currentPage - 1)}
                                // Disable Previous primarily if on page 1
                                isDisabled={currentPage === 1} // Simplified check
                                variant="outline"
                              />
                              <IconButton
                                aria-label={t('common.nextPage')}
                                icon={<ChevronRightIconSolid />}
                                onClick={() => handlePageChange(currentPage + 1)}
                                // Disable Next if nextLink is missing OR if on last page (when total is known)
                                isDisabled={totalEmails === -1 ? !nextLink : currentPage >= totalPages}
                                variant="outline"
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
                                 <Text noOfLines={1} title={email.sender?.emailAddress?.name || t('common.unknownSender')}>
                                   {email.sender?.emailAddress?.name || t('common.unknownSender')}
                                 </Text>
                               </Td>
                               <Td>
                                 <Text noOfLines={1} title={email.subject || t('common.noSubject')}>
                                   {email.subject || t('common.noSubject')}
                                 </Text>
                               </Td>
                               <Td>
                                 <Text noOfLines={1}>
                                   {email.receivedDateTime ? new Date(email.receivedDateTime).toLocaleString() : '-'}
                                 </Text>
                               </Td>
                               <Td>
                                 <Text noOfLines={1}>
                                   {email.hasAttachments ? t('common.yes') : t('common.no')}
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
                 
                 {/* Pagination controls have been moved to the card header for better UX */}
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
                      {t('common.taskID', { defaultValue: 'Task ID:' })} {analysisJobId} - {analysisError ? getTranslatedTaskStatus('FAILURE') : (analysisData ? getTranslatedTaskStatus('SUCCESS') : getTranslatedTaskStatus('PROGRESS'))}
                    </Tag>
                  )}
                </Heading>
              </CardHeader>
              <CardBody>
                {/* Display Error */} 
                {analysisError && (
                  <Text color="red.500">{t('common.error', 'Error')}: {analysisError}</Text>
                )}
                {/* Display Chart if data exists and no error */} 
                {!analysisError && analysisData && transformedChartData && (
                   <SubjectSunburstChart data={transformedChartData} />
                )}
                {/* Display message if analysis complete but no chart data */} 
                {!analysisError && analysisData && !transformedChartData && (
                  <Text>{t('emailProcessing.analysis.noData', 'Analysis complete, but no data suitable for charting.')}</Text>
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

          {/* --- Task Progress Display --- */} 
          {isKbGenerationRunning && activeTaskId && (
            <Card variant="outline" mb={6} borderColor={taskStatus === 'FAILURE' || taskStatus === 'POLLING_ERROR' ? "red.300" : "blue.300"}>
              <CardHeader pb={2}>
                  <Heading size="md" display="flex" alignItems="center">
                    <Spinner size="sm" mr={3} /> 
                    {t('kbGeneration.progressTitle', 'Knowledge Base Generation Progress')}
                  </Heading>
              </CardHeader>
              <CardBody pt={2}>
                <VStack spacing={3} align="stretch">
                  <Text fontSize="sm"><strong>{t('common.taskID', { defaultValue: 'Task ID:' })}</strong> {activeTaskId}</Text>
                  <Text fontSize="sm">
                    <strong>{t('common.statusLabel', { defaultValue: 'Status:' })}</strong> 
                    <Badge 
                      ml={2} 
                      colorScheme={
                        taskStatus === 'SUCCESS' ? 'green' : 
                        taskStatus === 'FAILURE' || taskStatus === 'POLLING_ERROR' ? 'red' : 
                        taskStatus === 'PROGRESS' ? 'blue' : 'gray'
                      }
                    >
                      {getTranslatedTaskStatus(taskStatus) || t('statusMessages.submitting', { defaultValue: 'Initializing...' })}
                    </Badge>
                  </Text>
                  {taskProgress !== null && (
                    <Box>
                      <Text fontSize="xs" mb={1} textAlign="right">{taskProgress}%</Text>
                      <Progress 
                        value={taskProgress} 
                        size="sm" 
                        colorScheme={taskStatus === 'FAILURE' || taskStatus === 'POLLING_ERROR' ? 'red' : 'blue'} 
                        hasStripe={['PROGRESS', 'STARTED', 'PENDING'].includes(taskStatus || '')} // Keep stripe for all non-final states
                        isAnimated={taskStatus === 'PROGRESS'} // Animate only when actively progressing
                        borderRadius="md"
                      />
                    </Box>
                  )}
                  {taskDetails && (
                      <Text fontSize="xs" color="gray.500" mt={1}>
                        {formatTaskDetails(taskDetails)}
                      </Text>
                  )}
                </VStack>
              </CardBody>
            </Card>
          )}
          {/* --- End Task Progress Display --- */} 

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