import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
import { FaFolder, FaFile, FaSearch, FaCloudDownloadAlt, FaDatabase, FaGlobeEurope, FaSort, FaSortUp, FaSortDown } from 'react-icons/fa';
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

// +++ Add Sorting Types +++
type BrowseSortableColumns = 'name' | 'lastModifiedDateTime' | 'size'; // Adjusted for available columns
type BrowseSortDirection = 'asc' | 'desc';
// +++ End Sorting Types +++

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

  // +++ Add State for Browse Table Sorting +++
  const [browseSortBy, setBrowseSortBy] = useState<BrowseSortableColumns>('name');
  const [browseSortDirection, setBrowseSortDirection] = useState<BrowseSortDirection>('asc');
  // +++ End Sorting State +++

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
  const tableBg = useColorModeValue('white', 'gray.800'); // Assuming gray.800 is preferred
  const hoverBg = useColorModeValue('gray.50', 'whiteAlpha.100');

  // --- Define polling functions FIRST --- 
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
  // --- End Polling Functions --- 

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
  }, [t, toast, fetchItems]);

  // Event Handlers (Now defined AFTER polling functions)
  const handleSiteSelect = useCallback((siteId: string) => {
    if (!siteId || isLoadingSites || isLoadingDrives) return; 
    console.log(`[SP Page] Site selected: ${siteId}`);
    if (siteId === selectedSite) return; 
    setSelectedSite(siteId);
    setSelectedDrive('');
    setDrives([]);
    setItems([]);
    setCurrentBreadcrumbs([]);
    setSearchQuery('');
    setSearchPerformed(false);
    stopPolling(); 
    setIsDownloadTaskRunning(false);
    setActiveTaskId(null);
    setTaskStatus(null);
    setTaskProgress(null);
    setTaskDetails(null);
    fetchDrives(siteId);
  }, [fetchDrives, isLoadingSites, isLoadingDrives, selectedSite, stopPolling]);

  const handleLetterFilterClick = (letter: string | null) => {
      setSelectedLetterFilter(letter);
  };

  const handleDriveSelect = useCallback((driveId: string) => {
    if (!driveId || isLoadingDrives || isLoadingItems) return; 
    console.log(`[SP Page] Drive selected: ${driveId}`);
    setSelectedDrive(driveId);
    // Trigger fetchItems for the root of the selected drive
    fetchItems(driveId, null);
    // Reset breadcrumbs to just the drive name
    const driveName = drives.find(d => d.id === driveId)?.name || 'Drive';
    setCurrentBreadcrumbs([{ id: 'root', name: driveName }]); // Start breadcrumbs at drive level
    setSearchQuery('');
    setSearchPerformed(false);
    // Reset sorting when drive changes
    setBrowseSortBy('name');
    setBrowseSortDirection('asc');
  }, [fetchItems, isLoadingDrives, isLoadingItems, drives]);

  const handleItemClick = useCallback((item: SharePointItem) => {
    if (isLoadingItems || isSearching) return; 
    if (item.isFolder) {
      console.log(`[SP Page] Folder clicked: ${item.name} (ID: ${item.id})`);
      fetchItems(selectedDrive, item.id); // Fetch items for the clicked folder
      // Add clicked folder to breadcrumbs
      setCurrentBreadcrumbs(prev => [...prev, { id: item.id, name: item.name || 'Unknown Folder' }]);
      // Reset sorting when navigating folders
      setBrowseSortBy('name');
      setBrowseSortDirection('asc');
    }
  }, [fetchItems, isLoadingItems, isSearching, selectedDrive, currentBreadcrumbs]);

  const handleBreadcrumbClick = useCallback((index: number) => {
    if (isLoadingItems || isSearching) return; 
    // index = -1 means root (or drive level)
    const targetItemId = index < 0 ? null : currentBreadcrumbs[index].id;
    const parentFolderId = targetItemId === 'root' ? null : targetItemId;
    console.log(`[SP Page] Breadcrumb clicked: Index ${index}, Target Item ID: '${targetItemId}', Fetching for Parent ID: '${parentFolderId}'`);
    fetchItems(selectedDrive, parentFolderId); // Fetch items for the clicked breadcrumb level
    // Update breadcrumbs state
    const newBreadcrumbs = currentBreadcrumbs.slice(0, index + 1);
    setCurrentBreadcrumbs(newBreadcrumbs);
    // Reset sorting when navigating folders
    setBrowseSortBy('name');
    setBrowseSortDirection('asc');
  }, [fetchItems, isLoadingItems, isSearching, selectedDrive, currentBreadcrumbs]);

  const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      searchDrive(selectedDrive, searchQuery);
    }
  };

  const handleDownloadClick = useCallback(async (item: SharePointItem) => {
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
  }, [selectedDrive, isDownloadTaskRunning, t, toast, startPolling]);

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

  // +++ Add Browse Sort Handler +++
  const handleBrowseSort = useCallback((column: BrowseSortableColumns) => {
    setBrowseSortBy(prevSortBy => {
      if (prevSortBy === column) {
        setBrowseSortDirection(prevDir => prevDir === 'asc' ? 'desc' : 'asc');
      } else {
        setBrowseSortDirection('asc'); // Default to ascending for browse
      }
      return column;
    });
  }, []);
  // +++ End Sort Handler +++

  // +++ Add Browse Sort Icon Helper +++
  const BrowseSortIcon = ({ column }: { column: BrowseSortableColumns }) => {
    if (browseSortBy !== column) {
      return <Icon as={FaSort} aria-label="sortable" color="gray.400" />; 
    }
    return browseSortBy === column && browseSortDirection === 'asc' ?
      <Icon as={FaSortUp} aria-label="sorted ascending" /> :
      <Icon as={FaSortDown} aria-label="sorted descending" />;
  };
  // +++ End Sort Icon Helper +++

  // +++ Create Memoized Sorted Items List +++
  const sortedAndFilteredItems = useMemo(() => {
    let processedItems = [...items]; // Start with the current items

    // Apply Sorting
    processedItems.sort((a, b) => {
      let aValue: any;
      let bValue: any;

      // Handle potentially missing values (treat null/undefined as lowest/empty)
      aValue = browseSortBy === 'size' ? (a.size ?? -1) : (a[browseSortBy] || '');
      bValue = browseSortBy === 'size' ? (b.size ?? -1) : (b[browseSortBy] || '');

      // Handle date sorting
      if (browseSortBy === 'lastModifiedDateTime') {
        aValue = a.lastModifiedDateTime ? new Date(a.lastModifiedDateTime).getTime() : 0;
        bValue = b.lastModifiedDateTime ? new Date(b.lastModifiedDateTime).getTime() : 0;
      }

      // Comparison logic (numbers or strings)
      let comparison = 0;
      if (typeof aValue === 'number' && typeof bValue === 'number') {
         comparison = aValue - bValue;
      } else {
         const strA = String(aValue);
         const strB = String(bValue);
         // Prioritize folders when sorting by name
         if (browseSortBy === 'name') {
             if (a.isFolder && !b.isFolder) return -1;
             if (!a.isFolder && b.isFolder) return 1;
         }
         comparison = strA.localeCompare(strB);
      }
     
      return browseSortDirection === 'asc' ? comparison : comparison * -1;
    });

    return processedItems;
  }, [items, browseSortBy, browseSortDirection]);
  // +++ End Memoized List +++

  // Effects
  useEffect(() => {
    // Auto-select single drive
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

  useEffect(() => {
    // Cleanup polling interval on unmount
    return () => stopPolling();
  }, [stopPolling]);

  // Main Return
  return (
    <Container maxW="1400px" py={4}>
      <VStack spacing={6} align="stretch">
        <Heading size="lg" textAlign={{ base: 'center', md: 'left' }}>{t('sharepoint.title')}</Heading>

        <Tabs variant="soft-rounded" colorScheme="blue">
          <TabList mb="1em">
            <Tab>{t('sharepoint.tabs.browseSites')}</Tab>
            <Tab>{t('sharepoint.tabs.quickAccess')}</Tab>
            <Tab>{t('sharepoint.tabs.myRecent')}</Tab>
          </TabList>
          <TabPanels>
            <TabPanel p={0}>
              <VStack spacing={6} align="stretch">
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
                              px={1}
                              css={{ 
                                  '&::-webkit-scrollbar': {
                                      height: '8px',
                                  },
                                  '&::-webkit-scrollbar-thumb': {
                                      background: useColorModeValue('gray.300', 'gray.600'),
                                      borderRadius: '8px',
                                  },
                                  'scrollbarWidth': 'thin'
                              }}
                          >
                              {filteredSites.map((site) => (
                                  <Card 
                                      key={site.id} 
                                      p={4} 
                                      onClick={() => handleSiteSelect(site.id)}
                                      cursor="pointer"
                                      _hover={{ shadow: 'md', borderColor: 'blue.400' }}
                                      borderWidth="2px"
                                      borderColor={selectedSite === site.id ? 'blue.400' : 'transparent'}
                                      transition="all 0.2s"
                                      minHeight="80px" 
                                      minWidth="180px"
                                      display="flex"
                                      alignItems="center" 
                                      justifyContent="center" 
                                      textAlign="center"
                                      flexShrink={0}
                                      title={`${site.displayName}\n${site.webUrl}`}
                                  >
                                      <Icon as={FaGlobeEurope} boxSize={5} mb={2} color="gray.500"/> 
                                      <Text fontWeight="medium" noOfLines={2}>{site.displayName}</Text>
                                  </Card>
                              ))}
                          </HStack>
                      ) : (
                          <Center h="100px">
                              <Text color="gray.500">{t('sharepoint.noSitesFoundForFilter', { letter: selectedLetterFilter })}</Text>
                          </Center>
                      )
                  ) : (
                    <Center h="100px">
                      <Text color="gray.500">{t('sharepoint.noSitesFound')}</Text>
                    </Center>
                  )}
                </Box>

                {selectedSite && (
                  <VStack spacing={4} align="stretch" mt={4} pt={4} borderTopWidth="1px">
                    <Heading size="md" mb={2}> 
                      {t('sharepoint.drivesForSite', { siteName: sites.find(s => s.id === selectedSite)?.displayName || selectedSite })}
                    </Heading>

                    <Box>
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
                                css={{ }}
                            >
                                {drives.map((drive) => (
                                    <Card 
                                        key={drive.id} 
                                        p={3}
                                        onClick={() => handleDriveSelect(drive.id)}
                                        cursor="pointer"
                                        _hover={{ shadow: 'md', borderColor: 'teal.400' }}
                                        borderWidth="2px"
                                        borderColor={selectedDrive === drive.id ? 'teal.400' : 'transparent'}
                                        transition="all 0.2s"
                                        minHeight="60px" 
                                        minWidth="160px"
                                        display="flex"
                                        alignItems="center" 
                                        justifyContent="center" 
                                        textAlign="center"
                                        flexShrink={0}
                                        title={`${drive.name || 'Unnamed Drive'}\nType: ${drive.driveType || 'N/A'}\n${drive.webUrl}`}
                                    >
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

                    {/* Render Search, Breadcrumbs, Progress, Table only when drive selected */} 
                    {selectedDrive && (
                      <>
                        {/* 1. Search Input */} 
                        <InputGroup size="md" mb={2}> {/* Add mb to separate from breadcrumbs */}
                            <Input
                                placeholder={t('sharepoint.searchDrivePlaceholder')}
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={handleSearchKeyDown}
                                bg={useColorModeValue('white', 'gray.700')}
                                pr="3rem"
                                isDisabled={isAnythingLoading || !selectedDrive}
                            />
                            <InputRightElement width="3rem">
                                <IconButton
                                    h="1.75rem"
                                    size="sm"
                                    aria-label={t('sharepoint.searchDrive') || 'Search'}
                                    icon={<Icon as={FaSearch} />}
                                    onClick={() => searchDrive(selectedDrive, searchQuery)}
                                    isDisabled={false}
                                    colorScheme="blue"
                                />
                            </InputRightElement>
                        </InputGroup>

                        {/* 2. Breadcrumbs Row */}
                        <HStack
                          width="100%"
                          alignItems="center" 
                          spacing={4}
                          mb={4} // Add margin bottom to separate from table/progress
                        >
                          <Box flex={1} minWidth="0">
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
                        </HStack>
                        
                        {/* 3. Task Progress Display */} 
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

                        {/* 4. Files and Folders Table Area */} 
                        <Box
                            overflowX="auto"
                            bg={tableBg} 
                            borderRadius="md"
                            borderWidth="1px"
                        >
                           {isLoadingItems ? (
                               <ItemTableSkeleton />
                           ) : sortedAndFilteredItems.length > 0 ? ( // <-- Use sorted list
                               <Table variant="simple" size="sm"> {/* Use sm size */}
                                 <Thead>
                                   <Tr>
                                     {/* Make headers sortable */}
                                     <Th cursor="pointer" onClick={() => handleBrowseSort('name')}>
                                        <HStack spacing={1}>{t('sharepoint.name')} <BrowseSortIcon column="name" /></HStack>
                                     </Th>
                                     <Th cursor="pointer" onClick={() => handleBrowseSort('lastModifiedDateTime')}>
                                        <HStack spacing={1}>{t('sharepoint.modified')} <BrowseSortIcon column="lastModifiedDateTime" /></HStack>
                                     </Th>
                                     <Th cursor="pointer" onClick={() => handleBrowseSort('size')} isNumeric>
                                        <HStack spacing={1} justify="flex-end">{t('sharepoint.size')} <BrowseSortIcon column="size" /></HStack>
                                     </Th>
                                     <Th>{t('sharepoint.actions')}</Th>
                                   </Tr>
                                 </Thead>
                                 <Tbody>
                                   {/* Map over sorted list */} 
                                   {sortedAndFilteredItems.map((item) => (
                                     <Tr key={item.id} _hover={{ bg: hoverBg }}> {/* Use consistent hover */}
                                       <Td py={2}> {/* Use consistent padding */} 
                                         <HStack spacing={2} alignItems="center">
                                           <Icon 
                                             as={item.isFolder ? FaFolder : FaFile} 
                                             color={item.isFolder ? folderColor : fileColor} 
                                             flexShrink={0}
                                             boxSize="1.2em"
                                           />
                                           <Text 
                                             as={item.isFolder ? 'button' : 'span'}
                                             onClick={item.isFolder ? () => handleItemClick(item) : undefined}
                                             cursor={item.isFolder ? 'pointer' : 'default'}
                                             _hover={item.isFolder ? { textDecoration: 'underline' } : {}}
                                             fontSize="sm" // Use sm size
                                             title={item.name || 'Unnamed Item'}
                                             maxWidth="500px" 
                                             overflow="hidden"
                                             textOverflow="ellipsis"
                                             whiteSpace="nowrap"
                                           >
                                             {item.name || 'Unnamed Item'}
                                           </Text>
                                         </HStack>
                                       </Td>
                                       <Td whiteSpace="nowrap" py={2} fontSize="sm">{formatDateTime(item.lastModifiedDateTime)}</Td> {/* Use sm size */}
                                       <Td whiteSpace="nowrap" py={2} isNumeric fontSize="sm">{formatFileSize(item.size)}</Td> {/* Use sm size */}
                                       <Td py={2}>
                                         {item.isFile && (
                                           <IconButton
                                             icon={<Icon as={FaCloudDownloadAlt} />} 
                                             aria-label={t('sharepoint.downloadFile')}
                                             size="xs"
                                             variant="ghost"
                                             onClick={() => handleDownloadClick(item)}
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
                               <Text color="gray.500">
                                 {searchPerformed ? t('sharepoint.noSearchResults') : t('sharepoint.emptyFolder')}
                               </Text>
                             </Center>
                           )}
                        </Box>
                      </>
                    )}
                  </VStack>
                )}
              </VStack>
            </TabPanel>
            <TabPanel p={0}>
              <QuickAccessList />
            </TabPanel>
            <TabPanel p={0}>
              <MyRecentFilesList />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Container>
  );
};

export default SharePointPage; 