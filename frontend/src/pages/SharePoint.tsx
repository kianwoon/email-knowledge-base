import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Button,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  useToast,
  Spinner,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Icon,
  Input,
  InputGroup,
  InputRightElement,
  useColorModeValue,
  Center,
  IconButton,
  Skeleton,
  Tag,
  Progress,
  Card,
  SimpleGrid,
  Tabs, TabList, TabPanels, Tab, TabPanel
} from '@chakra-ui/react';
import { FaFolder, FaFile, FaSearch, FaCloudDownloadAlt, FaDatabase, FaGlobeEurope } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import apiClient from '../api/apiClient'; // Changed to default import
import { getTaskStatus } from '../api/tasks'; // Import task API
import { TaskStatusEnum, TaskStatus as TaskStatusInterface } from '../models/tasks'; // Import enum and interface
import QuickAccessList from '../components/QuickAccessList'; // <-- Import the new component
import MyRecentFilesList from '../components/MyRecentFilesList'; // Import the new component

// Interfaces matching backend models
interface SharePointSite {
  id: string;
  name?: string; // Made optional as per backend model
  displayName: string;
  webUrl: string;
}

interface SharePointDrive {
  id: string;
  name?: string; // Made optional as per backend model
  driveType?: string; // Made optional as per backend model
  webUrl: string;
}

interface SharePointItem {
  id: string;
  name?: string; // Made optional as per backend model
  webUrl: string;
  size?: number;
  createdDateTime?: string;
  lastModifiedDateTime?: string;
  isFolder: boolean;
  isFile: boolean;
}

// Skeleton Loader for Table
const ItemTableSkeleton = () => (
  <Table variant="simple">
    <Thead>
      <Tr height="48px">
        <Th><Skeleton height="20px" /></Th>
        <Th><Skeleton height="20px" /></Th>
        <Th isNumeric><Skeleton height="20px" /></Th>
        <Th><Skeleton height="20px" width="40px" /></Th>
      </Tr>
    </Thead>
    <Tbody>
      {[...Array(5)].map((_, index) => (
        <Tr key={index} height="48px">
          <Td><Skeleton height="20px" width="80%" /></Td>
          <Td><Skeleton height="20px" width="60%" /></Td>
          <Td isNumeric><Skeleton height="20px" width="40px" /></Td>
          <Td><Skeleton height="20px" width="40px" /></Td>
        </Tr>
      ))}
    </Tbody>
  </Table>
);

// Skeleton for Site Cards
const SiteCardSkeleton = () => (
  <Card><Skeleton height="80px" /></Card>
);

// Skeleton for Drive Cards (similar to Site)
const DriveCardSkeleton = () => (
    <Card minW="160px"><Skeleton height="60px" /></Card>
);

const SharePointPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();

  // State Management
  const [isLoadingSites, setIsLoadingSites] = useState(true); // Start loading sites initially
  const [isLoadingDrives, setIsLoadingDrives] = useState(false);
  const [isLoadingItems, setIsLoadingItems] = useState(false);
  const [isSearching, setIsSearching] = useState(false); // Separate state for search loading
  const [sites, setSites] = useState<SharePointSite[]>([]);
  const [selectedSite, setSelectedSite] = useState<string>('');
  const [drives, setDrives] = useState<SharePointDrive[]>([]);
  const [selectedDrive, setSelectedDrive] = useState<string>('');
  const [currentBreadcrumbs, setCurrentBreadcrumbs] = useState<{ id: string; name: string }[]>([]);
  const [items, setItems] = useState<SharePointItem[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchPerformed, setSearchPerformed] = useState(false); // Track if a search returned results/no results

  // State for Download Task Polling (similar to FilterSetup)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [isDownloadTaskRunning, setIsDownloadTaskRunning] = useState(false);
  const [taskProgress, setTaskProgress] = useState<number | null>(null);
  const [taskStatus, setTaskStatus] = useState<string | null>(null);
  const [taskDetails, setTaskDetails] = useState<any | null>(null);
  const pollingIntervalRef = React.useRef<NodeJS.Timeout | null>(null);

  // Add state for A-Z filter
  const [selectedLetterFilter, setSelectedLetterFilter] = useState<string | null>(null);

  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');

  // Data Fetching Callbacks
  const fetchSites = useCallback(async () => {
    console.log("[SP Page] Fetching sites...");
    setIsLoadingSites(true);
    // Reset dependent state when fetching sites
    setSites([]);
    setDrives([]);
    setItems([]);
    setSelectedSite('');
    setSelectedDrive('');
    setCurrentBreadcrumbs([]);
    setSearchQuery('');
    setSearchPerformed(false);
    try {
      const response = await apiClient.get('/sharepoint/sites');
      setSites(response.data || []);
      console.log(`[SP Page] Fetched ${response.data?.length || 0} sites.`);
    } catch (error: any) {
      console.error('[SP Page] Error fetching sites:', error);
      toast({ title: t('sharepoint.errors.fetchSitesTitle'), description: error.response?.data?.detail || error.message || t('errors.unknown'), status: 'error', duration: 5000, isClosable: true });
    } finally {
      setIsLoadingSites(false);
    }
  }, [t, toast]);

  const fetchDrives = useCallback(async (siteId: string) => {
    if (!siteId) return;
    console.log(`[SP Page] Fetching drives for site: ${siteId}`);
    setIsLoadingDrives(true);
    // Reset dependent state
    setDrives([]);
    setItems([]);
    setSelectedDrive('');
    setCurrentBreadcrumbs([]);
    setSearchQuery('');
    setSearchPerformed(false);
    try {
      const response = await apiClient.get(`/sharepoint/sites/${siteId}/drives`);
      const fetchedDrives: SharePointDrive[] = response.data || []; // Store fetched data
      setDrives(fetchedDrives);
      console.log(`[SP Page] Fetched ${fetchedDrives.length} drives.`);

    } catch (error: any) {
      console.error(`[SP Page] Error fetching drives for site ${siteId}:`, error);
      toast({ title: t('sharepoint.errors.fetchDrivesTitle'), description: error.response?.data?.detail || error.message || t('errors.unknown'), status: 'error', duration: 5000, isClosable: true });
      setDrives([]); // Clear drives on error
    } finally {
      setIsLoadingDrives(false);
    }
  }, [t, toast]);

  const fetchItems = useCallback(async (driveId: string, itemId: string | null = null) => {
    if (!driveId) return;
    const parentFolderId = itemId || 'root'; // Use 'root' for logging clarity if itemId is null
    console.log(`[SP Page] Fetching items for drive ${driveId}, parent folder ID: '${parentFolderId}'`);
    setIsLoadingItems(true);
    setItems([]);
    setSearchPerformed(false); // Entering browse mode
    setSearchQuery(''); // Clear search query when browsing
    try {
      const response = await apiClient.get(`/sharepoint/drives/${driveId}/items`, {
        // Pass item_id query parameter if provided
        params: itemId ? { item_id: itemId } : {},
      });
      setItems(response.data || []);
      // currentBreadcrumbs is updated by the click handlers, not here directly
      console.log(`[SP Page] Fetched ${response.data?.length || 0} items for parent folder ID '${parentFolderId}'.`);
    } catch (error: any) {
      console.error(`[SP Page] Error fetching items for parent folder ID '${parentFolderId}':`, error);
      toast({ title: t('sharepoint.errors.fetchItemsTitle'), description: error.response?.data?.detail || error.message || t('errors.unknown'), status: 'error', duration: 5000, isClosable: true });
    } finally {
      setIsLoadingItems(false);
    }
  }, [t, toast]);

  const searchDrive = useCallback(async (driveId: string, query: string) => {
    const trimmedQuery = query.trim();
    if (!driveId || !trimmedQuery) {
        toast({ title: t('sharepoint.errors.searchQueryMissing'), status: 'warning', duration: 3000 });
        return;
    }
    console.log(`[SP Page] Searching drive ${driveId} for query: '${trimmedQuery}'`);
    setIsSearching(true); // Use dedicated search loading state
    setItems([]); // Clear current items
    setCurrentBreadcrumbs([]); // Reset breadcrumbs when drive changes
    setSearchPerformed(false); // Reset search performed flag
    try {
      const response = await apiClient.get(`/sharepoint/drives/${driveId}/search`, {
        params: { query: trimmedQuery },
      });
      setItems(response.data || []);
      setSearchPerformed(true); // Mark that search was performed
      console.log(`[SP Page] Search returned ${response.data?.length || 0} items.`);
    } catch (error: any) {
      console.error(`[SP Page] Error searching drive with query '${trimmedQuery}':`, error);
      toast({ title: t('sharepoint.errors.searchFailedTitle'), description: error.response?.data?.detail || error.message || t('errors.unknown'), status: 'error', duration: 5000, isClosable: true });
      setItems([]); // Clear items on error
      setSearchPerformed(true); // Mark search as performed even if error occurred
    } finally {
      setIsSearching(false);
    }
    setSelectedDrive(driveId);
    // Trigger fetchItems for the root when drive changes
    fetchItems(driveId, null); 
  }, [t, toast]);

  // Event Handlers
  const handleSiteSelect = (siteId: string) => {
    if (!siteId || isLoadingSites || isLoadingDrives) return; // Prevent action while loading
    console.log(`[SP Page] Site selected: ${siteId}`);
    // If the same site is clicked again, do nothing (or maybe toggle?) - current behavior: do nothing
    if (siteId === selectedSite) return; 

    setSelectedSite(siteId);
    // Removed setCurrentView('browse'); 
    
    // Reset drive/item state when selecting a new site
    setSelectedDrive('');
    setDrives([]);
    setItems([]);
    setCurrentBreadcrumbs([]);
    setSearchQuery('');
    setSearchPerformed(false);
    // Stop polling if a task was running for the previous site/drive
    stopPolling(); 
    setIsDownloadTaskRunning(false);
    setActiveTaskId(null);
    setTaskStatus(null);
    setTaskProgress(null);
    setTaskDetails(null);

    // Trigger fetchDrives when site is selected
    fetchDrives(siteId);
  };

  const handleLetterFilterClick = (letter: string | null) => {
      setSelectedLetterFilter(letter);
  };

  // Add handler for Drive Card click
  const handleDriveSelect = (driveId: string) => {
    if (!driveId || isLoadingDrives || isLoadingItems) return; // Prevent action while loading
    console.log(`[SP Page] Drive selected: ${driveId}`);
    // If the same drive is clicked again, do nothing
    if (driveId === selectedDrive) return;

    setSelectedDrive(driveId);
    // Trigger fetchItems for the root when drive changes
    fetchItems(driveId, null); 
    // Reset breadcrumbs and search when drive changes
    setCurrentBreadcrumbs([]);
    setSearchQuery('');
    setSearchPerformed(false);
    // Stop polling if relevant to the previous drive/item?
    // Consider if task polling should reset here or only on site change
  };

  const handleItemClick = (item: SharePointItem) => {
    if (isLoadingItems || isSearching) return; // Prevent navigation while loading/searching
    if (item.isFolder) {
      console.log(`[SP Page] Folder clicked: ${item.name} (ID: ${item.id}), navigating...`);
      // Fetch items using the folder's ID
      fetchItems(selectedDrive, item.id);
      // Update breadcrumbs state
      setCurrentBreadcrumbs(prev => [...prev, { id: item.id, name: item.name || 'Unknown Folder' }]);
    }
    // Could add file preview logic here later
  };

  const handleBreadcrumbClick = (index: number) => {
    if (isLoadingItems || isSearching) return; // Prevent navigation while loading/searching
    // index = -1 means root (or drive level)
    const targetItemId = index < 0 ? null : currentBreadcrumbs[index].id;
    const newBreadcrumbs = index < 0 ? [] : currentBreadcrumbs.slice(0, index + 1);
    console.log(`[SP Page] Breadcrumb clicked at index ${index}, navigating to item ID: '${targetItemId || "root"}'`);
    fetchItems(selectedDrive, targetItemId);
    // Update breadcrumbs state
    setCurrentBreadcrumbs(newBreadcrumbs);
  };

  const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      searchDrive(selectedDrive, searchQuery);
    }
  };

  // Download Task Polling Logic
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      console.log('[SP Polling] Stopping polling interval.');
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  const pollTaskStatus = useCallback(async (taskId: string) => {
    console.log(`[SP Polling] Checking status for task ${taskId}...`);
    try {
      const statusResult: TaskStatusInterface = await getTaskStatus(taskId);
      console.log(`[SP Polling] Status received:`, statusResult);
      
      setTaskStatus(statusResult.status);
      setTaskProgress(statusResult.progress ?? taskProgress);
      setTaskDetails(statusResult.message ?? statusResult.details ?? 'No details provided.');

      const finalStates: string[] = [TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED, 'SUCCESS', 'FAILURE'];
      if (finalStates.includes(statusResult.status)) {
        console.log(`[SP Polling] Task ${taskId} reached final state: ${statusResult.status}. Stopping polling.`);
        stopPolling();
        setIsDownloadTaskRunning(false); 
        setActiveTaskId(null); 
        
        const isSuccess = statusResult.status === TaskStatusEnum.COMPLETED || statusResult.status === 'SUCCESS';
        toast({
          title: isSuccess ? t('common.success') : t('common.error'),
          description: statusResult.message || (isSuccess ? t('common.taskCompleted') : t('common.taskFailed')),
          status: isSuccess ? 'success' : 'error',
          duration: 7000,
          isClosable: true,
        });
      }
    } catch (error: any) {
      console.error(`[SP Polling] Error fetching status for task ${taskId}:`, error);
      setTaskStatus(TaskStatusEnum.POLLING_ERROR);
      setTaskDetails(`Error polling status: ${error.message}`);
      stopPolling(); 
      setIsDownloadTaskRunning(false); 
      setActiveTaskId(null);
       toast({ title: t('errors.errorPollingStatus'), description: error.message, status: 'error', duration: 7000 });
    }
  }, [stopPolling, toast, t, taskProgress]);

  const startPolling = useCallback((taskId: string) => {
    stopPolling(); 
    console.log(`[SP Polling] Starting polling for task ${taskId}...`);
    setActiveTaskId(taskId);
    setIsDownloadTaskRunning(true);
    setTaskStatus(TaskStatusEnum.PENDING);
    setTaskProgress(0);
    setTaskDetails('Task submitted, waiting for worker...');
    pollTaskStatus(taskId);
    pollingIntervalRef.current = setInterval(() => pollTaskStatus(taskId), 3000); 
  }, [stopPolling, pollTaskStatus]);

  // Cleanup interval on component unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // --- Effect for Auto-Selecting Single Drive --- 
  useEffect(() => {
    // Run only after drives have loaded for a selected site, 
    // and only if there's exactly one drive and it's not already selected.
    if (!isLoadingDrives && selectedSite && drives.length === 1 && drives[0].id !== selectedDrive) {
        const singleDriveId = drives[0].id;
        if (singleDriveId) {
            console.log(`[SP Page EFFECT] Auto-selecting single drive: ${singleDriveId}`);
            setSelectedDrive(singleDriveId);
            fetchItems(singleDriveId, null); 
            setCurrentBreadcrumbs([]);
            setSearchQuery('');
            setSearchPerformed(false);
        }
    }
    // Dependencies: run when loading finishes, or when drives/selected site change
  }, [isLoadingDrives, drives, selectedSite, selectedDrive, fetchItems]); 

  const handleDownloadClick = async (item: SharePointItem) => {
    if (!item.isFile || !selectedDrive) return;
    console.log(`[SP Page] Download & Process clicked for item: ${item.name} (ID: ${item.id})`);
    
    // Prevent multiple concurrent downloads for simplicity
    if (isDownloadTaskRunning) {
      toast({ title: t('sharepoint.downloadTaskRunningTitle'), description: t('sharepoint.downloadTaskRunningDesc'), status: 'warning', duration: 3000 });
      return;
    }
    
    setIsDownloadTaskRunning(true); // Set loading state immediately
    setActiveTaskId(null); // Clear previous task ID just in case
    setTaskStatus('SUBMITTING');
    setTaskProgress(0);
    setTaskDetails('Submitting download request...');

    try {
        const response = await apiClient.post('/sharepoint/drives/download', {
            drive_id: selectedDrive,
            item_id: item.id,
        });
        
        if (response.data && response.data.task_id) {
          toast({ title: t('sharepoint.downloadStartedTitle'), description: `${t('sharepoint.downloadStartedDesc')} ${item.name}. Task ID: ${response.data.task_id}`, status: 'info', duration: 5000 });
          // Start polling for the submitted task
          startPolling(response.data.task_id);
        } else {
          throw new Error("Invalid response received when submitting download task.");
        }
    } catch (error: any) {
        console.error('[SP Page] Error initiating file download task:', error);
        toast({ title: t('sharepoint.errors.downloadFailedTitle'), description: error.response?.data?.detail || error.message, status: 'error', duration: 7000, isClosable: true });
        // Reset state on submission failure
        setIsDownloadTaskRunning(false);
        setActiveTaskId(null);
        setTaskStatus(null);
        setTaskProgress(null);
        setTaskDetails(null);
    } 
    // Note: setIsDownloadTaskRunning(false) is NOT called here on success, polling handles it.
  };

  // Filtering and Sorting Sites for Display
  const sortedSites = React.useMemo(() => {
      return [...sites].sort((a, b) => a.displayName.localeCompare(b.displayName));
  }, [sites]);

  const filteredSites = React.useMemo(() => {
    if (!selectedLetterFilter) {
      return sortedSites; // Show all if no filter
    }
    return sortedSites.filter(site => 
      site.displayName.toUpperCase().startsWith(selectedLetterFilter!)
    );
  }, [sortedSites, selectedLetterFilter]);

  // Generate alphabet index letters based on available sites
  const availableLetters = React.useMemo(() => {
      const letters = new Set(sortedSites.map(site => site.displayName.charAt(0).toUpperCase()));
      return Array.from(letters).sort();
  }, [sortedSites]);

  // Combined Loading State
  const isAnythingLoading = isLoadingSites || isLoadingDrives || isLoadingItems || isSearching;

  // --- A-Z Index Component ---
  const AlphabetIndex = () => (
      <HStack spacing={1} wrap="wrap" justify="center" mb={4}>
        <Button 
            size="xs" 
            variant={selectedLetterFilter === null ? 'solid' : 'ghost'}
            colorScheme="blue"
            onClick={() => handleLetterFilterClick(null)}
            aria-label={t('common.all')} 
        >
            {t('common.all')}
        </Button>
        {availableLetters.map(letter => (
            <Button 
                key={letter} 
                size="xs" 
                variant={selectedLetterFilter === letter ? 'solid' : 'ghost'}
                onClick={() => handleLetterFilterClick(letter)}
                aria-label={`${t('common.filterBy')} ${letter}`}
            >
                {letter}
            </Button>
        ))}
      </HStack>
  );

  // --- Helper Functions (Moved outside component) ---

const renderBreadcrumbs = ({ 
  drives,
  selectedDrive,
  currentBreadcrumbs,
  searchPerformed,
  isLoadingItems,
  isSearching,
  handleBreadcrumbClick,
  t
}: {
  drives: SharePointDrive[];
  selectedDrive: string;
  currentBreadcrumbs: { id: string; name: string }[];
  searchPerformed: boolean;
  isLoadingItems: boolean;
  isSearching: boolean;
  handleBreadcrumbClick: (index: number) => void;
  t: (key: string) => string; // Adjust based on actual t function type if needed
}) => {
  const driveName = selectedDrive ? drives.find(d => d.id === selectedDrive)?.name || 'Selected Drive' : t('sharepoint.root');
  return (
    <Breadcrumb separator='/' my={{ base: 2, md: 0 }} fontSize="sm" whiteSpace="nowrap" overflow="hidden" textOverflow="ellipsis">
      <BreadcrumbItem>
        <BreadcrumbLink
          onClick={() => !isLoadingItems && handleBreadcrumbClick(-1)}
          fontWeight={currentBreadcrumbs.length === 0 && !searchPerformed ? 'bold' : 'normal'}
          aria-disabled={isLoadingItems || isSearching}
          _disabled={{ opacity: 0.5, cursor: 'not-allowed' }}
          style={{ pointerEvents: (isLoadingItems || isSearching) ? 'none' : 'auto' }}
          title={driveName}
        >
          <Icon as={FaDatabase} mr={1} verticalAlign="middle" />
          {driveName}
        </BreadcrumbLink>
      </BreadcrumbItem>
      {currentBreadcrumbs.map((breadcrumb, index) => (
        <BreadcrumbItem key={index} isCurrentPage={index === currentBreadcrumbs.length - 1 && !searchPerformed}>
          <BreadcrumbLink
            onClick={() => !isLoadingItems && handleBreadcrumbClick(index)}
            fontWeight={index === currentBreadcrumbs.length - 1 && !searchPerformed ? 'bold' : 'normal'}
            aria-disabled={isLoadingItems || isSearching}
            _disabled={{ opacity: 0.5, cursor: 'not-allowed' }}
            style={{ pointerEvents: (isLoadingItems || isSearching) ? 'none' : 'auto' }}
            title={breadcrumb.name}
          >
            {breadcrumb.name}
          </BreadcrumbLink>
        </BreadcrumbItem>
      ))}
      {searchPerformed && (
        <BreadcrumbItem isCurrentPage={true}>
          <Text fontWeight="bold">{t('sharepoint.searchResults')}</Text> {/* Add translation key if missing */} 
        </BreadcrumbItem>
      )}
    </Breadcrumb>
  );
};

const formatDateTime = (dateTimeString?: string): string => {
  if (!dateTimeString) return '-';
  try {
    return new Date(dateTimeString).toLocaleString();
  } catch {
    return dateTimeString; // Return original string if parsing fails
  }
};

const formatFileSize = (bytes?: number): string => {
  if (bytes === undefined || bytes === null) return '-';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const precision = i < 2 ? 1 : 0;
  return parseFloat((bytes / Math.pow(k, i)).toFixed(precision)) + ' ' + sizes[i];
};

  // --- Add back the useEffect hook for initial site fetch --- 
  useEffect(() => {
    fetchSites();
  }, [fetchSites]); // Depend on the memoized callback

  // Main Return
  return (
    <Container maxW="1400px" py={4}>
      <VStack spacing={6} align="stretch">
        <Heading size="lg" textAlign={{ base: 'center', md: 'left' }}>{t('sharepoint.title')}</Heading>

        <Tabs variant="soft-rounded" colorScheme="blue">
          <TabList mb="1em">
            <Tab>{t('sharepoint.tabs.browse')}</Tab> 
            <Tab>{t('sharepoint.tabs.quickAccess')}</Tab> 
            <Tab>{t('sharepoint.tabs.myRecent')}</Tab> {/* Add new tab title */} 
            {/* <Tab>{t('sharepoint.tabs.shared')}</Tab> Placeholder for later */}
          </TabList>
          <TabPanels>
            <TabPanel p={0}> {/* Browse Tab */} 
              <VStack spacing={6} align="stretch">
                {/* --- Site Selection Area --- */}
                <Box>
                  <Text fontSize="lg" mb={2} textAlign="center">{t('sharepoint.selectSitePrompt')}</Text>
                  <AlphabetIndex />
                  {isLoadingSites ? (
                      <HStack overflowX="auto" py={2} spacing={4}>
                          {[...Array(8)].map((_, i) => <Card key={i} minW="180px"><Skeleton height="80px" /></Card>)}
                      </HStack>
                  ) : sites.length > 0 ? (
                      filteredSites.length > 0 ? (
                          <HStack 
                              overflowX="auto" 
                              spacing={4} 
                              py={2} 
                              px={1} // Add some padding for scrollbar visibility
                              css={{ 
                                  '&::-webkit-scrollbar': {
                                      height: '8px',
                                  },
                                  '&::-webkit-scrollbar-thumb': {
                                      background: useColorModeValue('gray.300', 'gray.600'),
                                      borderRadius: '8px',
                                  },
                                  'scrollbarWidth': 'thin' // Firefox
                              }}
                          >
                              {filteredSites.map((site) => (
                                  <Card 
                                      key={site.id} 
                                      p={4} 
                                      onClick={() => handleSiteSelect(site.id)}
                                      cursor="pointer"
                                      _hover={{ shadow: 'md', borderColor: 'blue.400' }}
                                      borderWidth="2px" // Make border thicker for selection feedback
                                      borderColor={selectedSite === site.id ? 'blue.400' : 'transparent'} // Highlight selected
                                      transition="all 0.2s"
                                      minHeight="80px" 
                                      minWidth="180px" // Give cards a minimum width
                                      display="flex"
                                      alignItems="center" 
                                      justifyContent="center" 
                                      textAlign="center"
                                      flexShrink={0} // Prevent cards from shrinking
                                      title={`${site.displayName}\n${site.webUrl}`}
                                  >
                                      <Icon as={FaGlobeEurope} boxSize={5} mb={2} color="gray.500"/> 
                                      <Text fontWeight="medium" noOfLines={2}>{site.displayName}</Text>
                                  </Card>
                              ))}
                          </HStack>
                      ) : ( // Filtered list is empty
                          <Center h="100px">
                              <Text color="gray.500">{t('sharepoint.noSitesFoundForFilter', { letter: selectedLetterFilter })}</Text> {/* Add translation */} 
                          </Center>
                      )
                  ) : ( // Initial load resulted in no sites
                    <Center h="100px">
                      <Text color="gray.500">{t('sharepoint.noSitesFound')}</Text>
                    </Center>
                  )}
                </Box>

                {/* --- Browse Area (Conditional Rendering based on selectedSite) --- */}
                {selectedSite && (
                  <VStack spacing={4} align="stretch" mt={4} pt={4} borderTopWidth="1px"> {/* Add separator */} 
                    {/* --- Add Header for Selected Site --- */}
                    <Heading size="md" mb={2}> 
                      {t('sharepoint.drivesForSite', { siteName: sites.find(s => s.id === selectedSite)?.displayName || selectedSite })}
                    </Heading>

                    {/* Drive Selection Row */} 
                    <Box>
                        {/* <Text fontSize="md" mb={2} fontWeight="medium">{t('sharepoint.drives')}</Text>  <-- Removed redundant/generic title */}
                        {isLoadingDrives ? (
                            <HStack overflowX="auto" py={2} spacing={4}>
                                {[...Array(5)].map((_, i) => <DriveCardSkeleton key={i} />)}
                            </HStack>
                        ) : drives.length > 0 ? (
                            <HStack 
                                overflowX="auto" 
                                spacing={4} 
                                py={2} 
                                px={1} 
                                css={{ /* Scrollbar styles */ }}
                            >
                                {drives.map((drive) => (
                                    <Card 
                                        key={drive.id} 
                                        p={3} // Slightly smaller padding
                                        onClick={() => handleDriveSelect(drive.id)}
                                        cursor="pointer"
                                        _hover={{ shadow: 'md', borderColor: 'teal.400' }} // Use a different color? e.g., teal
                                        borderWidth="2px"
                                        borderColor={selectedDrive === drive.id ? 'teal.400' : 'transparent'} // Highlight selected drive
                                        transition="all 0.2s"
                                        minHeight="60px" 
                                        minWidth="160px" // Slightly smaller cards
                                        display="flex"
                                        alignItems="center" 
                                        justifyContent="center" 
                                        textAlign="center"
                                        flexShrink={0}
                                        title={`${drive.name || 'Unnamed Drive'}\nType: ${drive.driveType || 'N/A'}\n${drive.webUrl}`}
                                    >
                                        {/* Icon can be added based on drive.driveType later */} 
                                        <Text fontWeight="medium" fontSize="sm" noOfLines={2}>{drive.name || 'Unnamed Drive'}</Text>
                                    </Card>
                                ))}
                            </HStack>
                        ) : (
                            <Center h="80px">
                                <Text color="gray.500">{t('sharepoint.noDrivesFound')}</Text>
                            </Center>
                        )}
                    </Box>

                    {/* Search and Breadcrumbs Area (Only show if drive is selected) */}
                    {selectedDrive && (
                      <HStack
                        justify="space-between"
                        mb={4}
                        flexWrap="wrap"
                        alignItems="center"
                        spacing={{ base: 2, md: 4 }}
                      >
                        {/* Breadcrumbs (Takes available space) */}
                        <Box flex={1} minWidth="0" order={{ base: 2, md: 1 }}>
                            {renderBreadcrumbs({ 
                              drives, 
                              selectedDrive, 
                              currentBreadcrumbs, 
                              searchPerformed, 
                              isLoadingItems, 
                              isSearching, 
                              handleBreadcrumbClick, 
                              t 
                            })} 
                        </Box>
                        {/* Search Input (Fixed width) */}
                        <InputGroup size="md" width={{ base: '100%', md: '300px' }} order={{ base: 1, md: 2}}>
                            <Input
                                pr="3.5rem"
                                type="search"
                                placeholder={t('sharepoint.searchDrivePlaceholder')}
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={handleSearchKeyDown}
                                isDisabled={isAnythingLoading || !selectedDrive}
                            />
                            <InputRightElement width="3.5rem">
                                <IconButton
                                    aria-label={t('sharepoint.searchButtonLabel')}
                                    h="1.75rem"
                                    size="sm"
                                    icon={isSearching ? <Spinner size="xs" /> : <Icon as={FaSearch} />}
                                    onClick={() => searchDrive(selectedDrive, searchQuery)}
                                    isDisabled={isAnythingLoading || !selectedDrive || !searchQuery.trim()}
                                />
                            </InputRightElement>
                        </InputGroup>
                      </HStack>
                    )}

                    {/* Task Progress Display */}
                    {isDownloadTaskRunning && activeTaskId && (
                      <Box 
                        p={4} borderWidth="1px" borderRadius="md" 
                        borderColor={taskStatus === 'FAILURE' || taskStatus === 'POLLING_ERROR' ? "red.300" : "blue.300"} 
                        bg={useColorModeValue("blue.50", "blue.900")} mb={4}
                      >
                          <VStack spacing={2} align="stretch">
                            <HStack justify="space-between">
                              <Text fontSize="sm" fontWeight="bold">{t('sharepoint.downloadTaskProgressTitle')}</Text>
                              <Tag 
                                  size="sm"
                                  colorScheme={
                                    taskStatus === TaskStatusEnum.COMPLETED ? 'green' : 
                                    taskStatus === TaskStatusEnum.FAILED || taskStatus === 'POLLING_ERROR' ? 'red' : 
                                    'blue'
                                  }
                                >
                                  {taskStatus || 'Initializing...'}
                                </Tag>
                            </HStack>
                            <Text fontSize="xs">{t('common.taskID', 'Task ID:')} {activeTaskId}</Text>
                            {taskProgress !== null && (
                              <Progress 
                                value={taskProgress} size="xs" 
                                colorScheme={taskStatus === 'FAILURE' || taskStatus === 'POLLING_ERROR' ? 'red' : 'blue'} 
                                isAnimated={taskStatus !== 'SUCCESS' && taskStatus !== 'FAILURE'} 
                                hasStripe={taskStatus !== 'SUCCESS' && taskStatus !== 'FAILURE'} 
                                borderRadius="full"
                              />
                            )}
                            {taskDetails && (
                                <Text fontSize="xs" color="gray.500" mt={1} noOfLines={1} title={typeof taskDetails === 'string' ? taskDetails : JSON.stringify(taskDetails)}>
                                  {typeof taskDetails === 'string' ? taskDetails : JSON.stringify(taskDetails)}
                                </Text>
                            )}
                          </VStack>
                      </Box>
                    )}

                    {/* Files and Folders Table Area */}
                    <Box
                        overflowX="auto"
                        borderWidth={selectedDrive ? "1px" : "0px"}
                        borderRadius="md"
                        borderColor={useColorModeValue('gray.200', 'gray.700')}
                        minHeight="300px"
                        position="relative"
                    >
                        {(isLoadingItems || isSearching) ? (
                            <ItemTableSkeleton />
                        ) : selectedDrive ? (
                            items.length > 0 ? (
                                <Table variant="simple" size="sm">
                                  <Thead>
                                      <Tr>
                                          <Th>{t('sharepoint.name')}</Th>
                                          <Th>{t('sharepoint.modified')}</Th>
                                          <Th isNumeric>{t('sharepoint.size')}</Th>
                                          <Th px={1}>{t('sharepoint.actions')}</Th> 
                                      </Tr>
                                  </Thead>
                                  <Tbody>
                                      {items.map((item) => (
                                      <Tr
                                          key={item.id}
                                          _hover={{ bg: useColorModeValue('gray.50', 'whiteAlpha.100') }}
                                      >
                                          <Td 
                                              cursor={item.isFolder ? 'pointer' : 'default'}
                                              onClick={() => handleItemClick(item)}
                                              title={item.name || 'Unnamed Item'}
                                              maxWidth="500px" // Adjust max width as needed
                                              overflow="hidden"
                                              textOverflow="ellipsis"
                                              whiteSpace="nowrap"
                                              py={2}
                                          >
                                          <HStack spacing={2}>
                                              <Icon 
                                                  as={item.isFolder ? FaFolder : FaFile} 
                                                  color={item.isFolder ? folderColor : fileColor} 
                                                  flexShrink={0}
                                                  boxSize="1.2em" // Slightly larger icon
                                              />
                                              <Text as="span" fontSize="sm">{item.name || 'Unnamed Item'}</Text>
                                          </HStack>
                                          </Td>
                                          <Td fontSize="sm" whiteSpace="nowrap">{formatDateTime(item.lastModifiedDateTime)}</Td>
                                          <Td fontSize="sm" isNumeric whiteSpace="nowrap">{formatFileSize(item.size)}</Td>
                                          <Td px={1} textAlign="center">
                                              {item.isFile && (
                                                  <IconButton
                                                      aria-label={t('sharepoint.downloadFile')}
                                                      icon={<Icon as={FaCloudDownloadAlt} />}
                                                      size="xs"
                                                      variant="ghost"
                                                      onClick={() => handleDownloadClick(item)}
                                                      // Disable if a task is already running for ANY item
                                                      isDisabled={isDownloadTaskRunning} 
                                                      title={isDownloadTaskRunning ? t('sharepoint.downloadTaskRunningDesc') : t('sharepoint.downloadFile')}
                                                  />
                                              )}
                                          </Td>
                                      </Tr>
                                      ))}
                                  </Tbody>
                                </Table>
                            ) : (
                                <Center py={8} minHeight="200px">
                                   {/* ... Empty folder / No search results ... */}
                                </Center>
                            )
                        ) : (
                            <Center py={8} minHeight="200px">
                                <VStack spacing={3} color="gray.500">
                                    <Icon as={FaDatabase} boxSize={8} />
                                    <Text fontSize="lg" fontWeight="medium">{t('sharepoint.selectDrivePrompt')}</Text>
                                    <Text fontSize="sm">{t('sharepoint.selectDriveDesc')}</Text>
                                </VStack>
                            </Center>
                        )
                        }
                    </Box>
                  </VStack>
                )}
              </VStack>
            </TabPanel>
            <TabPanel p={0}> {/* Quick Access Tab */} 
              <QuickAccessList />
            </TabPanel>
            <TabPanel p={0}> {/* My Recent Files Tab */} 
              <MyRecentFilesList /> {/* Render the new component */} 
            </TabPanel>
            {/* <TabPanel p={0}> Placeholder for Shared Tab </TabPanel> */} 
          </TabPanels>
        </Tabs>
      </VStack>
    </Container>
  );
};

export default SharePointPage; 