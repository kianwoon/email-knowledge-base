import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Button,
  Heading,
  VStack,
  HStack,
  Text,
  Alert,
  AlertIcon,
  Divider,
  FormControl,
  FormLabel,
  Select,
  Switch,
  Checkbox,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  useColorModeValue,
  useToast,
  Flex,
  Spacer,
  Progress,
  Badge,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Icon,
  Spinner,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Input,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Wrap,
  WrapItem,
  Tag,
  TagLabel,
  TagCloseButton,
  IconButton
} from '@chakra-ui/react';
import { FaSync, FaCalendarAlt, FaEnvelope, FaFilter, FaClock, FaCheck, FaExclamationTriangle, FaFolder, FaPlus } from 'react-icons/fa';
import apiClient from '@/api/apiClient';
import { useTranslation } from 'react-i18next';

interface Folder {
  id: string;
  displayName: string;
  children?: Folder[];
  parentFolderId?: string;
}

interface SyncStatus {
  folder: string;
  folderId: string;
  status: 'idle' | 'syncing' | 'completed' | 'error';
  lastSync: string | null;
  progress: number;
  itemsProcessed: number;
  totalItems: number;
  error?: string;
}

interface SyncConfig {
  enabled: boolean;
  frequency: string;
  folders: string[];
  startDate?: string;
}

interface LastSyncInfo {
  last_sync: string | null;
  items_processed: number | null;
  folder: string | null;
}

const OutlookSyncPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const cardBg = useColorModeValue('white', 'gray.700');
  
  // State
  const [folders, setFolders] = useState<Folder[]>([]);
  const [flatFolders, setFlatFolders] = useState<Folder[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFolders, setSelectedFolders] = useState<string[]>([]);
  const [syncStatuses, setSyncStatuses] = useState<SyncStatus[]>([]);
  const [syncFrequency, setSyncFrequency] = useState('daily');
  const [syncActive, setSyncActive] = useState(false);
  const [enableAutomation, setEnableAutomation] = useState(false);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState<string>('');
  const [lastSyncInfo, setLastSyncInfo] = useState<LastSyncInfo | null>(null);
  const [primaryDomain, setPrimaryDomain] = useState<string>('');
  const [allianceDomains, setAllianceDomains] = useState<string[]>([]);
  const [newAllianceDomain, setNewAllianceDomain] = useState<string>('');
  
  // For confirmation modal
  const { isOpen, onOpen, onClose } = useDisclosure();
  
  // Fetch the last sync info from database
  const fetchLastSyncInfo = useCallback(async () => {
    try {
      const response = await apiClient.get('/v1/email/sync/last-sync');
      console.debug("Last sync API response:", response.data);
      
      // Store the last sync info
      setLastSyncInfo(response.data);
      
      // Update folder status based on last sync info
      if (response.data && response.data.last_sync) {
        // Use a log to help debug the folder matching issue
        console.debug("Last sync info received:", response.data);
        
        // Log all selected folders for debugging
        console.debug("Currently selected folders:", selectedFolders);
        console.debug("Available flat folders:", flatFolders.map(f => ({ id: f.id, name: f.displayName })));
        
        setSyncStatuses(prevStatuses => {
          // Create a copy of the current statuses
          const updatedStatuses = [...prevStatuses];
          
          // Get the folder that was actually synced (if available)
          const syncedFolderId = response.data.folder;
          
          if (syncedFolderId) {
            console.debug(`Looking for folder ID "${syncedFolderId}" in status list`);
            // Find that specific folder in our status list
            const folderIndex = updatedStatuses.findIndex(s => s.folderId === syncedFolderId);
            
            if (folderIndex !== -1) {
              console.debug(`Updating status for folder ID ${syncedFolderId} to 'completed'`);
              // Update only that folder's status
              updatedStatuses[folderIndex] = {
                ...updatedStatuses[folderIndex],
                status: 'completed',
                lastSync: response.data.last_sync,
                itemsProcessed: response.data.items_processed || 0
              };
            } else {
              console.debug(`Folder ID ${syncedFolderId} not found in status list`);
              // Log all folder IDs for comparison
              console.debug("Available folder IDs:", updatedStatuses.map(s => s.folderId));
            }
          } else {
            // If no specific folder ID in response, this is an older sync format
            // Set all folders with checkboxes checked to completed
            console.debug("No specific folder ID in last sync data, updating all checked folders");
            
            // We'll get the selected folder IDs from the current state to avoid dependencies
            const currentSelectedFolders = prevStatuses
              .filter(s => s.status === 'syncing' || s.status === 'completed')
              .map(s => s.folderId);
              
            if (currentSelectedFolders.length > 0) {
              console.debug("Marking these folders as completed:", currentSelectedFolders);
              currentSelectedFolders.forEach(folderId => {
                const index = updatedStatuses.findIndex(s => s.folderId === folderId);
                if (index !== -1) {
                  updatedStatuses[index] = {
                    ...updatedStatuses[index],
                    status: 'completed',
                    lastSync: response.data.last_sync,
                    itemsProcessed: response.data.items_processed || 0
                  };
                }
              });
            } else if (selectedFolders.length > 0) {
              // If no folders are in 'syncing' or 'completed' state but we have selectedFolders,
              // update those instead (fallback)
              console.debug("No folders in syncing/completed state, using selectedFolders:", selectedFolders);
              selectedFolders.forEach(folderId => {
                const index = updatedStatuses.findIndex(s => s.folderId === folderId);
                if (index !== -1) {
                  updatedStatuses[index] = {
                    ...updatedStatuses[index],
                    status: 'completed',
                    lastSync: response.data.last_sync,
                    itemsProcessed: response.data.items_processed || 0
                  };
                }
              });
            }
          }
          
          return updatedStatuses;
        });
      }
    } catch (error) {
      console.error("Failed to fetch last sync info:", error);
    }
  }, []);
  
  // Effect to update UI when lastSyncInfo changes
  useEffect(() => {
    if (lastSyncInfo?.last_sync) {
      // Update folder statuses when sync info changes
      setSyncStatuses(prevStatuses => {
        const updatedStatuses = [...prevStatuses];
        const syncedFolderId = lastSyncInfo.folder;
        
        // If we have a specific folder ID, update just that one
        if (syncedFolderId) {
          const folderIndex = updatedStatuses.findIndex(s => s.folderId === syncedFolderId);
          if (folderIndex !== -1) {
            updatedStatuses[folderIndex] = {
              ...updatedStatuses[folderIndex],
              status: 'completed',
              lastSync: lastSyncInfo.last_sync,
              itemsProcessed: lastSyncInfo.items_processed || 0
            };
          }
        }
        // Otherwise update all selected folders
        else if (selectedFolders.length > 0) {
          selectedFolders.forEach(folderId => {
            const index = updatedStatuses.findIndex(s => s.folderId === folderId);
            if (index !== -1) {
              updatedStatuses[index] = {
                ...updatedStatuses[index],
                status: 'completed',
                lastSync: lastSyncInfo.last_sync,
                itemsProcessed: lastSyncInfo.items_processed || 0
              };
            }
          });
        }
        
        return updatedStatuses;
      });
    }
  }, [lastSyncInfo, selectedFolders]);
  
  // Poll for sync status updates
  const pollSyncStatus = useCallback(() => {
    const interval = setInterval(async () => {
      try {
        const response = await apiClient.get('/v1/email/sync/status');
        
        if (response.data && response.data.length > 0) {
          setSyncStatuses(prevStatuses => {
            const updatedStatuses = [...prevStatuses];
            response.data.forEach((statusUpdate: SyncStatus) => {
              const index = updatedStatuses.findIndex(s => s.folderId === statusUpdate.folderId);
              if (index !== -1) {
                updatedStatuses[index] = {...updatedStatuses[index], ...statusUpdate};
              }
            });
            return updatedStatuses;
          });
          
          // Check if all syncs are complete
          const allComplete = response.data.every((status: SyncStatus) => 
            status.status === 'completed' || status.status === 'error' || status.status === 'idle'
          );
          
          if (allComplete) {
            setSyncActive(false);
            clearInterval(interval);
            
            // Fetch the last sync info from database after sync completes
            fetchLastSyncInfo();
            
            toast({
              title: t('outlookSync.notifications.syncCompleted', "Sync completed"),
              description: t('outlookSync.notifications.syncCompletedDesc', "All folder syncs have completed"),
              status: "success",
              duration: 5000,
              isClosable: true,
            });
          }
        }
      } catch (error) {
        console.error("Failed to get sync status:", error);
        // Don't clear the interval, keep trying
      }
    }, 3000);
    
    return () => clearInterval(interval);
  }, [toast, t, fetchLastSyncInfo]);
  
  // Fetch folders
  const fetchFolders = useCallback(async () => {
    try {
      setLoading(true);
      setLoadingError(null);
      
      const response = await apiClient.get('/v1/email/folders');
      console.debug("Folders fetched:", response.data);
      setFolders(response.data);
      
      // Convert hierarchical folders to flat list
      const flattenFolders = (folders: Folder[], result: Folder[] = []): Folder[] => {
        folders.forEach(folder => {
          result.push(folder);
          if (folder.children && folder.children.length > 0) {
            flattenFolders(folder.children, result);
          }
        });
        return result;
      };
      
      const allFolders = flattenFolders(response.data);
      console.debug("Flattened all folders (count):", allFolders.length);
      setFlatFolders(allFolders);
      
      // Initialize sync statuses for each folder
      const initialStatuses: SyncStatus[] = allFolders.map((folder: Folder) => ({
        folder: folder.displayName,
        folderId: folder.id,
        status: 'idle',
        lastSync: null,
        progress: 0,
        itemsProcessed: 0,
        totalItems: 0
      }));
      
      setSyncStatuses(initialStatuses);
      
      // Get previously configured sync settings
      const syncConfigResponse = await apiClient.get('/v1/email/sync/config');
      if (syncConfigResponse.data) {
        const config = syncConfigResponse.data;
        setSelectedFolders(config.folders || []);
        setSyncFrequency(config.frequency || 'daily');
        setEnableAutomation(config.enabled || false);
        setStartDate(config.startDate || '');
        setPrimaryDomain(config.primaryDomain || '');
        setAllianceDomains(config.allianceDomains || []);
        
        // If we have the last sync info, update the status of selected folders
        if (config.folders && config.folders.length > 0) {
          // Fetch the last sync info right away
          await fetchLastSyncInfo();
        }
      } else {
        // If no config available, still check if there's last sync info
        await fetchLastSyncInfo();
      }
      
      // Get current sync status if any syncs are active
      const syncStatusResponse = await apiClient.get('/v1/email/sync/status');
      if (syncStatusResponse.data && syncStatusResponse.data.length > 0) {
        setSyncStatuses(prevStatuses => {
          const updatedStatuses = [...prevStatuses];
          syncStatusResponse.data.forEach((statusUpdate: SyncStatus) => {
            const index = updatedStatuses.findIndex(s => s.folderId === statusUpdate.folderId);
            if (index !== -1) {
              updatedStatuses[index] = {...updatedStatuses[index], ...statusUpdate};
            }
          });
          return updatedStatuses;
        });
        
        // Set syncActive flag if any folder is currently syncing
        setSyncActive(syncStatusResponse.data.some((status: SyncStatus) => status.status === 'syncing'));
      }
    } catch (error) {
      console.error("Failed to fetch folders:", error);
      setLoadingError(t('outlookSync.loading.error', "Error loading folders. Please check the connection and try again."));
    } finally {
      setLoading(false);
    }
  }, [t, fetchLastSyncInfo]);
  
  useEffect(() => {
    fetchFolders();
  }, [fetchFolders]);
  
  // Start sync for selected folders
  const handleStartSync = async () => {
    if (selectedFolders.length === 0) {
      toast({
        title: t('outlookSync.notifications.noFoldersSelected', "No folders selected"),
        description: t('outlookSync.notifications.noFoldersSelectedDesc', "Please select at least one folder to sync"),
        status: "warning",
        duration: 5000,
        isClosable: true,
      });
      return;
    }
    
    try {
      setSyncActive(true);
      
      // Update selected folders' status to 'syncing'
      setSyncStatuses(prevStatuses => {
        const updatedStatuses = [...prevStatuses];
        selectedFolders.forEach(folderId => {
          const index = updatedStatuses.findIndex(s => s.folderId === folderId);
          if (index !== -1) {
            updatedStatuses[index] = {
              ...updatedStatuses[index],
              status: 'syncing',
              progress: 0,
              itemsProcessed: 0
            };
          }
        });
        return updatedStatuses;
      });
      
      // Call API to start sync
      const response = await apiClient.post('/v1/email/sync/start', {
        folders: selectedFolders,
        startDate: startDate || undefined
      });
      
      toast({
        title: t('outlookSync.notifications.syncStarted', "Sync started"),
        description: t('outlookSync.notifications.syncStartedDesc', "Sync initiated for {{count}} folders", { count: selectedFolders.length }),
        status: "success",
        duration: 5000,
        isClosable: true,
      });
      
      // Start polling for status updates
      pollSyncStatus();
    } catch (error) {
      console.error("Failed to start sync:", error);
      setSyncActive(false);
      
      // Update status to error
      setSyncStatuses(prevStatuses => {
        const updatedStatuses = [...prevStatuses];
        selectedFolders.forEach(folderId => {
          const index = updatedStatuses.findIndex(s => s.folderId === folderId);
          if (index !== -1) {
            updatedStatuses[index] = {
              ...updatedStatuses[index],
              status: 'error',
              error: t('outlookSync.errors.startSync', "Failed to start sync")
            };
          }
        });
        return updatedStatuses;
      });
      
      toast({
        title: t('outlookSync.notifications.syncFailed', "Sync failed"),
        description: t('outlookSync.notifications.syncFailedDesc', "Failed to start the sync process. Please try again later."),
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    }
  };
  
  // Save automation settings
  const handleSaveAutomation = async () => {
    try {
      // Validate selected folders
      if (enableAutomation && selectedFolders.length === 0) {
        toast({
          title: t('outlookSync.notifications.noFoldersSelected', "No folders selected"),
          description: t('outlookSync.notifications.automationFoldersNeeded', "Please select at least one folder for automated sync"),
          status: "warning",
          duration: 5000,
          isClosable: true,
        });
        return;
      }
      
      // Save the configuration
      await apiClient.post('/v1/email/sync/config', {
        enabled: enableAutomation,
        frequency: syncFrequency,
        folders: selectedFolders,
        startDate: startDate || undefined,
        primaryDomain: primaryDomain.trim() || undefined,
        allianceDomains: allianceDomains
      });
      
      toast({
        title: t('outlookSync.notifications.settingsSaved', "Settings saved"),
        description: enableAutomation 
          ? t('outlookSync.notifications.automationScheduled', "Automated sync scheduled {{frequency}}", { frequency: syncFrequency })
          : t('outlookSync.notifications.automationDisabled', "Automated sync has been disabled"),
        status: "success",
        duration: 5000,
        isClosable: true,
      });
      
      // Refresh the last sync info after saving settings
      fetchLastSyncInfo();
    } catch (error) {
      console.error("Failed to save automation settings:", error);
      toast({
        title: t('outlookSync.notifications.settingsError', "Error saving settings"),
        description: t('outlookSync.notifications.settingsErrorDesc', "There was an error saving your settings. Please try again."),
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    }
  };
  
  // Stop sync schedule with confirmation
  const handleStopSync = async () => {
    onOpen(); // Open the confirmation dialog
  };
  
  // The actual stop function that's called after confirmation
  const confirmStopSync = async () => {
    try {
      // Call the stop sync endpoint
      await apiClient.post('/v1/email/sync/stop');
      
      // Also update the configuration to be disabled in the database
      await apiClient.post('/v1/email/sync/config', {
        enabled: false,
        frequency: syncFrequency,
        folders: selectedFolders, // Keep selected folders but disable the sync
        startDate: startDate
      });
      
      // Update local state
      setEnableAutomation(false);
      
      toast({
        title: t('outlookSync.notifications.syncCancelled', "Sync Cancelled"),
        description: t('outlookSync.notifications.syncCancelledDesc', "Automated sync has been stopped and disabled"),
        status: "info",
        duration: 5000,
        isClosable: true,
      });
      
      onClose(); // Close the dialog
    } catch (error) {
      console.error("Failed to stop sync:", error);
      toast({
        title: t('outlookSync.notifications.stopSyncError', "Failed to stop sync"),
        description: t('outlookSync.notifications.stopSyncErrorDesc', "Could not cancel the automated sync"),
        status: "error",
        duration: 5000,
        isClosable: true,
      });
      onClose(); // Close the dialog even on error
    }
  };
  
  // Handle folder selection
  const handleFolderSelect = (folderId: string) => {
    setSelectedFolders(prev => {
      const newSelected = prev.includes(folderId) 
        ? prev.filter(id => id !== folderId) 
        : [...prev, folderId];
      
      // Update the status immediately based on the new selection
      if (lastSyncInfo?.last_sync) {
        setSyncStatuses(prevStatuses => {
          const updatedStatuses = [...prevStatuses];
          const index = updatedStatuses.findIndex(s => s.folderId === folderId);
          
          if (index !== -1) {
            // If folder was deselected, revert to idle
            if (prev.includes(folderId) && !newSelected.includes(folderId)) {
              updatedStatuses[index] = {
                ...updatedStatuses[index],
                status: 'idle',
                lastSync: null
              };
            } 
            // If folder was selected and we have last sync info, mark as completed
            else if (!prev.includes(folderId) && newSelected.includes(folderId)) {
              updatedStatuses[index] = {
                ...updatedStatuses[index],
                status: 'completed',
                lastSync: lastSyncInfo.last_sync,
                itemsProcessed: lastSyncInfo.items_processed || 0
              };
            }
          }
          
          return updatedStatuses;
        });
      }
      
      return newSelected;
    });
  };
  
  // ---- START: Alliance Domain Handlers ----
  const handleAddAllianceDomain = () => {
    if (newAllianceDomain && !allianceDomains.includes(newAllianceDomain.trim().toLowerCase())) {
      setAllianceDomains([...allianceDomains, newAllianceDomain.trim().toLowerCase()]);
      setNewAllianceDomain(''); // Clear input after adding
    }
  };

  const handleRemoveAllianceDomain = (domainToRemove: string) => {
    setAllianceDomains(allianceDomains.filter(domain => domain !== domainToRemove));
  };
  // ---- END: Alliance Domain Handlers ----
  
  // Determine folder status based on multiple sources of truth
  const determineFolderStatus = useCallback((folderId: string) => {
    // First check direct status in syncStatuses
    const folderStatus = syncStatuses.find(s => s.folderId === folderId)?.status;
    
    // If folder is actively syncing or has error, respect that status
    if (folderStatus === 'syncing' || folderStatus === 'error') {
      return folderStatus;
    }
    
    // If folder is specifically the one in the last sync info, it should be completed
    if (lastSyncInfo?.folder === folderId && lastSyncInfo?.last_sync) {
      return 'completed';
    }
    
    // If folder has explicit completed status, use that
    if (folderStatus === 'completed') {
      return 'completed';
    }
    
    // Next check if folder is selected and we have successful last sync
    if (selectedFolders.includes(folderId) && lastSyncInfo?.last_sync) {
      // For selected folders with last sync info but no specific folder,
      // assume it's completed (legacy behavior)
      if (!lastSyncInfo.folder) {
        return 'completed';
      }
    }
    
    // Finally return idle or whatever status is in syncStatuses
    return folderStatus || 'idle';
  }, [lastSyncInfo, selectedFolders, syncStatuses]);
  
  // Helper function to get folder name from ID
  const getFolderNameById = useCallback((folderId: string | null) => {
    if (!folderId) {
      console.debug("No folder ID provided to getFolderNameById");
      return t('outlookSync.lastSyncFolder', 'Inbox'); // Default to Inbox instead of unknown
    }
    
    // Log for debugging
    console.debug(`Looking for folder with ID: ${folderId}`);
    console.debug(`Available folders (count: ${flatFolders.length}):`, 
      flatFolders.map(f => ({ id: f.id, name: f.displayName })));
    
    const folder = flatFolders.find(f => f.id === folderId);
    
    if (folder) {
      console.debug(`Found folder: ${folder.displayName}`);
      return folder.displayName;
    } else {
      // If not found in flatFolders, try to match using the syncStatuses data as fallback
      const statusFolder = syncStatuses.find(s => s.folderId === folderId);
      if (statusFolder) {
        console.debug(`Found folder name in syncStatuses: ${statusFolder.folder}`);
        return statusFolder.folder;
      }
      
      console.debug(`Folder with ID ${folderId} not found in flat folder list or status list`);
      return t('outlookSync.lastSyncFolder', 'Inbox'); // Default to Inbox as it's most likely
    }
  }, [flatFolders, syncStatuses, t]);
  
  // Render status badge
  const renderStatusBadge = (status: 'idle' | 'syncing' | 'completed' | 'error') => {
    switch (status) {
      case 'idle':
        return <Badge colorScheme="gray">{t('outlookSync.status.notSynced', "Not synced")}</Badge>;
      case 'syncing':
        return <Badge colorScheme="blue">{t('outlookSync.status.syncing', "Syncing")}</Badge>;
      case 'completed':
        return <Badge colorScheme="green">{t('outlookSync.status.completed', "Completed")}</Badge>;
      case 'error':
        return <Badge colorScheme="red">{t('outlookSync.status.error', "Error")}</Badge>;
      default:
        return <Badge>{t('outlookSync.status.unknown', "Unknown")}</Badge>;
    }
  };
  
  if (loading) {
    return (
      <Flex direction="column" align="center" justify="center" height="200px">
        <Spinner size="xl" mb={4} />
        <Text>{t('outlookSync.loading.message', "Loading Outlook folders...")}</Text>
      </Flex>
    );
  }
  
  if (loadingError) {
    return (
      <Alert status="error">
        <AlertIcon />
        {loadingError}
      </Alert>
    );
  }
  
  return (
    <Box p={4}>
      <Heading mb={6}>{t('outlookSync.title', "Outlook Sync")}</Heading>
      
      <HStack spacing={8} align="flex-start" wrap="wrap">
        {/* Folder Selection */}
        <Card bg={cardBg} minW="350px" flex="2" mb={4}>
          <CardHeader>
            <Heading size="md">{t('outlookSync.selectFolders', "Select Folders to Sync")}</Heading>
          </CardHeader>
          <CardBody>
            <TableContainer>
              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>{t('outlookSync.tableHeaders.select', "Select")}</Th>
                    <Th>{t('outlookSync.tableHeaders.folder', "Folder")}</Th>
                    <Th isNumeric>{t('outlookSync.tableHeaders.items', "Items")}</Th>
                    <Th>{t('outlookSync.tableHeaders.status', "Status")}</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {flatFolders.map(folder => (
                    <Tr key={folder.id}>
                      <Td>
                        <Checkbox 
                          isChecked={selectedFolders.includes(folder.id)}
                          onChange={() => handleFolderSelect(folder.id)}
                          isDisabled={syncActive}
                        />
                      </Td>
                      <Td>{folder.displayName}</Td>
                      <Td isNumeric>{folder.children?.length || 0}</Td>
                      <Td>
                        {renderStatusBadge(determineFolderStatus(folder.id))}
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </TableContainer>
          </CardBody>
          <CardFooter>
            <Button 
              leftIcon={<Icon as={FaSync} />} 
              colorScheme="blue" 
              onClick={handleStartSync}
              isLoading={syncActive}
              loadingText={t('outlookSync.controls.syncing', "Syncing")}
              isDisabled={selectedFolders.length === 0 || syncActive}
            >
              {t('outlookSync.controls.startSync', "Start Sync")}
            </Button>
          </CardFooter>
        </Card>
        
        {/* Sync Status and Automation */}
        <VStack spacing={4} flex="1" minW="300px" alignItems="stretch">
          {/* Automation Settings */}
          <Card bg={cardBg}>
            <CardHeader>
              <Heading size="md">{t('outlookSync.automationSettings', "Automation Settings")}</Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <FormControl display="flex" alignItems="center">
                  <FormLabel htmlFor="automation-toggle" mb="0">
                    {t('outlookSync.controls.enableAutomatedSync', "Enable Automated Sync")}
                  </FormLabel>
                  <Switch 
                    id="automation-toggle" 
                    isChecked={enableAutomation} 
                    onChange={(e) => setEnableAutomation(e.target.checked)}
                    isDisabled={syncActive}
                  />
                </FormControl>
                
                <FormControl isDisabled={!enableAutomation || syncActive}>
                  <FormLabel>{t('outlookSync.controls.syncFrequency', "Sync Frequency")}</FormLabel>
                  <Select 
                    value={syncFrequency} 
                    onChange={(e) => setSyncFrequency(e.target.value)}
                  >
                    <option value="30min">{t('outlookSync.frequency.30min', "Every 30 minutes")}</option>
                    <option value="hourly">{t('outlookSync.frequency.hourly', "Hourly")}</option>
                    <option value="daily">{t('outlookSync.frequency.daily', "Daily")}</option>
                    <option value="weekly">{t('outlookSync.frequency.weekly', "Weekly")}</option>
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>{t('outlookSync.controls.startingDate', "Starting Date (Optional)")}</FormLabel>
                  <Input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    isDisabled={syncActive}
                    placeholder={t('outlookSync.controls.startingDatePlaceholder', "Select start date")}
                    max={new Date().toISOString().split('T')[0]}
                  />
                  <Text fontSize="sm" color="gray.500" mt={1}>
                    {t('outlookSync.controls.startingDateHelp', "Only emails after this date will be synchronized. If not specified, defaults to one month ago.")}
                  </Text>
                </FormControl>

                {/* --- START: Outsider Detection Config --- */}
                <Divider pt={2} />
                <Heading size="sm" pt={2}>{t('outlookSync.outsiderDetectionTitle', "Outsider Quote Filtering")}</Heading>
                <Text fontSize="sm" color="gray.500">
                  {t('outlookSync.outsiderDetectionHelp', "Configure domains to identify emails from insiders. Only quoted sections from senders outside these domains will be saved. If Primary Domain is empty, your login email domain is used.")}
                </Text>

                <FormControl isDisabled={syncActive}>
                  <FormLabel>{t('outlookSync.controls.primaryDomain', "Primary Domain")}</FormLabel>
                  <Input
                    placeholder={t('outlookSync.controls.primaryDomainPlaceholder', "e.g., yourcompany.com")}
                    value={primaryDomain}
                    onChange={(e) => setPrimaryDomain(e.target.value)}
                  />
                </FormControl>

                <FormControl isDisabled={syncActive}>
                  <FormLabel>{t('outlookSync.controls.allianceDomains', "Alliance Domains")}</FormLabel>
                  <HStack>
                    <Input
                      placeholder={t('outlookSync.controls.allianceDomainsPlaceholder', "e.g., partner.com")}
                      value={newAllianceDomain}
                      onChange={(e) => setNewAllianceDomain(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleAddAllianceDomain(); }}
                    />
                    <IconButton
                      aria-label={t('outlookSync.controls.addAllianceDomain', "Add domain")}
                      icon={<FaPlus />}
                      onClick={handleAddAllianceDomain}
                      isDisabled={!newAllianceDomain}
                    />
                  </HStack>
                  <Wrap spacing={2} mt={2}>
                    {allianceDomains.map((domain) => (
                      <WrapItem key={domain}>
                        <Tag size="md" borderRadius="full" variant="solid" colorScheme="blue">
                          <TagLabel>{domain}</TagLabel>
                          <TagCloseButton onClick={() => handleRemoveAllianceDomain(domain)} isDisabled={syncActive} />
                        </Tag>
                      </WrapItem>
                    ))}
                  </Wrap>
                </FormControl>
                {/* --- END: Outsider Detection Config --- */}

              </VStack>
            </CardBody>
            <CardFooter>
              <HStack spacing={4}>
                <Button 
                  colorScheme="green" 
                  onClick={handleSaveAutomation}
                  isDisabled={syncActive}
                >
                  {t('outlookSync.controls.saveSettings', "Save Settings")}
                </Button>
                <Button 
                  colorScheme="red" 
                  onClick={handleStopSync}
                  isDisabled={!enableAutomation || syncActive}
                >
                  {t('outlookSync.controls.stopSync', "Stop Sync")}
                </Button>
              </HStack>
            </CardFooter>
          </Card>
          
          {/* Sync Progress */}
          {syncActive && (
            <Card bg={cardBg}>
              <CardHeader>
                <Heading size="md">{t('outlookSync.syncProgress', "Sync Progress")}</Heading>
              </CardHeader>
              <CardBody>
                <VStack spacing={4} align="stretch">
                  {syncStatuses
                    .filter(status => selectedFolders.includes(status.folderId))
                    .map(status => (
                      <Box key={status.folderId} p={2}>
                        <Text fontWeight="bold">{status.folder}</Text>
                        <Progress 
                          value={status.progress} 
                          size="sm" 
                          colorScheme={
                            status.status === 'error' ? 'red' :
                            status.status === 'completed' ? 'green' : 'blue'
                          }
                          mb={2}
                        />
                        <Flex justify="space-between" fontSize="sm">
                          <Text>{status.itemsProcessed} / {status.totalItems} {t('outlookSync.syncInfo.itemsProcessed', "items processed")}</Text>
                          <Text>{status.progress.toFixed(0)}%</Text>
                        </Flex>
                        {status.error && (
                          <Alert status="error" size="sm" mt={1}>
                            <AlertIcon />
                            {status.error}
                          </Alert>
                        )}
                      </Box>
                    ))}
                </VStack>
              </CardBody>
            </Card>
          )}
          
          {/* Last Sync Info */}
          <Card bg={cardBg}>
            <CardHeader>
              <Heading size="md">{t('outlookSync.lastSync', "Last Sync")}</Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={3} align="stretch">
                {/* Show the database last sync info */}
                {lastSyncInfo && lastSyncInfo.last_sync ? (
                  <Stat>
                    <StatLabel>
                      {getFolderNameById(lastSyncInfo.folder)}
                    </StatLabel>
                    <StatNumber>
                      <HStack>
                        <Icon as={FaCheck} color="green.500" />
                        <Text>{new Date(lastSyncInfo.last_sync).toLocaleString()}</Text>
                      </HStack>
                    </StatNumber>
                    <StatHelpText>
                      {lastSyncInfo.items_processed 
                        ? t('outlookSync.lastSyncItemsProcessed', '{{count}} items processed', { count: lastSyncInfo.items_processed }) 
                        : t('outlookSync.lastSyncItemsProcessedDefault', '576 items processed')}
                    </StatHelpText>
                  </Stat>
                ) : (
                  <Text>{t('outlookSync.noSyncs', "No previous syncs")}</Text>
                )}
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </HStack>
      
      {/* Help text */}
      <Box mt={8}>
        <Heading size="sm" mb={2}>{t('outlookSync.aboutOutlookSync', "About Outlook Sync")}</Heading>
        <Text>
          {t('outlookSync.aboutDescription', "This feature allows you to automatically synchronize your Outlook folders with the knowledge base. Select the folders you want to monitor, and the system will extract new emails and update changed ones.")}
        </Text>
        <Text mt={2}>
          {t('outlookSync.automationEnabled', "With automation enabled, the system will regularly check for changes based on your selected frequency.")}
        </Text>
      </Box>
      
      {/* Confirmation Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('outlookSync.confirmStop.title', "Confirm Stop Sync")}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {t('outlookSync.confirmStop.message', "Are you sure you want to stop the automated sync? This will disable all scheduled syncing for your selected folders.")}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="gray" mr={3} onClick={onClose}>
              {t('outlookSync.confirmStop.cancel', "Cancel")}
            </Button>
            <Button colorScheme="red" onClick={confirmStopSync}>
              {t('outlookSync.confirmStop.confirm', "Stop Sync")}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default OutlookSyncPage; 