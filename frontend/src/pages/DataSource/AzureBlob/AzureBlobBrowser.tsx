import React, { useState, useEffect, useCallback } from 'react';
import {
    Box, Heading, Select, Button, Icon, // Basic Chakra components
    Table, Thead, Tbody, Tr, Th, Td, TableContainer, // Chakra Table
    Breadcrumb, BreadcrumbItem, BreadcrumbLink, // Chakra Breadcrumb
    VStack, HStack, Stack, // Chakra Layout
    Alert, AlertIcon, Spinner, Center, Text, Tag, // Chakra Feedback & Text
    List, ListItem, // Chakra List
    Tabs, TabList, Tab, TabPanels, TabPanel, // Chakra Tabs
    FormControl, FormLabel, // Chakra Form (if needed for Settings later)
    IconButton, // Chakra IconButton
    useColorModeValue, // Hook for colors
    useToast // Hook for notifications
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FaFolder, FaFileAlt, FaSync, FaPlusCircle, FaTrashAlt } from 'react-icons/fa'; // Keep react-icons
import { ChevronRightIcon } from '@chakra-ui/icons'; // Chakra icons

import apiClient from '../../../api/apiClient';
import axios from 'axios';

// --- API Interface Definitions ---
// Existing interfaces: AzureConnection, AzureContainer, AzureBlob, AzureSyncItem
interface AzureConnection {
  id: string; // Use string ID
  name: string;
}
interface AzureContainer { name: string; }
interface AzureBlob {
  name: string;
  path: string;
  isDirectory: boolean;
  size?: number | null;
  lastModified?: string | null; // Expect ISO string
}
interface AzureSyncItem {
  id: number;
  item_name: string;
  container_name: string;
  item_path: string;
  item_type: 'blob' | 'prefix';
  status: 'pending' | 'processing' | 'completed' | 'error';
}

// --- API Functions (Keep as is, using apiClient) ---
const getAzureConnections = async (): Promise<AzureConnection[]> => {
  console.log("API CALL: getAzureConnections");
  try {
      const response = await apiClient.get<AzureConnection[]>('/azure_blob/connections');
      // Ensure ID compatibility if backend sends UUID as string
      return response.data.map(conn => ({ ...conn, id: String(conn.id) }));
  } catch (error) {
      console.error("Failed to fetch connections:", error);
      const errorMsg = axios.isAxiosError(error) ? error.response?.data?.detail || error.message : 'Unknown error';
      throw new Error(`Failed to fetch connections: ${errorMsg}`);
  }
};

const listAzureContainers = async (connectionId: string): Promise<AzureContainer[]> => {
  console.log("API CALL: listAzureContainers", connectionId);
  if (!connectionId) throw new Error("Connection ID is required to list containers");
  try {
      const response = await apiClient.get<string[]>(`/azure_blob/connections/${connectionId}/containers`);
      return response.data.map(name => ({ name })); // Map string array to AzureContainer objects
  } catch (error) {
       console.error("Failed to list containers:", error);
       const errorMsg = axios.isAxiosError(error) ? error.response?.data?.detail || error.message : 'Unknown error';
       throw new Error(`Failed to list containers: ${errorMsg}`);
  }
};

const listAzureBlobs = async (connectionId: string, containerName: string, prefix: string = ''): Promise<AzureBlob[]> => {
  console.log("API CALL: listAzureBlobs", connectionId, containerName, prefix);
  if (!connectionId || !containerName) {
      throw new Error("Connection ID and Container Name are required to list blobs");
  }
  const encodedContainerName = encodeURIComponent(containerName);
  const url = `/azure_blob/connections/${connectionId}/containers/${encodedContainerName}/objects`;

  try {
    const response = await apiClient.get<AzureBlob[]>(url, {
      params: { prefix: prefix } // Pass prefix as query parameter
    });
    // Ensure lastModified is correctly handled (it should be string/null from backend)
    return response.data;
  } catch (error) {
      console.error("[listAzureBlobs] API Error listing blobs:", error); // Log error within function
      const errorMsg = axios.isAxiosError(error) ? error.response?.data?.detail || error.message : 'Unknown error';
      throw new Error(`Failed to list blobs: ${errorMsg}`);
  }
};

// --- Mocked Sync API Functions --- 
const addAzureSyncItem = async (item: Omit<AzureSyncItem, 'id' | 'status'>): Promise<AzureSyncItem> => {
    console.log("API CALL (Mock): addAzureSyncItem", item);
    // TODO: Replace with actual API call, e.g., POST /api/v1/azure_blob/sync_list/add
    // const response = await apiClient.post<AzureSyncItem>('/api/v1/azure_blob/sync_list/add', item);
    // return response.data;
    await new Promise(resolve => setTimeout(resolve, 300));
    // Mock response
    return { ...item, id: Math.random(), status: 'pending' };
};

const getAzureSyncList = async (): Promise<AzureSyncItem[]> => {
    console.log("API CALL (Mock): getAzureSyncList");
    // TODO: Replace with actual API call, e.g., GET /api/v1/azure_blob/sync_list
    // const response = await apiClient.get<AzureSyncItem[]>('/api/v1/azure_blob/sync_list');
    // return response.data;
    await new Promise(resolve => setTimeout(resolve, 400));
    // Mock response
    return [
        // { id: 101, item_name: 'existing_file.txt', container_name: 'container-a', item_path: 'existing_file.txt', item_type: 'blob', status: 'pending' },
    ];
};

const removeAzureSyncItem = async (itemId: number): Promise<void> => {
    console.log("API CALL (Mock): removeAzureSyncItem", itemId);
    // TODO: Replace with actual API call, e.g., DELETE /api/v1/azure_blob/sync_list/remove/{itemId}
    // await apiClient.delete(`/api/v1/azure_blob/sync_list/remove/${itemId}`);
    await new Promise(resolve => setTimeout(resolve, 300));
};

const triggerAzureIngestion = async (): Promise<{ task_id: string }> => {
    console.log("API CALL (Mock): triggerAzureIngestion");
    // TODO: Replace with actual API call, e.g., POST /api/v1/azure_blob/ingest
    // const response = await apiClient.post<{ task_id: string }>('/api/v1/azure_blob/ingest');
    // return response.data;
    await new Promise(resolve => setTimeout(resolve, 1000));
    // Mock response
    return { task_id: `azure-task-${Math.random().toString(36).substring(7)}` };
};

// --- Helper Functions (Keep as is) ---
const formatFileSize = (bytes?: number | null): string => {
    if (bytes === undefined || bytes === null) return '-';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const precision = i < 2 ? 1 : 0;
    return parseFloat((bytes / Math.pow(k, i)).toFixed(precision)) + ' ' + sizes[i];
};

const formatDateTime = (dateTimeString?: string | null): string => {
  if (!dateTimeString) return '-';
  try {
    // Format consistently, maybe without seconds?
    return new Date(dateTimeString).toLocaleString(undefined, {
        year: 'numeric', month: 'numeric', day: 'numeric', 
        hour: 'numeric', minute: '2-digit' 
    });
  } catch {
    return dateTimeString; // Fallback
  }
};

// --- Component ---

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

  // --- Color Mode Values (Chakra) ---
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const tableHeaderBg = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.700');
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');

  // --- useEffect Hooks (Keep logic, adapt error handling if needed) ---
  // Load connections
  useEffect(() => {
    const loadConnections = async () => {
        setIsLoadingConnections(true);
        setConnectionError(null);
        try {
            const data = await getAzureConnections();
            setConnections(data);
        } catch (error: any) { // Catch specific error type
            console.error("Component Error: Failed to load connections:", error);
            setConnectionError(error.message || t('azureBlobBrowser.errors.loadConnections', 'Failed to load connections.'));
        } finally {
            setIsLoadingConnections(false);
        }
    };
    loadConnections();
  }, [t]);

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
            const data = await listAzureContainers(selectedConnectionId);
            setContainers(data);
            setSelectedContainer(''); // Reset selection
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

   // Load sync list (mocked)
   useEffect(() => {
       const loadSyncList = async () => {
            setIsLoadingSyncList(true);
            setSyncListError(null);
            try {
                const data = await getAzureSyncList();
                setSyncList(data);
            } catch (error: any) {
                console.error("Failed to load sync list (Mock):", error);
                setSyncListError(t('azureBlobBrowser.errors.loadSyncList', 'Failed to load sync list.'));
            } finally {
                setIsLoadingSyncList(false);
            }
       };
       loadSyncList();
   }, [t]);

  // --- Event Handlers (Keep logic, adapt types/toast) ---
  const handleConnectionChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedConnectionId(event.target.value);
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
        const newItem: Omit<AzureSyncItem, 'id' | 'status'> = {
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
        setIsProcessingSync(true);
        setSyncProcessError(null);
        try {
            const result = await triggerAzureIngestion();
            toast({ title: t('azureBlobBrowser.syncSuccessTitle'), description: t('azureBlobBrowser.syncSuccessDetail', { taskId: result.task_id }), status: 'info' });
            // Refresh sync list
            const data = await getAzureSyncList();
            setSyncList(data);
        } catch (error: any) {
            setSyncProcessError(t('azureBlobBrowser.errors.processSyncList', 'Failed to start sync process.') + `: ${error.message}`);
            toast({ title: t('errors.processSyncListFailed'), description: error.message, status: 'error' });
        } finally {
            setIsProcessingSync(false);
        }
    };

  // Tab change handler
  const handleTabsChange = (index: number) => {
    setTabIndex(index);
  };

  // --- Render Logic using Chakra UI ---

  // Define Content for Browse & Sync Tab
  const browseAndSyncContent = (
    <VStack spacing={4} align="stretch"> {/* Use VStack */} 
      {/* Connection & Container Row */}
      <HStack spacing={4}> {/* Use HStack */} 
         {/* Connection Select */} 
         <FormControl id="azure-connection" isDisabled={isLoadingConnections} flex={1}>
            {/* <FormLabel>Select Connection</FormLabel> */}
            <Select 
              placeholder={isLoadingConnections ? t('common.loading') : t('azureBlobBrowser.connectionSelectPlaceholder')}
              value={selectedConnectionId}
              onChange={handleConnectionChange}
              icon={isLoadingConnections ? <Spinner size="xs" /> : undefined}
            >
               {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name}
                  </option>
                ))}
            </Select>
            {connectionError && <Text color="red.500" fontSize="sm" mt={1}>{connectionError}</Text>}
          </FormControl>

         {/* Container Select */} 
         {selectedConnectionId && (
              <FormControl id="azure-container" isDisabled={isLoadingContainers || !selectedConnectionId} minWidth="200px">
                {/* <FormLabel>Select Container</FormLabel> */} 
                <Select 
                   placeholder={isLoadingContainers ? t('common.loading') : t('azureBlobBrowser.containerSelectPlaceholder')}
                   value={selectedContainer}
                   onChange={handleContainerChange}
                   icon={isLoadingContainers ? <Spinner size="xs" /> : undefined}
                >
                  {containers.map((cont) => (
                     <option key={cont.name} value={cont.name}>
                       {cont.name}
                     </option>
                  ))}
                </Select>
                {containerError && <Text color="red.500" fontSize="sm" mt={1}>{containerError}</Text>}
              </FormControl>
         )}
      </HStack>

      {/* Browser Section */} 
      {selectedContainer && (
           <Box borderWidth="1px" borderRadius="lg" bg={bgColor} shadow="sm" overflow="hidden"> {/* Mimic outlined Paper */} 
              {/* Breadcrumbs */}
              <Box p={2.5} borderBottomWidth="1px" borderColor={borderColor} bg={tableHeaderBg}> 
                 <Breadcrumb spacing="8px" separator={<Icon as={ChevronRightIcon} color="gray.500" />}>
                    {breadcrumbs.map((part, index) => (
                        <BreadcrumbItem key={index} isCurrentPage={index === breadcrumbs.length - 1}>
                            <BreadcrumbLink 
                                href="#"
                                onClick={(e) => { e.preventDefault(); handleBreadcrumbClick(index); }}
                                display="flex" 
                                alignItems="center"
                                fontWeight={index === breadcrumbs.length - 1 ? 'semibold' : 'normal'}
                                _hover={{ textDecoration: 'none', color: 'blue.500'}}
                            >
                                <Icon as={FaFolder} mr={1.5} color={folderColor} />
                                {part}
                            </BreadcrumbLink>
                        </BreadcrumbItem>
                    ))}
                </Breadcrumb>
              </Box>

               {/* Blob List */}
               <Box>
                   {isLoadingBlobs && <Center p={6}><Spinner /></Center>}
                   {blobError && <Alert status="error" m={4}><AlertIcon />{blobError}</Alert>}
                   {!isLoadingBlobs && !blobError && blobs.length === 0 && 
                        <Center p={6}><Text color="gray.500">{t('azureBlobBrowser.folderEmpty')}</Text></Center>
                   }
                   {!isLoadingBlobs && !blobError && blobs.length > 0 && (
                       <TableContainer>
                          <Table variant="simple" size="sm">
                              <Thead bg={tableHeaderBg}>
                                  <Tr>
                                      <Th width="50%">{t('common.name').toUpperCase()}</Th>
                                      <Th width="25%">{t('common.lastModified').toUpperCase()}</Th>
                                      <Th width="15%" isNumeric>{t('common.size').toUpperCase()}</Th>
                                      <Th width="10%" textAlign="center">{t('common.sync').toUpperCase()}</Th>
                                  </Tr>
                              </Thead>
                              <Tbody>
                                  {blobs.map((blob) => (
                                      <Tr 
                                        key={blob.path} 
                                        _hover={{ bg: hoverBg }} 
                                        cursor={blob.isDirectory ? 'pointer' : 'default'}
                                        onClick={() => blob.isDirectory && handleNavigate(blob)}
                                      >
                                          <Td>
                                              <HStack spacing={2}>
                                                  <Icon 
                                                    as={blob.isDirectory ? FaFolder : FaFileAlt} 
                                                    color={blob.isDirectory ? folderColor : fileColor}
                                                    boxSize="1.2em"
                                                  />
                                                  <Text fontWeight="medium">{blob.name}</Text>
                                              </HStack>
                                          </Td>
                                          <Td>{formatDateTime(blob.lastModified)}</Td>
                                          <Td isNumeric>{blob.isDirectory ? '-' : formatFileSize(blob.size)}</Td>
                                          <Td textAlign="center">
                                              <IconButton
                                                  aria-label={t('azureBlobBrowser.addToSyncList')}
                                                  icon={<FaPlusCircle />}
                                                  size="sm"
                                                  variant="ghost"
                                                  colorScheme="blue"
                                                  onClick={(e) => { e.stopPropagation(); handleAddToSyncList(blob); }}
                                              />
                                          </Td>
                                      </Tr>
                                  ))}
                              </Tbody>
                          </Table>
                      </TableContainer>
                   )}
               </Box>
           </Box>
      )}

      {/* Sync List Section */} 
      <Box borderWidth="1px" borderRadius="lg" bg={bgColor} shadow="sm" overflow="hidden">
          <HStack justify="space-between" p={4} borderBottomWidth="1px" borderColor={borderColor}>
             <Heading size="md">{t('azureBlobBrowser.syncListTitle')}</Heading>
             <Tag size="md" variant='solid' colorScheme='blue'>
                {t('common.pendingCount', { count: syncList.filter(item => item.status === 'pending').length })}
             </Tag>
          </HStack>
          <Box maxHeight="300px" overflowY="auto">
             {isLoadingSyncList && <Center p={5}><Spinner /></Center>}
             {syncListError && <Center p={5}><Text color="red.500">{syncListError}</Text></Center>}
             {!isLoadingSyncList && !syncListError && (
                 <>
                    {syncList.filter(item => item.status === 'pending').length === 0 ? (
                        <Center p={5}><Text color="gray.500">{t('azureBlobBrowser.syncListEmpty')}</Text></Center>
                    ) : (
                      <List spacing={1} p={2}>
                           {syncList.filter(item => item.status === 'pending').map(item => (
                                <ListItem 
                                    key={item.id} 
                                    display="flex" 
                                    justifyContent="space-between" 
                                    alignItems="center"
                                    p={1.5}
                                    borderRadius="md"
                                    _hover={{ bg: hoverBg }}
                                >
                                   <HStack spacing={2} flex={1} minWidth={0}>
                                        <Icon 
                                            as={item.item_type === 'prefix' ? FaFolder : FaFileAlt} 
                                            color={item.item_type === 'prefix' ? folderColor : fileColor}
                                            boxSize="1.2em"
                                        />
                                        <VStack align="start" spacing={0} flex={1} minWidth={0}>
                                            <Text fontSize="sm" fontWeight="medium" noOfLines={1} title={item.item_path}>{item.item_name}</Text>
                                            <Text fontSize="xs" color="gray.500">{t('azureBlobBrowser.containerLabel')}: {item.container_name}</Text>
                                        </VStack>
                                   </HStack>
                                    <IconButton
                                        aria-label={t('common.remove')}
                                        icon={<FaTrashAlt />}
                                        size="sm"
                                        variant="ghost"
                                        colorScheme="red"
                                        onClick={() => handleRemoveFromSyncList(item.id)}
                                        isDisabled={isProcessingSync}
                                    />
                                </ListItem>
                            ))}
                       </List>
                    )}
                 </>
             )}
           </Box>
           <HStack justify="flex-end" p={3} borderTopWidth="1px" borderColor={borderColor}>
               <Button
                    leftIcon={<Icon as={FaSync} />}
                    colorScheme="blue"
                    onClick={handleProcessSyncList}
                    isDisabled={isProcessingSync || syncList.filter(item => item.status === 'pending').length === 0}
                    isLoading={isProcessingSync}
                    loadingText={t('common.processing')}
                >
                    {t('azureBlobBrowser.processSyncListButton')}
               </Button>
           </HStack>
           {syncProcessError && <Alert status="error" m={4} mt={0}><AlertIcon />{syncProcessError}</Alert>}
       </Box>
    </VStack>
  );

  return (
    <Box p={4}> {/* Use Box for overall padding */} 
      <Heading size="lg" mb={6}>{t('azureBlobBrowser.title')}</Heading>
      <Tabs index={tabIndex} onChange={handleTabsChange} variant='soft-rounded' colorScheme='blue'>
        <TabList mb={4}>
          <Tab>{t('azureBlobBrowser.tabs.browseAndSync')}</Tab>
          <Tab>{t('azureBlobBrowser.tabs.history')}</Tab>
          <Tab>{t('azureBlobBrowser.tabs.settings')}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel p={0}> {/* Remove TabPanel padding, VStack handles it */} 
            {browseAndSyncContent}
          </TabPanel>
          <TabPanel><Text>{t('azureBlobBrowser.tabs.history')} Placeholder</Text></TabPanel>
          <TabPanel><Text>{t('azureBlobBrowser.tabs.settings')} Placeholder</Text></TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
} 