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
  Progress
} from '@chakra-ui/react';
import { FaFolder, FaFile, FaSearch, FaCloudDownloadAlt, FaDatabase, FaGlobeEurope } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import apiClient from '../api/apiClient'; // Changed to default import
import { getTaskStatus } from '../api/tasks'; // Import task API
import { TaskStatusEnum, TaskStatus as TaskStatusInterface } from '../models/tasks'; // Import enum and interface

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
      setDrives(response.data || []);
      console.log(`[SP Page] Fetched ${response.data?.length || 0} drives.`);
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
  const handleSiteChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const siteId = event.target.value;
    console.log(`[SP Page] Site selected: ${siteId}`);
    setSelectedSite(siteId);
    // Trigger fetchDrives when site changes
    fetchDrives(siteId);
  };

  const handleDriveChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const driveId = event.target.value;
    console.log(`[SP Page] Drive selected: ${driveId}`);
    setSelectedDrive(driveId);
    // Trigger fetchItems for the root when drive changes
    fetchItems(driveId, null); 
    // Reset breadcrumbs when drive changes
    setCurrentBreadcrumbs([]);
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

  // Effects
  useEffect(() => {
    fetchSites();
  }, [fetchSites]); // Depend on the memoized callback

  // Rendering Helpers
  const renderBreadcrumbs = () => {
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
              {/* Show Drive icon if possible */} 
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
                  <Text fontWeight="bold">{t('sharepoint.searchResults')}</Text>
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
    // Show more precision for smaller files
    const precision = i < 2 ? 1 : 0; 
    return parseFloat((bytes / Math.pow(k, i)).toFixed(precision)) + ' ' + sizes[i];
  };

  // Combined Loading State
  const isAnythingLoading = isLoadingSites || isLoadingDrives || isLoadingItems || isSearching;

  // Main Return
  return (
    <Container maxW="1400px" py={4}>
      <VStack spacing={4} align="stretch">
        <Heading size="lg" mb={4}>{t('sharepoint.title')}</Heading>

        {/* Selection Area */} 
        <HStack spacing={4} mb={4} flexWrap="wrap">
          {/* Site Selection */} 
          <Select
            icon={isLoadingSites ? <Spinner size="xs" /> : undefined}
            placeholder={sites.length > 0 ? t('sharepoint.selectSite') : (isLoadingSites ? t('sharepoint.loadingSites') : t('sharepoint.noSitesFound'))}
            value={selectedSite}
            onChange={handleSiteChange}
            isDisabled={isLoadingSites || sites.length === 0}
            minW="250px"
            flexGrow={1}
          >
            {sites.map((site) => (
              <option key={site.id} value={site.id} title={site.webUrl}>
                {site.displayName} {site.name ? `(${site.name})` : ''}
              </option>
            ))}
          </Select>
          {/* Drive Selection */} 
          <Select
            icon={isLoadingDrives ? <Spinner size="xs" /> : undefined}
            placeholder={
                !selectedSite ? t('sharepoint.selectSiteFirst') : 
                (drives.length > 0 ? t('sharepoint.selectDrive') : 
                (isLoadingDrives ? t('sharepoint.loadingDrives') : t('sharepoint.noDrivesFound')))
            }
            value={selectedDrive}
            onChange={handleDriveChange}
            isDisabled={isAnythingLoading || !selectedSite}
            minW="250px"
            flexGrow={1}
          >
            {drives.map((drive) => (
              <option key={drive.id} value={drive.id} title={drive.webUrl}>
                {drive.name || 'Unnamed Drive'}
              </option>
            ))}
          </Select>
        </HStack>

        {/* Search and Breadcrumbs Area */} 
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
                    {renderBreadcrumbs()}
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

        {/* Task Progress Display (if task is running) */} 
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
            minHeight="300px" // Ensure minimum height
            position="relative" // For potential absolute positioning of overlays
        >
          {(isLoadingItems || isSearching) ? (
            <ItemTableSkeleton /> // Show skeleton loader
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
                    <VStack spacing={3} color="gray.500">
                        <Icon as={searchPerformed ? FaSearch : FaFolder} boxSize={8} />
                        <Text fontSize="lg" fontWeight="medium">
                            {searchPerformed ? t('sharepoint.noSearchResults') : t('sharepoint.emptyFolder')}
                        </Text>
                        {!searchPerformed && <Text fontSize="sm">{t('sharepoint.emptyFolderDesc')}</Text>} 
                    </VStack>
                </Center>
            )
          ) : (
            <Center py={8} minHeight="200px">
                <VStack spacing={3} color="gray.500">
                    <Icon as={FaGlobeEurope} boxSize={8} />
                    <Text fontSize="lg" fontWeight="medium">
                        {selectedSite ? t('sharepoint.selectDrivePrompt') : t('sharepoint.selectSitePrompt')}
                    </Text>
                    <Text fontSize="sm">
                        {selectedSite ? t('sharepoint.selectDriveDesc') : t('sharepoint.selectSiteDesc')}
                    </Text>
                </VStack>
            </Center>
          )}
        </Box>

      </VStack>
    </Container>
  );
};

export default SharePointPage; 