import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
import { FaFolder, FaFile, FaSearch, FaCloudDownloadAlt, FaDatabase, FaGlobeEurope, FaSort, FaSortUp, FaSortDown, FaCheckCircle, FaPlusCircle } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import apiClient from '../api/apiClient'; // Changed to default import
import { getTaskStatus } from '../api/tasks'; // Import task API
import { TaskStatusEnum, TaskStatus as TaskStatusInterface } from '../models/tasks'; // Import enum and interface
import QuickAccessList from '../components/QuickAccessList'; // <-- Import the new component
import MyRecentFilesList from '../components/MyRecentFilesList'; // Import the new component
import SyncListComponent from '../components/SyncListComponent'; // <-- Import the new component
import {
  SharePointSite, 
  SharePointDrive, 
  SharePointItem, 
  SharePointSyncItem, 
  SharePointSyncItemCreate,
  RecentDriveItem,
  UsedInsight
} from '../models/sharepoint';

// Define allowed file extensions (lowercase)
const ALLOWED_FILE_EXTENSIONS = [
  '.docx', '.pdf', '.pptx', '.txt', '.xlsx', '.doc', '.ppt', '.xls', '.csv'
];

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

// --- A-Z Index Component ---
const AlphabetIndex = ({ 
    selectedLetterFilter, 
    handleLetterFilterClick, 
    availableLetters, 
    t 
}: {
    selectedLetterFilter: string | null;
    handleLetterFilterClick: (letter: string | null) => void;
    availableLetters: string[];
    t: (key: string) => string;
}) => (
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

// +++ Restore formatDateTime and formatFileSize +++
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
// +++ End Restore +++

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

  // +++ State for Sync List Feature (MOVED HERE) +++
  const [syncList, setSyncList] = useState<SharePointSyncItem[]>([]);
  const [isSyncListLoading, setIsSyncListLoading] = useState(false);
  const [syncListError, setSyncListError] = useState<string | null>(null);
  const [processingTaskId, setProcessingTaskId] = useState<string | null>(null);
  const [processingTaskStatus, setProcessingTaskStatus] = useState<TaskStatusInterface | null>(null);
  const [isProcessing, setIsProcessing] = useState(false); // Tracks if the *submission* is happening or polling is active
  const [processingError, setProcessingError] = useState<string | null>(null);
  const syncPollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  // +++ End Sync List State +++

  // +++ Add History State +++
  const [historyItems, setHistoryItems] = useState<SharePointSyncItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  // +++ End History State +++

  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');
  const tableBg = useColorModeValue('white', 'gray.800'); // Assuming gray.800 is preferred
  const hoverBg = useColorModeValue('gray.50', 'whiteAlpha.100');
  const scrollbarThumbBg = useColorModeValue('gray.300', 'gray.600'); // Moved from JSX
  const searchInputBg = useColorModeValue('white', 'gray.700'); // Moved from JSX

  // --- Legacy Polling Functions (Renamed for Clarity) --- 
  const stopDownloadPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      console.log('[SP Download Polling] Stopping polling interval.');
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  const pollDownloadTaskStatus = useCallback(async (taskId: string) => {
    console.log(`[SP Download Polling] Checking status for task ${taskId}...`);
    try {
      const statusResult: TaskStatusInterface = await getTaskStatus(taskId);
      console.log(`[SP Download Polling] Status received:`, statusResult);
      
      setTaskStatus(statusResult.status);
      setTaskProgress(statusResult.progress ?? taskProgress);
      setTaskDetails(statusResult.message ?? statusResult.details ?? 'No details provided.');

      const finalStates: string[] = [TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED, 'SUCCESS', 'FAILURE'];
      if (finalStates.includes(statusResult.status)) {
        console.log(`[SP Download Polling] Task ${taskId} reached final state: ${statusResult.status}. Stopping polling.`);
        stopDownloadPolling();
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
      console.error(`[SP Download Polling] Error fetching status for task ${taskId}:`, error);
      setTaskStatus(TaskStatusEnum.POLLING_ERROR);
      setTaskDetails(`Error polling status: ${error.message}`);
      stopDownloadPolling(); 
      setIsDownloadTaskRunning(false); 
      setActiveTaskId(null);
       toast({ title: t('errors.errorPollingStatus'), description: error.message, status: 'error', duration: 7000 });
    }
  }, [stopDownloadPolling, toast, t, taskProgress]); // Removed getTaskStatus from here, it's stable

  const startDownloadPolling = useCallback((taskId: string) => {
    stopDownloadPolling(); 
    console.log(`[SP Download Polling] Starting polling for task ${taskId}...`);
    setActiveTaskId(taskId);
    setIsDownloadTaskRunning(true);
    setTaskStatus(TaskStatusEnum.PENDING);
    setTaskProgress(0);
    setTaskDetails('Task submitted, waiting for worker...');
    pollDownloadTaskStatus(taskId);
    pollingIntervalRef.current = setInterval(() => pollDownloadTaskStatus(taskId), 3000); 
  }, [stopDownloadPolling, pollDownloadTaskStatus]);
  // --- End Download Polling Functions --- 

  // --- NEW SYNC POLLING FUNCTIONS --- 
  const stopSyncPolling = useCallback(() => {
    if (syncPollingIntervalRef.current) {
      console.log('[SP Sync Polling] Stopping polling.');
      clearInterval(syncPollingIntervalRef.current);
      syncPollingIntervalRef.current = null;
    }
  }, []);

  const pollSyncTaskStatus = useCallback(async (taskId: string) => {
    if (!taskId) return;
    console.log(`[SP Sync Polling] Checking status for task ${taskId}...`);
    try {
      // Use the imported getTaskStatus function
      const statusResult: TaskStatusInterface = await getTaskStatus(taskId); 
      console.log('[SP Sync Polling] Status received:', statusResult);
      setProcessingTaskStatus(statusResult);
      setProcessingError(null);
      
      // Check if the task has reached a final state
      const finalStates: string[] = [
        TaskStatusEnum.COMPLETED, 
        TaskStatusEnum.FAILED, 
        'SUCCESS', // Include potentially legacy statuses 
        'FAILURE' 
      ];
      if (finalStates.includes(statusResult.status)) {
        console.log(`[SP Sync Polling] Task ${taskId} reached final state: ${statusResult.status}. Stopping.`);
        stopSyncPolling();
        setIsProcessing(false); // Polling finished, processing is no longer active
        // Keep processingTaskId for potential display or retry?
        // setProcessingTaskId(null); // Optional: Clear task ID once finished
        
        const isSuccess = statusResult.status === TaskStatusEnum.COMPLETED || statusResult.status === 'SUCCESS';
        // Check for partial failure based on backend message/result if status is FAILED
        const isPartial = statusResult.status === TaskStatusEnum.FAILED && statusResult.result && typeof statusResult.result === 'object'; 
        let toastStatus: 'success' | 'error' | 'warning' = isSuccess ? 'success' : (isPartial ? 'warning' : 'error');
        let toastTitle = isSuccess ? t('sharepoint.syncCompleteTitle') : (isPartial ? t('sharepoint.syncPartialFailureTitle') : t('sharepoint.syncFailedTitle'));
        let toastDescription = statusResult.message || statusResult.result?.message || (isSuccess ? t('sharepoint.syncCompleteDesc') : (isPartial ? t('sharepoint.syncPartialFailureDesc') : t('sharepoint.syncFailedDesc')));

        toast({ title: toastTitle, description: toastDescription, status: toastStatus, duration: 9000, isClosable: true });
      }
    } catch (error: any) {
      console.error(`[SP Sync Polling] Error fetching status for task ${taskId}:`, error);
      const errorMsg = `Polling failed: ${error.message}`;
      setProcessingError(errorMsg);
      // Update status to reflect polling error, keeping existing data if possible
      setProcessingTaskStatus(prev => prev ? { ...prev, status: TaskStatusEnum.POLLING_ERROR } : { task_id: taskId, status: TaskStatusEnum.POLLING_ERROR, progress: null, message: errorMsg });
      stopSyncPolling();
      setIsProcessing(false); // Polling stopped due to error
      toast({ title: t('errors.errorPollingStatus'), description: error.message, status: 'error' });
    }
  }, [stopSyncPolling, t, toast, setProcessingTaskStatus, setProcessingError, setIsProcessing]); // Add dependencies

  const startSyncPolling = useCallback((taskId: string) => {
    stopSyncPolling(); // Ensure any previous polling is stopped
    console.log(`[SP Sync Polling] Starting polling for task ${taskId}...`);
    setProcessingTaskId(taskId);
    setIsProcessing(true); // Mark processing as active during polling
    setProcessingError(null);
    // Set initial status while waiting for the first poll result
    setProcessingTaskStatus({ task_id: taskId, status: TaskStatusEnum.PENDING, progress: 0, message: 'Sync task submitted, starting...' }); 
    pollSyncTaskStatus(taskId); // Poll immediately
    syncPollingIntervalRef.current = setInterval(() => pollSyncTaskStatus(taskId), 5000); // Poll every 5 seconds
  }, [stopSyncPolling, pollSyncTaskStatus, setProcessingTaskId, setIsProcessing, setProcessingError, setProcessingTaskStatus]);
  // --- END NEW SYNC POLLING FUNCTIONS ---

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
    stopDownloadPolling(); // Use renamed function
    setIsDownloadTaskRunning(false);
    setActiveTaskId(null);
    setTaskStatus(null);
    setTaskProgress(null);
    setTaskDetails(null);
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
  }, [t, toast, stopDownloadPolling]);

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
      const fetchedItems = response.data || []; // Store data
      // ADD THIS LOG: Check the keys of the first file-like item found
      const firstFile = fetchedItems.find((item: any) => item.name?.includes('.')); // Heuristic to find a file
      if (firstFile) {
          console.log('[SP Page] Keys of first fetched file-like item:', Object.keys(firstFile));
      } else {
          console.log('[SP Page] No file-like items found in fetchItems response to check keys.');
      }
      setItems(fetchedItems);
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
    stopDownloadPolling(); 
    setIsDownloadTaskRunning(false);
    setActiveTaskId(null);
    setTaskStatus(null);
    setTaskProgress(null);
    setTaskDetails(null);
    fetchDrives(siteId);
  }, [fetchDrives, isLoadingSites, isLoadingDrives, selectedSite, stopDownloadPolling]);

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
    if (item.is_folder) {
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
    setBrowseSortDirection('asc');
  }, [fetchItems, isLoadingItems, isSearching, selectedDrive, currentBreadcrumbs]);

  const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      searchDrive(selectedDrive, searchQuery);
    }
  };

  const handleDownloadClick = useCallback(async (item: SharePointItem) => {
    if (!item.is_file || !selectedDrive) return;
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
          startDownloadPolling(response.data.task_id); // Use renamed function
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
  }, [selectedDrive, isDownloadTaskRunning, t, toast, startDownloadPolling]);

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

  // --- Sorting logic ---
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
             if (a.is_folder && !b.is_folder) return -1;
             if (!a.is_folder && b.is_folder) return 1;
         }
         comparison = strA.localeCompare(strB);
      }
     
      return browseSortDirection === 'asc' ? comparison : comparison * -1;
    });

    return processedItems;
  }, [items, browseSortBy, browseSortDirection, selectedLetterFilter]);
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
    // Cleanup polling intervals on unmount
    return () => {
        stopDownloadPolling(); // Use renamed function
        stopSyncPolling();     // Add sync polling cleanup
    }
  }, [stopDownloadPolling, stopSyncPolling]); // Add dependencies

  // +++ SYNC LIST HANDLERS +++ (AFTER POLLING FUNCTIONS)
  const handleAddSyncItem = useCallback(async (item: SharePointItem) => {
    if (!selectedDrive) {
      console.error("[SP Page] Cannot add item: No drive selected.");
      toast({ title: t('errors.error'), description: t('sharepoint.errors.noDriveSelected'), status: 'warning' });
      return;
    }
    if (syncList.some(syncItem => syncItem.sharepoint_item_id === item.id)) {
        toast({ title: t('sharepoint.alreadyInSyncList'), status: 'info', duration: 2000});
        return;
    }
    const itemData: SharePointSyncItemCreate = {
      item_type: item.is_folder ? 'folder' : 'file',
      sharepoint_item_id: item.id,
      sharepoint_drive_id: selectedDrive,
      item_name: item.name || 'Unnamed Item'
    };
    try {
      console.log(`[SP Page] Adding item ${item.id} to sync list...`);
      const addedItem = await apiClient.post('/sharepoint/sync-list/add', itemData).then(res => res.data);
      setSyncList(prev => [...prev.filter(i => i.sharepoint_item_id !== item.id), addedItem]);
      toast({ title: t('sharepoint.itemAddedToSync', { name: item.name }), status: 'success', duration: 2000 });
    } catch (error: any) {
      console.error(`[SP Page] Error adding item ${item.id} to sync list:`, error);
      toast({ title: t('errors.errorAddingItem'), description: error.response?.data?.detail || error.message || t('errors.unknown'), status: 'error' });
    }
  }, [selectedDrive, t, toast, syncList, apiClient, setSyncList]);

  const handleRemoveSyncItem = useCallback(async (sharepointItemId: string) => {
    const itemToRemove = syncList.find(i => i.sharepoint_item_id === sharepointItemId);
    if (!itemToRemove) return;
    try {
      console.log(`[SP Page] Removing item ${sharepointItemId} from sync list...`);
      await apiClient.delete(`/sharepoint/sync-list/remove/${sharepointItemId}`);
      setSyncList(prev => prev.filter(i => i.sharepoint_item_id !== sharepointItemId));
      toast({ title: t('sharepoint.itemRemovedFromSync', { name: itemToRemove.item_name }), status: 'info', duration: 2000 });
    } catch (error: any) {
      console.error(`[SP Page] Error removing item ${sharepointItemId}:`, error);
      toast({ title: t('errors.errorRemovingItem'), description: error.response?.data?.detail || error.message || t('errors.unknown'), status: 'error' });
    }
  }, [syncList, t, toast, apiClient, setSyncList]);

  const handleProcessSyncList = useCallback(async () => {
    if (syncList.length === 0) {
      toast({ title: t('sharepoint.syncListEmptyTitle'), description: t('sharepoint.syncListEmptyDesc'), status: 'warning' });
      return;
    }
    if (isProcessing) {
       toast({ title: t('sharepoint.syncAlreadyInProgress'), status: 'info' });
       return;
    }
    console.log("[SP Page] Initiating sync list processing...");
    setIsProcessing(true);
    setProcessingError(null);
    setProcessingTaskStatus(null);
    setProcessingTaskId(null); 
    try {
      const result = await apiClient.post('/sharepoint/sync-list/process').then(res => res.data);
      const newTaskId = result.task_id;
      setProcessingTaskId(newTaskId);
      setSyncList([]); 
      // Remove initial status set here, startSyncPolling will handle it
      // setProcessingTaskStatus({ task_id: newTaskId, status: TaskStatusEnum.SUBMITTING }); 
      toast({ title: t('sharepoint.syncProcessStartedTitle'), description: t('sharepoint.syncProcessStartedDesc', { taskId: newTaskId }), status: 'info' });
      startSyncPolling(newTaskId); // Start polling the sync task
    } catch (error: any) {
      console.error("[SP Page] Error submitting sync list for processing:", error);
      const errorMsg = error.response?.data?.detail || error.message || t('sharepoint.errors.processSyncListError');
      setProcessingError(errorMsg);
      setIsProcessing(false);
      setProcessingTaskStatus({ task_id: 'error', status: TaskStatusEnum.FAILED_SUBMISSION });
      toast({ title: t('errors.error'), description: errorMsg, status: 'error' });
    }
    // Dependencies include polling functions which are now defined above
  }, [syncList, isProcessing, t, toast, startSyncPolling, apiClient, setSyncList, setIsProcessing, setProcessingError, setProcessingTaskStatus, setProcessingTaskId]); // Removed stop/poll from here, use startSyncPolling
  // +++ END SYNC LIST HANDLERS +++

  // +++ ADD BACK Helper Function for Action Button +++
  const renderSyncActionButton = (item: SharePointItem, syncList: SharePointSyncItem[], isProcessing: boolean, handleAddSyncItem: (item: SharePointItem) => void, t: (key: string) => string) => {
    // Check if the current item is in the sync list
    const isInSyncList = syncList.some((syncItem: SharePointSyncItem) => syncItem.sharepoint_item_id === item.id);

    let canAddItem = false;
    if (item.is_folder) {
        // Always allow adding folders
        canAddItem = true;
    } else if (item.is_file && item.name) {
        // Check file extension if it's a file
        const fileNameLower = item.name.toLowerCase();
        const lastDotIndex = fileNameLower.lastIndexOf('.');
        if (lastDotIndex !== -1) { // Ensure there is an extension
          const fileExtension = fileNameLower.substring(lastDotIndex);
          if (ALLOWED_FILE_EXTENSIONS.includes(fileExtension)) {
              canAddItem = true;
          }
        } 
    }

    // Render button only if the item type is allowed
    if (canAddItem) {
      return (
        <IconButton
          aria-label={isInSyncList ? t('sharepoint.alreadyInSyncList') : t('sharepoint.addToSyncList')}
          icon={isInSyncList ? <FaCheckCircle color="green"/> : <FaPlusCircle />}
          size="sm"
          variant="ghost"
          color={isInSyncList ? "green.500" : "blue.500"} 
          onClick={() => !isInSyncList && handleAddSyncItem(item)} 
          isDisabled={isProcessing || isInSyncList} 
          title={isInSyncList ? t('sharepoint.alreadyInSyncList') : t('sharepoint.addToSyncList')}
        />
      );
    } 

    return null; // Don't render button for unsupported file types
  };
  // +++ END Helper Function +++

  // --- Effect to auto-select site if filter results in one ---
  useEffect(() => {
    // This calculation might already exist via useMemo, adjust if needed
    const currentlyFilteredSites = selectedLetterFilter
      ? sites.filter(site => site.displayName?.toUpperCase().startsWith(selectedLetterFilter))
      : sites;

    // Check if filter is active, resulted in one site, and no site is currently selected
    if (currentlyFilteredSites.length === 1 && selectedLetterFilter !== null && !selectedSite) {
      console.log(`[Auto-Select] Filter resulted in one site (${currentlyFilteredSites[0].displayName}), selecting it.`);
      if (typeof handleSiteSelect === 'function') {
          handleSiteSelect(currentlyFilteredSites[0].id);
      } else {
          console.error("[Auto-Select] handleSiteSelect function not found or not ready.");
      }
    }
  // Dependencies need careful review based on actual implementation
  }, [sites, selectedLetterFilter, selectedSite, handleSiteSelect]);

  // +++ Add History Fetch Function +++
  const fetchHistory = useCallback(async () => {
      console.log('[SP History] Fetching completed items...');
      setIsLoadingHistory(true);
      setHistoryError(null);
      try {
          // Ensure apiClient is correctly imported and configured
          const response = await apiClient.get<SharePointSyncItem[]>('/sharepoint/sync-history');
          setHistoryItems(response.data || []); // Default to empty array if data is null/undefined
          console.log(`[SP History] Fetched ${response.data?.length || 0} items.`);
      } catch (error: any) {
          console.error('[SP History] Error fetching history:', error);
          const errorMsg = error.response?.data?.detail || error.message || 'Failed to load history';
          setHistoryError(errorMsg);
          toast({
              title: t('errors.errorLoadingHistory'), // Need translation key
              description: errorMsg,
              status: 'error',
              duration: 5000,
              isClosable: true,
          });
      } finally {
          setIsLoadingHistory(false);
      }
  }, [t, toast, apiClient]); // Add apiClient if it's a dependency, adjust others as needed
  // +++ End History Fetch Function +++

  // Main Return
  return (
    <Container maxW="container.xl" py={5}>
      <VStack spacing={5} align="stretch">
        <Heading size="lg" textAlign={{ base: 'center', md: 'left' }}>{t('sharepoint.title')}</Heading>

        <Tabs variant="soft-rounded" colorScheme="blue" isLazy onChange={(index) => {
          if (index === 3) {
            fetchHistory();
          }
        }}>
          <TabList mb="1em">
            <Tab>{t('sharepoint.tabs.browseSites')}</Tab>
            <Tab>{t('sharepoint.tabs.quickAccess')}</Tab>
            <Tab>{t('sharepoint.tabs.myRecent')}</Tab>
            <Tab>{t('sharepoint.tabs.history')}</Tab>
          </TabList>
          <TabPanels>
            <TabPanel p={0}>
              <VStack spacing={6} align="stretch">
                <Box>
                <Text fontSize="lg" mb={2} textAlign="center">{t('sharepoint.selectSitePlaceholder')}</Text>
                  <AlphabetIndex 
                    selectedLetterFilter={selectedLetterFilter}
                    handleLetterFilterClick={handleLetterFilterClick}
                    availableLetters={availableLetters}
                    t={t}
                  />
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
                                      background: scrollbarThumbBg,
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
                                        title={`${drive.name || t('common.unnamedDrive', 'Unnamed Drive')}\n${t('common.type', 'Type')}: ${drive.driveType || t('common.notApplicable', 'N/A')}\n${drive.webUrl}`}
                                    >
                                        <Text fontWeight="medium" fontSize="sm" noOfLines={2}>{drive.name || t('common.unnamedDrive', 'Unnamed Drive')}</Text>
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
                                bg={searchInputBg}
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
                           {isLoadingItems || isSearching ? (
                               <ItemTableSkeleton />
                           ) : (
                               <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
                                 <Table variant="simple" bg={tableBg}>
                                   <Thead>
                                     <Tr>
                                       <Th 
                                         onClick={() => handleBrowseSort('name')} 
                                         cursor="pointer"
                                         _hover={{ bg: hoverBg }}
                                       >{t('common.name')} <BrowseSortIcon column="name" /></Th>
                                       <Th 
                                         onClick={() => handleBrowseSort('lastModifiedDateTime')} 
                                         cursor="pointer"
                                         _hover={{ bg: hoverBg }}
                                       >{t('common.modified')} <BrowseSortIcon column="lastModifiedDateTime" /></Th>
                                       <Th 
                                         isNumeric 
                                         onClick={() => handleBrowseSort('size')} 
                                         cursor="pointer"
                                         _hover={{ bg: hoverBg }}
                                       >{t('common.size')} <BrowseSortIcon column="size" /></Th>
                                       <Th>{t('common.modifiedBy')}</Th>
                                       <Th>{t('common.modified')}</Th>
                                       <Th>{t('common.actionsHeader')}</Th>{/* Action column */}
                                     </Tr>
                                   </Thead>
                                   <Tbody>
                                     {sortedAndFilteredItems.length > 0 ? (
                                       sortedAndFilteredItems.map((item: SharePointItem) => (
                                         <Tr key={item.id} _hover={{ bg: hoverBg }}>
                                           <Td 
                                             onClick={() => item.is_folder && handleItemClick(item)} 
                                             cursor={item.is_folder ? 'pointer' : 'default'}
                                             title={item.name}
                                           >
                                             <HStack>
                                               <Icon 
                                                 as={item.is_folder ? FaFolder : FaFile} 
                                                 color={item.is_folder ? folderColor : fileColor}
                                                 w={4} h={4}
                                               />
                                               <Text noOfLines={1}>{item.name || '-'}</Text>
                                             </HStack>
                                           </Td>
                                           <Td>{formatDateTime(item.lastModifiedDateTime)}</Td>
                                           <Td isNumeric>{formatFileSize(item.size)}</Td>
                                           <Td>
                                             {renderSyncActionButton(item, syncList, isProcessing, handleAddSyncItem, t)}
                                           </Td>
                                         </Tr>
                                       ))
                                     ) : (
                                       <Tr>
                                         <Td colSpan={4} textAlign="center">{searchPerformed ? t('common.noResultsFound') : t('sharepoint.noItemsFound')}</Td>
                                       </Tr>
                                     )}
                                   </Tbody>
                                 </Table>
                               </Box>
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
            <TabPanel p={0}>
              <VStack spacing={4} align="stretch">
                  <Heading size="md">{t('sharepoint.history.title')}</Heading>
                  {isLoadingHistory && <Center><Spinner /></Center>}
                  {historyError && <Text color="red.500">{historyError}</Text>}
                  {!isLoadingHistory && !historyError && (
                      historyItems.length === 0
                      ? (<Text>{t('sharepoint.history.empty')}</Text>)
                      : (
                          <Box overflowY="auto" maxHeight="400px">
                              <Table variant="simple" size="sm" bg={tableBg}>
                                  <Thead>
                                      <Tr>
                                          <Th>{t('common.name')}</Th>
                                          <Th>{t('common.type')}</Th>
                                      </Tr>
                                  </Thead>
                                  <Tbody>
                                      {historyItems.map((item) => (
                                          <Tr key={item.id} _hover={{ bg: hoverBg }}>
                                              <Td>
                                                  <HStack>
                                                      <Icon
                                                          as={item.item_type === 'folder' ? FaFolder : FaFile}
                                                          color={item.item_type === 'folder' ? folderColor : fileColor}
                                                      />
                                                      <Text>{item.item_name}</Text>
                                                  </HStack>
                                              </Td>
                                              <Td>{t(`sharepoint.itemType.${item.item_type}`)}</Td>
                                          </Tr>
                                      ))}
                                  </Tbody>
                              </Table>
                          </Box>
                      )
                  )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* +++ Render the Sync List Component +++ */}
        <Box mt={6}> {/* Add some margin top */} 
          <SyncListComponent 
            items={syncList} 
            onRemoveItem={handleRemoveSyncItem}
            onProcessList={handleProcessSyncList}
            isProcessing={isProcessing}
            isLoading={isSyncListLoading}
            error={syncListError}
          />
        </Box>
        {/* +++ End Sync List Component Rendering +++ */}

        {/* +++ NEW: Sync Task Progress Display +++ */}
        {(isProcessing || processingTaskStatus) && processingTaskId && (
          <Box 
            mt={4} p={4} borderWidth="1px" borderRadius="md" 
            borderColor={
              processingTaskStatus?.status === TaskStatusEnum.FAILED || 
              processingTaskStatus?.status === TaskStatusEnum.FAILED_SUBMISSION
                ? "red.300" 
                : (processingTaskStatus?.status === TaskStatusEnum.COMPLETED ? "green.300" : "blue.300")
            } 
            bg={useColorModeValue(
              processingTaskStatus?.status === TaskStatusEnum.FAILED || 
              processingTaskStatus?.status === TaskStatusEnum.FAILED_SUBMISSION
                ? "red.50" 
                : (processingTaskStatus?.status === TaskStatusEnum.COMPLETED ? "green.50" : "blue.50"),
              processingTaskStatus?.status === TaskStatusEnum.FAILED || 
              processingTaskStatus?.status === TaskStatusEnum.FAILED_SUBMISSION
                ? "red.900" 
                : (processingTaskStatus?.status === TaskStatusEnum.COMPLETED ? "green.900" : "blue.900")
            )}
            mb={4}
          >
              <VStack spacing={2} align="stretch">
                <HStack justify="space-between">
                  <Text fontSize="sm" fontWeight="bold">{t('sharepoint.syncTaskProgressTitle')}</Text>
                  <Tag 
                      size="sm"
                      colorScheme={
                        processingTaskStatus?.status === TaskStatusEnum.COMPLETED ? 'green' :
                        processingTaskStatus?.status === TaskStatusEnum.FAILED || 
                        processingTaskStatus?.status === TaskStatusEnum.FAILED_SUBMISSION ? 'red' : 
                        processingTaskStatus?.status === TaskStatusEnum.POLLING_ERROR ? 'gray' :
                        'blue'
                      }
                    >
                      {processingTaskStatus?.status || 'Initializing...'}
                    </Tag>
                </HStack>
                <Text fontSize="xs">{t('common.taskID')} {processingTaskId}</Text>
                {typeof processingTaskStatus?.progress === 'number' && (
                  <Progress 
                    value={processingTaskStatus.progress} size="xs" 
                    colorScheme={
                      processingTaskStatus?.status === TaskStatusEnum.FAILED || 
                      processingTaskStatus?.status === TaskStatusEnum.FAILED_SUBMISSION ? 'red' : 
                      (processingTaskStatus?.status === TaskStatusEnum.COMPLETED ? 'green' : 'blue')
                    } 
                    isAnimated={processingTaskStatus?.status === TaskStatusEnum.RUNNING || processingTaskStatus?.status === TaskStatusEnum.PENDING}
                    hasStripe={processingTaskStatus?.status === TaskStatusEnum.RUNNING || processingTaskStatus?.status === TaskStatusEnum.PENDING}
                    borderRadius="full"
                  />
                )}
                {(processingTaskStatus?.message || processingError) && (
                    <Text fontSize="xs" color={processingError ? "red.500" : "gray.500"} mt={1} noOfLines={2} title={processingError || processingTaskStatus?.message || undefined}>
                      {processingError || processingTaskStatus?.message}
                    </Text>
                )}
                 {/* Display results if available (e.g., partial failure details) */} 
                 {processingTaskStatus?.result && typeof processingTaskStatus.result === 'object' && (
                     <Text fontSize="xs" color="orange.500" mt={1}>
                         Details: {JSON.stringify(processingTaskStatus.result)}
                     </Text>
                 )}
              </VStack>
          </Box>
        )}
        {/* +++ END Sync Task Progress Display +++ */}

      </VStack>
    </Container>
  );
};

export default SharePointPage; 