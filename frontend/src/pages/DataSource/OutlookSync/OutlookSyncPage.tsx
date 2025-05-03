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
  useDisclosure
} from '@chakra-ui/react';
import { FaSync, FaCalendarAlt, FaEnvelope, FaFilter, FaClock, FaCheck, FaExclamationTriangle, FaFolder } from 'react-icons/fa';
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
  
  // For confirmation modal
  const { isOpen, onOpen, onClose } = useDisclosure();
  
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
  }, [toast, t]);
  
  // Fetch folders
  const fetchFolders = useCallback(async () => {
    try {
      setLoading(true);
      setLoadingError(null);
      
      const response = await apiClient.get('/v1/email/folders');
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
        setSelectedFolders(syncConfigResponse.data.folders || []);
        setSyncFrequency(syncConfigResponse.data.frequency || 'daily');
        setEnableAutomation(syncConfigResponse.data.enabled || false);
        setStartDate(syncConfigResponse.data.startDate || '');
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
      setLoadingError(t('outlookSync.loading.error', "Failed to load your Outlook folders. Please try again later."));
    } finally {
      setLoading(false);
    }
  }, [t]);
  
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
        description: t('outlookSync.notifications.syncStartedDesc', { count: selectedFolders.length }),
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
      await apiClient.post('/v1/email/sync/config', {
        enabled: enableAutomation,
        frequency: syncFrequency,
        folders: selectedFolders,
        startDate: startDate
      });
      
      toast({
        title: t('outlookSync.notifications.settingsSaved', "Settings saved"),
        description: enableAutomation 
          ? t('outlookSync.notifications.automationEnabled', { frequency: syncFrequency })
          : t('outlookSync.notifications.automationDisabled', "Automated sync disabled"),
        status: "success",
        duration: 5000,
        isClosable: true,
      });
    } catch (error) {
      console.error("Failed to save automation settings:", error);
      toast({
        title: t('outlookSync.notifications.saveError', "Failed to save"),
        description: t('outlookSync.notifications.saveErrorDesc', "Could not save automation settings"),
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
      if (prev.includes(folderId)) {
        return prev.filter(id => id !== folderId);
      } else {
        return [...prev, folderId];
      }
    });
  };
  
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
      <Box p={8} textAlign="center">
        <Spinner size="xl" />
        <Text mt={4}>{t('outlookSync.loading', "Loading your Outlook folders...")}</Text>
      </Box>
    );
  }
  
  if (loadingError) {
    return (
      <Box p={8}>
        <Alert status="error" mb={4}>
          <AlertIcon />
          {loadingError}
        </Alert>
        <Button leftIcon={<Icon as={FaSync} />} onClick={fetchFolders}>
          {t('common.retry', "Retry")}
        </Button>
      </Box>
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
                        {renderStatusBadge(syncStatuses.find(s => s.folderId === folder.id)?.status || 'idle')}
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
              {syncStatuses.some(s => s.lastSync) ? (
                <VStack spacing={3} align="stretch">
                  {syncStatuses
                    .filter(status => status.lastSync)
                    .map(status => (
                      <Stat key={status.folderId} size="sm">
                        <StatLabel>{status.folder}</StatLabel>
                        <StatNumber>
                          <HStack>
                            <Icon 
                              as={status.status === 'error' ? FaExclamationTriangle : FaCheck} 
                              color={status.status === 'error' ? 'red.500' : 'green.500'} 
                            />
                            <Text>{new Date(status.lastSync!).toLocaleString()}</Text>
                          </HStack>
                        </StatNumber>
                        <StatHelpText>
                          {status.itemsProcessed} {t('outlookSync.syncInfo.itemsProcessed', "items processed")}
                        </StatHelpText>
                      </Stat>
                    ))}
                </VStack>
              ) : (
                <Text>{t('outlookSync.noSyncs', "No previous syncs")}</Text>
              )}
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