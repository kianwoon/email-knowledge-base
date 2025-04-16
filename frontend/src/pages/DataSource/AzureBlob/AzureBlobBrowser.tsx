import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box, Heading, Select, Button, Icon, // Basic Chakra components
    Table, Thead, Tbody, Tr, Th, Td, TableContainer, // Chakra Table
    Breadcrumb, BreadcrumbItem, BreadcrumbLink, // Chakra Breadcrumb
    VStack, HStack, Stack, // Chakra Layout
    Alert, AlertIcon, Spinner, Center, Text, Tag, // Chakra Feedback & Text
    List, ListItem, // Chakra List
    Tabs, TabList, Tab, TabPanels, TabPanel, // Chakra Tabs
    FormControl, FormLabel, FormErrorMessage, // Chakra Form (if needed for Settings later)
    IconButton, // Chakra IconButton
    useColorModeValue, // Hook for colors
    useToast, // Hook for notifications
    Progress, // Add Progress for polling display
    Tooltip // <<< Add Tooltip import
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FaFolder, FaFileAlt, FaSync, FaPlusCircle, FaTrashAlt, FaCheckCircle, FaExclamationTriangle, FaCloud } from 'react-icons/fa'; // Keep react-icons
import { ChevronRightIcon, AddIcon, CheckCircleIcon, DeleteIcon, SearchIcon, RepeatIcon } from '@chakra-ui/icons'; // Chakra icons

import apiClient from '../../../api/apiClient';
import axios from 'axios';

// Import from the new azure api file
import {
    getAzureConnections, listAzureContainers, listAzureBlobs,
    getAzureSyncList, addAzureSyncItem, removeAzureSyncItem, triggerAzureIngestion,
    AzureConnection, AzureContainer, AzureBlob, AzureSyncItem, AzureSyncItemCreate, TriggerIngestResponse
} from '../../../api/azure'; 
import { getTaskStatus } from '../../../api/tasks'; // Assuming tasks API is separate
import { TaskStatus, TaskStatusEnum } from '../../../models/tasks';
import AzureConnectionManager from './AzureConnectionManager';

// --- API Interface Definitions --- 
// Now imported from ../../../api/azure.ts
// interface AzureConnection { ... }
// interface AzureContainer { ... }
// interface AzureBlob { ... }
// interface AzureSyncItem { ... }

// --- API Functions (Keep as is, using apiClient) ---
// Now imported from ../../../api/azure.ts
// const getAzureConnections = async (): Promise<AzureConnection[]> => { /* ... */ };
// const listAzureContainers = async (connectionId: string): Promise<AzureContainer[]> => { /* ... */ };
// const listAzureBlobs = async (connectionId: string, containerName: string, prefix: string = ''): Promise<AzureBlob[]> => { /* ... */ };
// const addAzureSyncItem = async (item: Omit<AzureSyncItem, 'id' | 'status'>): Promise<AzureSyncItem> => { /* ... */ };
// const getAzureSyncList = async (): Promise<AzureSyncItem[]> => { /* ... */ };
// const removeAzureSyncItem = async (itemId: number): Promise<void> => { /* ... */ };
// const triggerAzureIngestion = async (): Promise<{ task_id: string }> => { /* ... */ };

// --- Helper Functions (Keep as is) ---
const formatFileSize = (bytes?: number | null): string => {
    if (bytes === undefined || bytes === null) return '-';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const dm = 2;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

const formatDateTime = (dateString?: string | null): string => {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        // Example format: 4/13/2025, 9:46:25 PM (adjust options as needed)
        return date.toLocaleString(undefined, {
            year: 'numeric', 
            month: 'numeric', 
            day: 'numeric', 
            hour: 'numeric', 
            minute: '2-digit', 
            second: '2-digit' 
        });
    } catch (e) {
        return 'Invalid Date';
    }
};

// --- Component ---

// +++ NEW History List Component +++
interface HistoryListComponentProps {
  items: AzureSyncItem[];
  isLoading: boolean;
  error: string | null;
  t: (key: string, options?: any) => string;
}

const AzureHistoryListComponent: React.FC<HistoryListComponentProps> = ({ 
  items, isLoading, error, t 
}) => {
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');

  const renderContent = () => {
    if (isLoading) {
      return <Center p={5}><Spinner /></Center>;
    }
    if (error) {
      return <Center p={5}><Text color="red.500" textAlign="center" width="100%">{t('azureBlobBrowser.errors.loadHistoryError', 'Error loading history')}: {error}</Text></Center>;
    }
    if (items.length === 0) {
      return <Center p={5}><Text color="gray.500" textAlign="center" width="100%">{t('azureBlobBrowser.historyEmpty', 'No processed items found in history.')}</Text></Center>;
    }
    return (
      <List spacing={3} p={2}>
        {items.map((item) => (
          <ListItem 
            key={item.id} 
            display="flex" 
            justifyContent="space-between" 
            alignItems="center"
            p={2}
            borderRadius="md"
            _hover={{ bg: hoverBg }}
          >
            <HStack spacing={2} flex={1} minWidth={0} width="100%"> 
              <Icon 
                as={item.item_type === 'prefix' ? FaFolder : FaFileAlt} 
                color={item.item_type === 'prefix' ? folderColor : fileColor}
                boxSize="1.2em"
                flexShrink={0}
              />
              <VStack align="start" spacing={0} flex={1} minWidth={0} width="100%"> 
                 <Text fontSize="sm" fontWeight="medium" noOfLines={1} title={item.item_path} width="100%" textAlign="left">
                  {item.item_name || item.item_path} 
                 </Text>
                 <Text fontSize="xs" color="gray.500" noOfLines={1} title={item.container_name} width="100%" textAlign="left">
                   Container: {item.container_name}
                 </Text>
              </VStack>
            </HStack>
            <Tag 
              size="sm" 
              variant="subtle" 
              colorScheme={item.status === 'completed' ? 'green' : 'red'}
              mr={2}
              flexShrink={0}
            >
               <Icon 
                 as={item.status === 'completed' ? FaCheckCircle : FaExclamationTriangle}
                 mr={1} 
               />
               {/* Use a generic status translation or add specific ones for Azure */}
               {t(`common.status.${item.status}`, item.status)} 
            </Tag>
          </ListItem>
        ))}
      </List>
    );
  };

  return (
    <Box mt={6} borderWidth="1px" borderRadius="lg" bg={bgColor} shadow="base">
      <VStack align="stretch">
        <HStack justify="space-between" p={4} borderBottomWidth="1px">
          <Heading size="md">{t('azureBlobBrowser.historyListTitle', 'Processing History')}</Heading>
        </HStack>
        <Box maxHeight="400px" overflowY="auto">
           {renderContent()}
        </Box>
      </VStack>
    </Box>
  );
};
// --- End History List Component ---

export default function AzureBlobBrowser() {
  const { t } = useTranslation();
  const toast = useToast(); // Use Chakra toast
  const [tabIndex, setTabIndex] = useState(0); // For Tabs

  // --- State Variables (Keep as is) ---
  const [connections, setConnections] = useState<AzureConnection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>('');
  const [containers, setContainers] = useState<AzureContainer[]>([]);
  const [selectedContainer, setSelectedContainer] = useState<string>('');
  const [blobs, setBlobs] = useState<AzureBlob[]>([]);
  const [currentPrefix, setCurrentPrefix] = useState<string>('');
  const [breadcrumbs, setBreadcrumbs] = useState<string[]>([]);
  const [syncList, setSyncList] = useState<AzureSyncItem[]>([]);
  // Loading states
  const [isLoadingConnections, setIsLoadingConnections] = useState(false);
  const [isLoadingContainers, setIsLoadingContainers] = useState(false);
  const [isLoadingBlobs, setIsLoadingBlobs] = useState(false);
  const [isLoadingSyncList, setIsLoadingSyncList] = useState(false);
  const [isProcessingSync, setIsProcessingSync] = useState(false);
  // Error states
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [containerError, setContainerError] = useState<string | null>(null);
  const [blobError, setBlobError] = useState<string | null>(null);
  const [syncListError, setSyncListError] = useState<string | null>(null);
  const [syncProcessError, setSyncProcessError] = useState<string | null>(null);
  // Polling State 
  const [ingestionTaskId, setIngestionTaskId] = useState<string | null>(null);
  const [isIngestionPolling, setIsIngestionPolling] = useState<boolean>(false);
  const [ingestionTaskStatus, setIngestionTaskStatus] = useState<TaskStatus | null>(null);
  const [ingestionError, setIngestionError] = useState<string | null>(null);
  const ingestionPollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // --- Color Mode Values (Chakra) ---
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const tableHeaderBg = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.700');
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');

  // --- useEffect Hooks (Keep logic, adapt error handling if needed) ---
  // Load connections
  const loadConnections = useCallback(async () => {
      console.log('[Azure Load Connections] Running. Current selectedConnectionId:', selectedConnectionId); // LOG BEFORE
      setIsLoadingConnections(true);
      setConnectionError(null);
      try {
          const data = await getAzureConnections();
          setConnections(data);
          // Auto-select if only one connection exists
          if (data && data.length === 1) {
              console.log(`[Azure Load Connections] Exactly one connection found ('${data[0].name}' / ${data[0].id}). Auto-selecting.`);
              // Check if it's different from the current selection to avoid unnecessary state updates/re-renders
              if (data[0].id !== selectedConnectionId) {
                  setSelectedConnectionId(data[0].id);
              }
          } else {
              // If multiple or zero connections, ensure the current selection is still valid
              const selectedExists = data.some(c => c.id === selectedConnectionId);
              console.log(`[Azure Load Connections] Fetched ${data.length} connections. Selected (${selectedConnectionId}) exists: ${selectedExists}`); // LOG CHECK
              if (selectedConnectionId && !selectedExists) {
                  console.log(`[Azure Load Connections] Resetting selectedConnectionId from ${selectedConnectionId} because it no longer exists.`); // LOG RESET
                  setSelectedConnectionId(''); // Reset if selected connection is gone
              }
          }
      } catch (error: any) {
          console.error("Failed to load Azure connections:", error);
          setConnectionError(t('errors.loadConnectionsFailed'));
          toast({ title: t('errors.error'), description: t('errors.loadConnectionsFailed'), status: 'error' });
      } finally {
          setIsLoadingConnections(false);
      }
  }, [t, toast, selectedConnectionId]);

  // Initial load for connections
  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  // Load containers
  useEffect(() => {
    if (!selectedConnectionId) { /* Reset state */ return; }
    const loadContainers = async () => {
        setIsLoadingContainers(true);
        setContainerError(null); /* Reset errors */
        setBlobError(null);
        setBlobs([]); /* Clear downstream data */
        setCurrentPrefix('');
        setBreadcrumbs([]);
        try {
            console.log(`[Azure Load Containers] Fetching containers for connection ID: ${selectedConnectionId}`); // LOG BEFORE API CALL
            const data = await listAzureContainers(selectedConnectionId);
            // Auto-select if only one container exists
            if (data && data.length === 1) {
                console.log(`[Azure Load Containers] Exactly one container found ('${data[0].name}'). Auto-selecting.`);
                setSelectedContainer(data[0].name);
            } else {
                 setSelectedContainer(''); // Reset selection if multiple or zero containers
            }
            setContainers(data);
        } catch (error: any) {
            console.error("Component Error: Failed to load containers:", error);
            setContainerError(error.message || t('azureBlobBrowser.errors.loadContainers', 'Failed to load containers.'));
        } finally {
            setIsLoadingContainers(false);
        }
    };
    loadContainers();
  }, [selectedConnectionId, t]);

  // Load blobs
  useEffect(() => {
    if (!selectedConnectionId || !selectedContainer) { /* Reset state */ return; }
    const loadBlobs = async () => {
        setIsLoadingBlobs(true);
        setBlobError(null);
        try {
            const data = await listAzureBlobs(selectedConnectionId, selectedContainer, currentPrefix);
            setBlobs(data);
        } catch (error: any) {
            console.error("Component Error: Failed to load blobs:", error);
            setBlobError(error.message || t('azureBlobBrowser.errors.loadBlobs', 'Failed to load blobs.'));
        } finally {
            setIsLoadingBlobs(false);
        }
    };
    loadBlobs();
  }, [selectedConnectionId, selectedContainer, currentPrefix, t]);

  // Update breadcrumbs
   useEffect(() => {
        if (!selectedContainer) {
            setBreadcrumbs([]);
        } else {
            const parts = currentPrefix.split('/').filter(part => part !== '');
            setBreadcrumbs([selectedContainer, ...parts]);
        }
    }, [selectedContainer, currentPrefix]);

   // Load sync list (using useCallback)
   const fetchSyncList = useCallback(async () => {
       setIsLoadingSyncList(true);
       setSyncListError(null);
       console.log(`[fetchSyncList] Running for TabIndex: ${tabIndex}, ConnectionId: ${selectedConnectionId}`);
       
       let itemsToFetch: AzureSyncItem[] = [];
       try {
           if (tabIndex === 1) { // History Tab
               console.log("[fetchSyncList] Fetching completed and error items for History tab (user-wide).");
               // Fetch both completed and error statuses without connection ID
               const completedItems = await getAzureSyncList(undefined, 'completed');
               const errorItems = await getAzureSyncList(undefined, 'error');
               itemsToFetch = [...completedItems, ...errorItems];
           } else if (tabIndex === 0 && selectedConnectionId) { // Browse & Sync Tab (and connection selected)
               // Fetch *ALL* items for the specific connection, regardless of status
               console.log(`[fetchSyncList] Fetching ALL sync items for connection: ${selectedConnectionId}`);
               itemsToFetch = await getAzureSyncList(selectedConnectionId, undefined); // Remove status filter
           } else {
               // If Browse tab but no connection, or other tabs, don't fetch.
               console.log("[fetchSyncList] Skipping fetch (Browse tab with no connection, or other tab).");
           }
           setSyncList(itemsToFetch);
       } catch (error: any) {
           console.error("Failed to fetch sync list:", error);
           const errorMessage = error?.response?.data?.detail || error?.message || t('errors.anErrorOccurred');
           setSyncListError(errorMessage);
           toast({ title: t('errors.error'), description: errorMessage, status: 'error' });
       } finally {
           setIsLoadingSyncList(false);
       }
   }, [selectedConnectionId, tabIndex, t, toast]); // Added toast dependency

  // useEffect to call fetchSyncList when relevant state changes
  useEffect(() => {
    // Fetch only when either:
    // 1. History tab is active (tabIndex 1)
    // 2. Browse tab is active (tabIndex 0) AND a connection is selected
    if (tabIndex === 1 || (tabIndex === 0 && selectedConnectionId)) {
        console.log(`[Sync List Fetch Trigger] Connection: ${selectedConnectionId}, TabIndex: ${tabIndex}. Fetching...`);
        fetchSyncList();
    } else {
        // Clear list if conditions aren't met (e.g., Browse tab with no connection, or Settings tab)
        console.log(`[Sync List Fetch Trigger] Conditions not met (Conn: ${selectedConnectionId}, Tab: ${tabIndex}). Clearing list.`);
        setSyncList([]);
    }
  }, [selectedConnectionId, tabIndex, fetchSyncList]); // Keep fetchSyncList dependency

  // --- Event Handlers (Keep logic, adapt types/toast) ---
  const handleConnectionChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newConnectionId = event.target.value;
    console.log(`[Azure Handle Connection Change] Setting selectedConnectionId to: ${newConnectionId}`); // LOG SET
    setSelectedConnectionId(newConnectionId);
    // Reset downstream state
    setSelectedContainer('');
    setContainers([]);
    setBlobs([]);
    setCurrentPrefix('');
    setBreadcrumbs([]);
    setContainerError(null);
    setBlobError(null);
  };

  const handleContainerChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    console.log("handleContainerChange triggered with value:", event.target.value); // Keep diagnostic log
    setSelectedContainer(event.target.value);
    setCurrentPrefix('');
    setBlobs([]);
    setBlobError(null);
  };

  const handleNavigate = (blob: AzureBlob) => {
        if (blob.isDirectory) {
            setCurrentPrefix(blob.path);
        } else {
            console.log("File clicked:", blob);
        }
    };

    const handleBreadcrumbClick = (index: number) => {
        if (index === 0) { // Clicked on Container name
            setCurrentPrefix('');
        } else {
            const newPrefix = breadcrumbs.slice(1, index + 1).join('/') + '/';
            setCurrentPrefix(newPrefix);
        }
    };

    const handleAddToSyncList = async (blob: AzureBlob) => {
        if (!selectedConnectionId || !selectedContainer) return;
        const newItem: AzureSyncItemCreate = {
            connection_id: selectedConnectionId, // Add connection_id
            item_name: blob.name,
            container_name: selectedContainer,
            item_path: blob.path,
            item_type: blob.isDirectory ? 'prefix' : 'blob',
        };
        try {
            const addedItem = await addAzureSyncItem(newItem);
            setSyncList(prev => [...prev, addedItem]);
            toast({ title: t('common.addedToSyncList'), status: 'success', duration: 2000 });
        } catch (error: any) {
            toast({ title: t('errors.addToSyncListFailed'), description: error.message, status: 'error' });
        }
    };

    const handleRemoveFromSyncList = async (itemId: number) => {
        const originalList = [...syncList];
        setSyncList(prev => prev.filter(item => item.id !== itemId));
        try {
            await removeAzureSyncItem(itemId);
            toast({ title: t('common.removedFromSyncList'), status: 'success', duration: 2000 });
        } catch (error: any) {
            setSyncList(originalList);
            toast({ title: t('errors.removeFromSyncListFailed'), description: error.message, status: 'error' });
        }
    };

     const handleProcessSyncList = async () => {
        // Ensure a connection is selected before proceeding
        if (!selectedConnectionId) {
            toast({ title: t('errors.error'), description: t('azureBlobBrowser.errors.noConnectionSelected'), status: 'warning' });
            return;
        }

        setIsProcessingSync(true);
        setSyncProcessError(null);
        setIngestionTaskStatus(null);
        setIngestionTaskId(null);
        setIngestionError(null);
        try {
            // Pass the selectedConnectionId
            const response = await triggerAzureIngestion(selectedConnectionId);
            if (response.task_id) {
                toast({ title: t('azureBlobBrowser.syncSuccessTitle'), description: t('azureBlobBrowser.syncSuccessDetail', { taskId: response.task_id }), status: 'info' });
                startIngestionPolling(response.task_id);
            } else {
                // Handle the NO_OP case or other messages from the backend
                const message = response.message || t('azureBlobBrowser.syncWarningDetail');
                toast({ title: t('azureBlobBrowser.syncWarningTitle'), description: message, status: 'warning' });
                setIsProcessingSync(false);
            }
        } catch (error: any) {
            const errorMessage = error.message || t('azureBlobBrowser.errors.processSyncList');
            setSyncProcessError(errorMessage);
            toast({ title: t('errors.processSyncListFailed'), description: errorMessage, status: 'error' });
            setIsProcessingSync(false);
        }
    };

  // Tab change handler
  const handleTabsChange = (index: number) => {
    setTabIndex(index);
  };

  // --- Polling Logic --- 
  const stopIngestionPolling = useCallback(() => {
    console.log('[Azure Polling] stopIngestionPolling called.');
    if (ingestionPollingIntervalRef.current) {
      clearInterval(ingestionPollingIntervalRef.current);
      ingestionPollingIntervalRef.current = null;
    }
    setIsProcessingSync(false);
    setIsIngestionPolling(false);
  }, [setIsProcessingSync, setIsIngestionPolling]);

  const pollIngestionTaskStatus = useCallback(async (taskId: string) => {
    if (!taskId) return;
    console.log(`[Azure Polling] Checking status for task ${taskId}...`);
    try {
      const statusResult = await getTaskStatus(taskId);
      setIngestionTaskStatus(statusResult);
      setIngestionError(null);

      const finalStates = [TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED, 'SUCCESS', 'FAILURE'];
      if (finalStates.includes(statusResult.status as TaskStatusEnum | 'SUCCESS' | 'FAILURE')) {
        stopIngestionPolling();
        const isSuccess = statusResult.status === TaskStatusEnum.COMPLETED || statusResult.status === 'SUCCESS';
        const errorMessage = statusResult?.details || t('azureBlobBrowser.syncFailedDetail');
        toast({ title: isSuccess ? t('azureBlobBrowser.syncCompleteTitle') : t('azureBlobBrowser.syncFailedTitle'), 
                description: isSuccess ? t('azureBlobBrowser.syncCompleteDetail', { taskId: taskId }) : errorMessage,
                status: isSuccess ? 'success' : 'error', duration: 5000 });
        // Refresh the *pending* list specifically after polling finishes
        if (selectedConnectionId) {
            // Fetch only pending items to update the main sync list display
            getAzureSyncList(selectedConnectionId, 'pending').then(setSyncList).catch(err => {
                console.error("Failed to refresh pending sync list:", err);
                setSyncListError(err instanceof Error ? err.message : t('errors.anErrorOccurred'));
             });
        }
      }
    } catch (error: any) {
      console.error("Error polling task status:", error);
      stopIngestionPolling();
      const errorMessage = error instanceof Error ? error.message : t('errors.anErrorOccurred');
      setIngestionError(errorMessage);
      toast({ title: t('errors.pollingErrorTitle'), description: errorMessage, status: 'error' });
    }
  }, [stopIngestionPolling, t, toast, selectedConnectionId]);

  const startIngestionPolling = useCallback((taskId: string) => {
    stopIngestionPolling();
    setIngestionTaskId(taskId);
    setIsIngestionPolling(true);
    setIsProcessingSync(true);
    setIngestionError(null);
    setIngestionTaskStatus({ task_id: taskId, status: TaskStatusEnum.PENDING, progress: 0, message: 'Starting...' });
    pollIngestionTaskStatus(taskId);
    ingestionPollingIntervalRef.current = setInterval(() => pollIngestionTaskStatus(taskId), 5000);
  }, [stopIngestionPolling, pollIngestionTaskStatus, setIsProcessingSync]);

  // Cleanup polling on unmount
  useEffect(() => { return () => { stopIngestionPolling(); }; }, [stopIngestionPolling]);

  const isInSyncList = useCallback((itemPath: string) => {
      return syncList.some(item => 
          item.container_name === selectedContainer && 
          item.item_path === itemPath
      );
  }, [syncList, selectedContainer]);

  // Memoized lists for pending and history items (similar to S3)
  const pendingSyncItems = React.useMemo(() => 
    syncList.filter(item => item.status === 'pending'), 
  [syncList]);

  const historySyncItems = React.useMemo(() => 
    syncList.filter(item => item.status === 'completed' || item.status === 'error')
    .sort((a, b) => b.id - a.id), // Sort by ID descending (newest first)
  [syncList]);

  // --- Render Logic using Chakra UI ---

  // +++ Moved Definition UP: Define Content for Browse & Sync Tab FIRST +++
  const browseAndSyncContent = (
    <VStack spacing={4} align="stretch"> 
      {/* Connection & Container Row */}
      <HStack spacing={4} align="end">
         {/* Connection Select */}
         <FormControl id="azure-connection" isDisabled={isLoadingConnections || isProcessingSync || isIngestionPolling} flex={1}>
            <FormLabel>{t('azureBlobBrowser.connectionLabel', 'Select Connection')}</FormLabel>
            {/* Add Icon to Select */}
            <HStack>
               <Icon as={FaCloud} color="blue.500" boxSize={5} /> {/* Azure Icon */} 
               <Select
                 placeholder={isLoadingConnections ? t('common.loading') : connectionError ? t('errors.loadConnectionsFailed') : t('azureBlobBrowser.connectionSelectPlaceholder')}
                 value={selectedConnectionId}
                 onChange={handleConnectionChange}
                 isInvalid={!!connectionError}
               >
                 {connections.map((conn) => (
                   <option key={conn.id} value={conn.id}>
                     {conn.name} {/* Use conn.name based on API definition */}
                   </option>
                 ))}
               </Select>
            </HStack>
            {connectionError && <FormErrorMessage>{connectionError}</FormErrorMessage>}
         </FormControl>

         {/* Container Select */}
         {selectedConnectionId && (
            <FormControl id="azure-container" isDisabled={!selectedConnectionId || isLoadingContainers || isProcessingSync || isIngestionPolling} flex={1}>
              <FormLabel>{t('azureBlobBrowser.containerLabel', 'Select Container')}</FormLabel>
              <Select 
                 placeholder={isLoadingContainers ? t('common.loading') : containerError ? t('errors.loadContainersFailed') : t('azureBlobBrowser.containerSelectPlaceholder')}
                 value={selectedContainer}
                 onChange={handleContainerChange}
                 isInvalid={!!containerError}
              >
                {containers.map((cont) => (
                  <option key={cont.name} value={cont.name}>
                    {cont.name}
                  </option>
                ))}
              </Select>
              {containerError && <FormErrorMessage>{containerError}</FormErrorMessage>}
            </FormControl>
         )}
      </HStack>

      {/* Breadcrumbs */}
      {selectedContainer && (
          <Breadcrumb separator='/' spacing='8px'>
            <BreadcrumbItem>
                <BreadcrumbLink onClick={() => handleBreadcrumbClick(0)}>{selectedContainer}</BreadcrumbLink>
            </BreadcrumbItem>
            {breadcrumbs.slice(1).map((part, index) => (
                <BreadcrumbItem key={index + 1}>
                    <BreadcrumbLink onClick={() => handleBreadcrumbClick(index + 1)}>{part}</BreadcrumbLink>
                </BreadcrumbItem>
            ))}
          </Breadcrumb>
       )}

      {/* Blob List Table */}
      {selectedContainer && (
          isLoadingBlobs ? <Spinner /> :
          blobError ? <Text color="red.500">{blobError}</Text> :
          <Box mt={4} borderWidth="1px" borderRadius="md" bg={bgColor} overflow="hidden">
            <TableContainer> 
                <Table variant="simple" size="sm">
                    <Thead>
                        <Tr>
                            <Th width="50%">{t('common.name')}</Th>
                            <Th width="25%">{t('common.modified')}</Th>
                            <Th width="15%" isNumeric>{t('common.size')}</Th>
                            <Th width="10%" textAlign="center">{t('common.sync')}</Th>
                        </Tr>
                    </Thead>
                    <Tbody>
                        {blobs.length === 0 && !isLoadingBlobs && (
                            <Tr><Td colSpan={4} textAlign="center">{t('azureBlobBrowser.folderEmpty', 'Folder is empty.')}</Td></Tr>
                        )}
                        {blobs.map((blob) => {
                            const alreadyInList = isInSyncList(blob.path);
                            const currentlyDisabled = alreadyInList || isProcessingSync || isIngestionPolling;
                            const actionButtonLabel = alreadyInList ? t('azureBlobBrowser.alreadyInSyncList') : t('common.add');
                            return (
                                <Tr 
                                  key={blob.path} 
                                  _hover={{ bg: useColorModeValue('gray.100', 'gray.700') }} 
                                  cursor={blob.isDirectory ? 'pointer' : 'default'}
                                  onClick={() => blob.isDirectory && handleNavigate(blob)}
                                >
                                    <Td>
                                        <HStack spacing={2}>
                                            <Icon 
                                              as={blob.isDirectory ? FaFolder : FaFileAlt} 
                                              color={blob.isDirectory ? folderColor : fileColor}
                                            />
                                            <Text>{blob.name}</Text>
                                        </HStack>
                                    </Td>
                                    <Td>{formatDateTime(blob.lastModified)}</Td>
                                    <Td isNumeric>{formatFileSize(blob.size)}</Td>
                                    <Td textAlign="center">
                                         <Tooltip label={actionButtonLabel} aria-label={actionButtonLabel} placement="top">
                                            <span> 
                                              <IconButton
                                                aria-label={actionButtonLabel}
                                                icon={alreadyInList ? <Icon as={FaCheckCircle} /> : <Icon as={FaPlusCircle} />}
                                                size="xs"
                                                variant="solid"
                                                colorScheme={alreadyInList ? "green" : "blue"}
                                                onClick={(e) => {
                                                    if (!alreadyInList) {
                                                        e.stopPropagation(); 
                                                        handleAddToSyncList(blob); 
                                                    }
                                                }}
                                                isDisabled={currentlyDisabled}
                                              />
                                            </span>
                                         </Tooltip>
                                    </Td>
                                </Tr>
                            );
                        })}
                    </Tbody>
                </Table>
            </TableContainer>
          </Box>
       )}

       {/* Sync List Section */}
      {selectedConnectionId && (
          <Box mt={8} p={4} borderWidth="1px" borderRadius="md">
            {/* Filter syncList to only show pending items for display and logic below */}
            {(() => {
                const pendingItems = syncList.filter(item => item.status === 'pending');
                const pendingCount = pendingItems.length;
                return (
                    <>
                        <HStack justify="space-between" mb={4}>
                            <Heading size="md">{t('azureBlobBrowser.syncListTitle', 'Azure Sync List')}</Heading>
                            {/* Use pendingCount for the Tag */}
                            <Tag size="md" variant='solid' colorScheme='blue'>
                                {t('common.pendingCount', { count: pendingCount })}
                            </Tag>
                        </HStack>
                        {isLoadingSyncList && <Spinner />}
                        {syncListError && <Text color="red.500">{syncListError}</Text>}
                        {!isLoadingSyncList && pendingCount === 0 && 
                            <Text color="gray.500" textAlign="center" p={4}>
                                {t('azureBlobBrowser.syncListEmptyMessage', 'Your sync list is empty. Browse Azure and add files/folders.')}
                            </Text>
                        }
                        {!isLoadingSyncList && pendingCount > 0 && (
                            <VStack spacing={2} align="stretch" mb={4} maxHeight="200px" overflowY="auto">
                                {/* Iterate over PENDING items only */}
                                {pendingItems.map((item) => (
                                <HStack key={item.id} justify="space-between" p={1} _hover={{ bg: useColorModeValue('gray.50', 'gray.800') }}>
                                    <HStack spacing={1} flex={1} minWidth={0}>
                                        <Icon as={item.item_type === 'prefix' ? FaFolder : FaFileAlt} size="sm" color="gray.500"/>
                                        <Text fontSize="sm" title={item.item_path} isTruncated>
                                            {item.item_name} 
                                            <Text as="span" color="gray.500" fontSize="xs"> ({item.container_name})</Text>
                                        </Text>
                                    </HStack>
                                    <IconButton
                                        aria-label={t('common.remove')}
                                        icon={<DeleteIcon />}
                                        size="xs"
                                        variant="ghost"
                                        colorScheme="red"
                                        onClick={() => handleRemoveFromSyncList(item.id)}
                                        isDisabled={isProcessingSync || isIngestionPolling}
                                    />
                                </HStack>
                                ))}
                            </VStack>
                        )}
                        <HStack justify="flex-end">
                            <Button 
                                colorScheme="blue" 
                                leftIcon={<RepeatIcon />} 
                                onClick={handleProcessSyncList} 
                                isLoading={isProcessingSync || isIngestionPolling}
                                /* Disable button based on PENDING count */
                                isDisabled={pendingCount === 0 || isProcessingSync || isIngestionPolling}
                            >
                                {isProcessingSync || isIngestionPolling ? t('azureBlobBrowser.syncing') : t('azureBlobBrowser.processSynced')}
                            </Button>
                        </HStack>
                    </>
                );
             })()}
             {/* Keep the Ingestion Status display outside the IIFE */}
             {syncProcessError && <Text color="red.500" mt={2}>{syncProcessError}</Text>}
            {ingestionTaskStatus && (
              <Box mt={4} p={3} borderWidth="1px" borderRadius="md" bg={useColorModeValue('gray.50', 'gray.700')}>
                <HStack justify="space-between">
                  <Text fontWeight="bold">{t('azureBlobBrowser.ingestionStatusTitle')} (ID: {ingestionTaskStatus.task_id})</Text>
                   {isIngestionPolling && <Spinner size="sm" />}
                </HStack>
                <Text>Status: {ingestionTaskStatus.status}</Text>
                 {ingestionTaskStatus.progress != null && (
                    <Progress value={ingestionTaskStatus.progress} size="sm" colorScheme="blue" mt={1} />
                 )}
                 {ingestionTaskStatus.message && <Text fontSize="sm" mt={1}>Message: {ingestionTaskStatus.message}</Text>}
                 {ingestionError && <Text color="red.500" mt={1}>Error: {ingestionError}</Text>}
              </Box>
            )}
          </Box>
       )}
    </VStack>
  );

  return (
    <Box p={5}>
      {/* Add Page Title */}
      <Heading size="lg" mb={6}>{t('azureBlobBrowser.title', 'Azure Blob Browser')}</Heading>

      {/* Add History Tab */}
      <Tabs index={tabIndex} onChange={setTabIndex} variant="soft-rounded" colorScheme="blue">
        <TabList mb="1em">
          <Tab>{t('azureBlobBrowser.tabs.browseAndSync', 'Browse & Sync')}</Tab>
          <Tab>{t('azureBlobBrowser.tabs.history', 'History')}</Tab> {/* Added History Tab */} 
          <Tab>{t('azureBlobBrowser.tabs.settings', 'Settings')}</Tab>
        </TabList>
        <TabPanels>
          {/* Panel 1: Browse & Sync Content */}
          <TabPanel p={0}> {/* Remove padding if VStack handles it */}
            {browseAndSyncContent}
          </TabPanel>
           {/* Panel 2: History Content */}
          <TabPanel p={0}>
             <AzureHistoryListComponent
                items={historySyncItems}
                isLoading={isLoadingSyncList} 
                error={syncListError} 
                t={t}
              />
          </TabPanel>
          {/* Panel 3: Settings Content */}
          <TabPanel>
            <AzureConnectionManager onConnectionsChange={loadConnections} />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
} 