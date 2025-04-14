import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Heading,
  Container,
  Text,
  useColorModeValue,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  Button,
  Link as ChakraLink,
  Select,
  HStack,
  Icon,
  VStack,
  Divider,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Skeleton,
  useToast,
  IconButton,
  Tag,
  List,
  ListItem,
  Progress,
  Tabs, TabList, Tab, TabPanels, TabPanel,
  Input, 
  FormControl, 
  FormLabel, 
  FormHelperText,
  Stack,
  useDisclosure,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink } from 'react-router-dom';
import {
  getS3Config,
  listS3Buckets,
  listS3Objects,
  S3Config,
  S3Bucket,
  S3Object,
  triggerS3Ingestion,
  TriggerIngestResponse,
  getS3SyncList,
  addS3SyncItem,
  removeS3SyncItem,
  S3SyncItem,
  S3SyncItemCreate,
  configureS3,
  clearS3Config
} from '../api/s3';
import { getTaskStatus } from '../api/tasks';
import { TaskStatusEnum, TaskStatus as TaskStatusInterface } from '../models/tasks';
import { FaAws, FaFolder, FaFileAlt, FaSync, FaPlusCircle, FaCheckCircle, FaTrashAlt, FaHistory, FaCheck, FaExclamationTriangle } from 'react-icons/fa';
import { ChevronRightIcon } from '@chakra-ui/icons';

const formatDateTime = (dateTimeString?: string): string => {
  if (!dateTimeString) return '-';
  try {
    return new Date(dateTimeString).toLocaleString();
  } catch {
    return dateTimeString;
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

const ItemTableSkeleton = () => (
  <TableContainer>
    <Table variant="simple">
      <Thead>
        <Tr>
          <Th width="40%" textAlign="left"><Skeleton height="20px" /></Th>
          <Th width="30%" textAlign="left"><Skeleton height="20px" /></Th>
          <Th isNumeric width="15%"><Skeleton height="20px" /></Th>
           <Th width="15%" textAlign="center"><Skeleton height="20px" /></Th>
        </Tr>
      </Thead>
      <Tbody>
        {[...Array(5)].map((_, index) => (
          <Tr key={index}>
            <Td width="40%" textAlign="left"><Skeleton height="20px" width="80%" /></Td>
            <Td width="30%" textAlign="left"><Skeleton height="20px" width="60%" /></Td>
            <Td isNumeric width="15%"><Skeleton height="20px" width="40px" /></Td>
            <Td width="15%" textAlign="center"><Skeleton height="20px" width="40px" /></Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  </TableContainer>
);

interface SyncListComponentProps {
  items: S3SyncItem[];
  onRemoveItem: (itemId: number) => Promise<void>;
  onProcessList: () => void;
  isProcessing: boolean;
  isLoading: boolean;
  error: string | null;
  t: (key: string, options?: any) => string;
}

const S3SyncListComponent: React.FC<SyncListComponentProps> = ({ 
  items, onRemoveItem, onProcessList, isProcessing, isLoading, error, t 
}) => {
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');

  const pendingItems = items.filter(item => item.status === 'pending');

  const renderContent = () => {
    if (isLoading) {
      return <Center p={5}><Spinner /></Center>;
    }
    if (error) {
      return <Center p={5}><Text color="red.500" textAlign="center" width="100%">{t('s3Browser.errors.loadSyncListError', 'Error loading sync list')}: {error}</Text></Center>;
    }
    if (pendingItems.length === 0) {
      return <Center p={5}><Text color="gray.500" textAlign="center" width="100%">{t('s3Browser.syncListEmpty', 'Your sync list is empty. Browse S3 and add files/folders.')}</Text></Center>;
    }
    return (
      <List spacing={3} p={2}>
        {pendingItems.map((item) => (
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
                 <Text fontSize="sm" fontWeight="medium" noOfLines={1} title={item.s3_key} width="100%" textAlign="left">
                  {item.item_name || item.s3_key} 
                 </Text>
                 <Text fontSize="xs" color="gray.500" noOfLines={1} title={item.s3_bucket} width="100%" textAlign="left">
                   Bucket: {item.s3_bucket}
                 </Text>
              </VStack>
            </HStack>
            <IconButton
              aria-label={t('common.remove', 'Remove')}
              icon={<FaTrashAlt />}
              size="sm"
              variant="ghost"
              colorScheme="red"
              onClick={() => onRemoveItem(item.id)}
              isDisabled={isProcessing}
              flexShrink={0}
            />
          </ListItem>
        ))}
      </List>
    );
  };

  return (
    <Box mt={6} borderWidth="1px" borderRadius="lg" bg={bgColor} shadow="base">
      <VStack align="stretch">
        <HStack justify="space-between" p={4} borderBottomWidth="1px">
          <Heading size="md">{t('s3Browser.syncListTitle', 'S3 Sync List')}</Heading>
          <Tag size="md" variant='solid' colorScheme='blue'>
            {t('s3Browser.pendingCount', { count: pendingItems.length })}
          </Tag>
        </HStack>
        <Box maxHeight="300px" overflowY="auto">
           {renderContent()}
        </Box>
        <HStack justify="flex-end" p={4} borderTopWidth="1px">
           <Button
              leftIcon={<FaSync />}
              colorScheme="orange"
              onClick={onProcessList}
              isDisabled={isProcessing || pendingItems.length === 0}
              isLoading={isProcessing}
              loadingText={t('s3Browser.ingestingButton', 'Processing...')}
            >
              {t('s3Browser.processSyncListButton', 'Process Sync List')}
           </Button>
        </HStack>
      </VStack>
    </Box>
  );
};

interface HistoryListComponentProps {
  items: S3SyncItem[];
  isLoading: boolean;
  error: string | null;
  t: (key: string, options?: any) => string;
}

const S3HistoryListComponent: React.FC<HistoryListComponentProps> = ({ 
  items, isLoading, error, t 
}) => {
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');
  const successColor = useColorModeValue('green.600', 'green.300');
  const errorColor = useColorModeValue('red.600', 'red.300');

  const renderContent = () => {
    if (isLoading) {
      return <Center p={5}><Spinner /></Center>;
    }
    if (error) {
      return <Center p={5}><Text color="red.500" textAlign="center" width="100%">{t('s3Browser.errors.loadHistoryError', 'Error loading history')}: {error}</Text></Center>;
    }
    if (items.length === 0) {
      return <Center p={5}><Text color="gray.500" textAlign="center" width="100%">{t('s3Browser.historyEmpty', 'No processed items found in history.')}</Text></Center>;
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
                 <Text fontSize="sm" fontWeight="medium" noOfLines={1} title={item.s3_key} width="100%" textAlign="left">
                  {item.item_name || item.s3_key} 
                 </Text>
                 <Text fontSize="xs" color="gray.500" noOfLines={1} title={item.s3_bucket} width="100%" textAlign="left">
                   Bucket: {item.s3_bucket}
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
               {t(`s3Browser.status.${item.status}`, item.status)} 
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
          <Heading size="md">{t('s3Browser.historyListTitle', 'Processing History')}</Heading>
        </HStack>
        <Box maxHeight="400px" overflowY="auto">
           {renderContent()}
        </Box>
      </VStack>
    </Box>
  );
};

const S3Browser: React.FC = () => {
  const { t } = useTranslation();
  const bgColor = useColorModeValue('gray.50', 'gray.800');
  const headingColor = useColorModeValue('gray.700', 'white');
  const tableHoverBg = useColorModeValue('gray.100', 'gray.700');
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');
  const toast = useToast();

  const [isLoadingConfig, setIsLoadingConfig] = useState<boolean>(true);
  const [isConfigured, setIsConfigured] = useState<boolean>(false);
  const [isLoadingBuckets, setIsLoadingBuckets] = useState<boolean>(false);
  const [isLoadingObjects, setIsLoadingObjects] = useState<boolean>(false);
  const [buckets, setBuckets] = useState<S3Bucket[]>([]);
  const [selectedBucket, setSelectedBucket] = useState<string>('');
  const [currentPrefix, setCurrentPrefix] = useState<string>('');
  const [objects, setObjects] = useState<S3Object[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [syncList, setSyncList] = useState<S3SyncItem[]>([]);
  const [isLoadingSyncList, setIsLoadingSyncList] = useState<boolean>(true);
  const [syncListError, setSyncListError] = useState<string | null>(null);
  const [isProcessingSyncList, setIsProcessingSyncList] = useState<boolean>(false);

  const [ingestionTaskId, setIngestionTaskId] = useState<string | null>(null);
  const [isIngestionPolling, setIsIngestionPolling] = useState<boolean>(false);
  const [ingestionTaskStatus, setIngestionTaskStatus] = useState<TaskStatusInterface | null>(null);
  const [ingestionError, setIngestionError] = useState<string | null>(null);
  const ingestionPollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const [config, setConfig] = useState<S3Config | null>(null);
  const [currentRoleArn, setCurrentRoleArn] = useState<string>('');
  const [inputRoleArn, setInputRoleArn] = useState<string>('');
  const [isSavingConfig, setIsSavingConfig] = useState<boolean>(false);
  const [configError, setConfigError] = useState<string | null>(null);

  const { isOpen: isClearConfirmOpen, onOpen: onClearConfirmOpen, onClose: onClearConfirmClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const pendingSyncItems = React.useMemo(() => 
    syncList.filter(item => item.status === 'pending'), 
  [syncList]);

  const historySyncItems = React.useMemo(() => 
    syncList.filter(item => item.status === 'completed' || item.status === 'failed')
    .sort((a, b) => b.id - a.id), 
  [syncList]);

  const fetchS3SyncList = useCallback(async () => {
    setIsLoadingSyncList(true);
    setSyncListError(null);
    try {
      const fetchedList = await getS3SyncList();
      setSyncList(fetchedList);
    } catch (err: any) {
      console.error('Failed to fetch S3 sync list:', err);
      setSyncListError(t('s3Browser.errors.loadSyncListError', 'Failed to load sync list. Please try refreshing.'));
    } finally {
      setIsLoadingSyncList(false);
    }
  }, [t]);

  const checkConfig = useCallback(async () => {
    console.log("Checking S3 config...");
    setIsLoadingConfig(true);
    setConfigError(null);
    let configured = false; // Local variable to track status
    try {
      const fetchedConfig = await getS3Config();
      setConfig(fetchedConfig);
      const arn = fetchedConfig?.role_arn ?? '';
      setCurrentRoleArn(arn);
      setInputRoleArn(arn);
      configured = !!arn; // Determine status based on fetched ARN
      console.log("S3 Config fetched:", fetchedConfig, "Is Configured:", configured);
    } catch (err: any) {
      console.error("Failed to check S3 config:", err);
      const errorDetail = err.response?.data?.detail || err.message || 'Unknown error';
      setConfigError(t('s3Browser.errors.configCheckFailed', `Failed to check S3 configuration: ${errorDetail}` ));
      setConfig(null);
      setCurrentRoleArn('');
      setInputRoleArn('');
      configured = false; // Ensure it's false on error
    } finally {
      setIsConfigured(configured); // Set the state *after* check is complete
      setIsLoadingConfig(false);
    }
  }, [t]);

  useEffect(() => {
    const loadInitialData = async () => {
      await checkConfig();
      fetchS3SyncList(); 
    };
    loadInitialData();
  }, [checkConfig, fetchS3SyncList]);

  const fetchBuckets = useCallback(async () => {
    if (!isConfigured) {
      console.log("[fetchBuckets] Not configured, skipping fetch.");
      return; 
    }
    setIsLoadingBuckets(true);
    setError(null);
    setBuckets([]);
    setSelectedBucket('');
    setCurrentPrefix('');
    setObjects([]);
    try {
      const fetchedBuckets = await listS3Buckets();
      setBuckets(fetchedBuckets);
      if (fetchedBuckets && fetchedBuckets.length === 1) {
        console.log(`[S3 Load Buckets] Exactly one bucket found ('${fetchedBuckets[0].name}'). Auto-selecting.`);
        setSelectedBucket(fetchedBuckets[0].name);
      } else {
        console.log(`[S3 Load Buckets] Fetched ${fetchedBuckets.length} buckets. User needs to select.`);
      }
    } catch (err: any) {
      console.error('Failed to fetch S3 buckets:', err);
      const errorMsg = err.response?.data?.detail || err.message || t('s3Browser.errors.loadBucketsFailed', 'Failed to load S3 buckets. Check permissions or configuration.');
      setError(errorMsg);
    } finally {
      setIsLoadingBuckets(false);
    }
  }, [isConfigured, t]);

  useEffect(() => {
    if (isConfigured) {
      fetchBuckets();
    }
  }, [isConfigured, fetchBuckets]);

  const fetchObjects = useCallback(async () => {
    if (!selectedBucket) return;
    setIsLoadingObjects(true);
    setError(null);
    setObjects([]);
    try {
      console.log(`Fetching objects for bucket: ${selectedBucket}, prefix: '${currentPrefix}'`);
      const fetchedObjects = await listS3Objects(selectedBucket, currentPrefix);
      setObjects(fetchedObjects);
    } catch (err: any) {
      console.error(`Failed to fetch S3 objects for s3://${selectedBucket}/${currentPrefix}:`, err);
      const errorMsg = err.response?.data?.detail || err.message || t('s3Browser.errors.loadObjectsFailed', 'Failed to load objects. Check permissions or try again.');
      setError(errorMsg);
    } finally {
      setIsLoadingObjects(false);
    }
  }, [selectedBucket, currentPrefix, t]);

  useEffect(() => {
    if (selectedBucket) {
      setCurrentPrefix('');
      fetchObjects();
    } else {
      setObjects([]);
      setCurrentPrefix('');
    }
  }, [selectedBucket]);

  useEffect(() => {
    if (selectedBucket) {
      fetchObjects();
    }
  }, [currentPrefix]);

  const handleNavigate = (key: string) => {
    if (key.endsWith('/')) {
      setCurrentPrefix(key);
    }
  };

  const handleBreadcrumbClick = (index: number) => {
    if (isLoadingObjects) return;
    const prefixParts = currentPrefix.split('/').filter(p => p);
    const newPrefix = prefixParts.slice(0, index).join('/') + (index > 0 ? '/' : '');
    setCurrentPrefix(newPrefix);
  };

  const stopIngestionPolling = useCallback(() => {
    console.log('[S3 Polling] stopIngestionPolling called.');
    if (ingestionPollingIntervalRef.current) {
      console.log('[S3 Polling] Clearing interval.');
      clearInterval(ingestionPollingIntervalRef.current);
      ingestionPollingIntervalRef.current = null;
    }
    console.log('[S3 Polling] Setting isProcessingSyncList to false.');
    setIsProcessingSyncList(false);
  }, [setIsProcessingSyncList]);

  const pollIngestionTaskStatus = useCallback(async (taskId: string) => {
    if (!taskId) return;
    console.log(`[S3 Polling] Checking status for task ${taskId}...`);
    try {
      const statusResult: TaskStatusInterface = await getTaskStatus(taskId);
      console.log('[S3 Polling] Status received:', statusResult);
      setIngestionTaskStatus(statusResult);
      setIngestionError(null);

      const finalStates: string[] = [TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED, 'SUCCESS', 'FAILURE'];
      if (finalStates.includes(statusResult.status)) {
        console.log(`[S3 Polling] Task ${taskId} reached final state: ${statusResult.status}. Stopping.`);
        stopIngestionPolling();

        const isSuccess = statusResult.status === TaskStatusEnum.COMPLETED || statusResult.status === 'SUCCESS';
        toast({
          title: isSuccess ? t('common.success') : t('common.error'),
          description: statusResult.message || (isSuccess ? t('common.taskCompleted') : t('common.taskFailed')),
          status: isSuccess ? 'success' : 'error',
          duration: 7000,
          isClosable: true,
        });
        fetchS3SyncList(); 
      }
    } catch (error: any) {
      console.error(`[S3 Polling] Error fetching status for task ${taskId}:`, error);
      const errorMsg = `Polling failed: ${error.message}`;
      setIngestionError(errorMsg);
      setIngestionTaskStatus(prev => prev ? { ...prev, status: TaskStatusEnum.POLLING_ERROR } : { task_id: taskId, status: TaskStatusEnum.POLLING_ERROR, progress: null, message: errorMsg });
      stopIngestionPolling();
      toast({ title: t('errors.errorPollingStatus'), description: error.message, status: 'error' });
    }
  }, [stopIngestionPolling, t, toast, fetchS3SyncList]); 

  const startIngestionPolling = useCallback((taskId: string) => {
    stopIngestionPolling();
    console.log(`[S3 Polling] Starting polling for task ${taskId}...`);
    setIngestionTaskId(taskId);
    setIsIngestionPolling(true);
    setIsProcessingSyncList(true);
    setIngestionError(null);
    setIngestionTaskStatus({ task_id: taskId, status: TaskStatusEnum.PENDING, progress: 0, message: 'Ingestion task submitted, starting...' });
    pollIngestionTaskStatus(taskId);
    ingestionPollingIntervalRef.current = setInterval(() => pollIngestionTaskStatus(taskId), 5000);
  }, [stopIngestionPolling, pollIngestionTaskStatus]);

  useEffect(() => {
      return () => {
          stopIngestionPolling();
      };
  }, [stopIngestionPolling]);

  const handleAddSyncItem = useCallback(async (s3Object: S3Object) => {
    if (!selectedBucket) return;

    let itemName = s3Object.key.split('/').filter(Boolean).pop() || s3Object.key;
    if (s3Object.is_folder && !itemName.endsWith('/')) {
        itemName += '/';
    }
    
    const itemData: S3SyncItemCreate = {
      item_type: s3Object.is_folder ? 'prefix' : 'file',
      s3_bucket: selectedBucket,
      s3_key: s3Object.key,
      item_name: itemName, 
    };

    try {
      const addedItem = await addS3SyncItem(itemData);
      setSyncList(prev => {
          const exists = prev.some(item => item.id === addedItem.id);
          return exists ? prev : [...prev, addedItem];
      });
      toast({ 
          title: t('s3Browser.itemAddedToSync', { name: itemName }), 
          status: 'success', 
          duration: 2000 
      });
    } catch (error: any) {
        console.error(`Error adding item ${s3Object.key} to sync list:`, error);
        toast({ 
            title: t('errors.errorAddingItem'), 
            description: error.response?.data?.detail || error.message || t('errors.unknown'), 
            status: 'error' 
        });
    }
  }, [selectedBucket, t, toast, setSyncList]);

  const handleRemoveSyncItem = useCallback(async (itemId: number) => {
      const itemToRemove = syncList.find(i => i.id === itemId);
      if (!itemToRemove) return;
      try {
          await removeS3SyncItem(itemId);
          setSyncList(prev => prev.filter(i => i.id !== itemId));
          toast({ 
              title: t('s3Browser.itemRemovedFromSync', { name: itemToRemove.item_name }), 
              status: 'info', 
              duration: 2000 
          });
      } catch (error: any) {
          console.error(`Error removing sync item ${itemId}:`, error);
          toast({ 
              title: t('errors.errorRemovingItem'), 
              description: error.response?.data?.detail || error.message || t('errors.unknown'), 
              status: 'error' 
          });
      }
  }, [syncList, t, toast, setSyncList]);

  const handleProcessSyncList = useCallback(async () => {
      setIsProcessingSyncList(true);
      setIngestionError(null);
      setIngestionTaskStatus(null);
      try {
          const response: TriggerIngestResponse = await triggerS3Ingestion();
          if (response.task_id) {
             toast({ title: t('s3Browser.syncProcessStartedTitle'), description: response.message, status: 'info', duration: 5000 });
             startIngestionPolling(response.task_id);
          } else {
             toast({ title: t('s3Browser.syncListEmptyTitle'), description: response.message, status: 'warning', duration: 3000 });
             setIsProcessingSyncList(false);
          }
      } catch (error: any) {
          console.error('Error triggering S3 ingestion:', error);
          toast({ title: t('errors.errorStartingTask'), description: error.response?.data?.detail || error.message, status: 'error' });
          setIsProcessingSyncList(false);
          setIngestionError(error.response?.data?.detail || error.message || 'Failed to start task');
      }
  }, [t, toast, startIngestionPolling]);

  const isInSyncList = useCallback((s3ObjectKey: string) => {
      return syncList.some(item => item.s3_bucket === selectedBucket && item.s3_key === s3ObjectKey);
  }, [syncList, selectedBucket]);

  const handleSaveConfig = async () => {
    setIsSavingConfig(true);
    setConfigError(null);
    try {
      if (!inputRoleArn.startsWith("arn:aws:iam::") || !inputRoleArn.includes(":role/")) {
        throw new Error(t('s3Browser.errors.invalidArnFormat', 'Invalid AWS Role ARN format.'));
      }
      
      const updatedConfig = await configureS3(inputRoleArn);
      setCurrentRoleArn(updatedConfig?.role_arn ?? '');
      setInputRoleArn(updatedConfig?.role_arn ?? '');
      setConfig(updatedConfig);
      toast({
        title: t('s3Browser.settings.saveSuccessTitle', 'Configuration Saved'),
        description: t('s3Browser.settings.saveSuccessDesc', 'AWS Role ARN updated successfully.'),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      setIsConfigured(true);
      fetchBuckets();
    } catch (err: any) {
      console.error("Failed to save S3 config:", err);
      const errorDetail = err.response?.data?.detail || err.message || 'Unknown error';
      setConfigError(t('s3Browser.settings.saveError', `Failed to save configuration: ${errorDetail}` ));
      toast({
        title: t('s3Browser.errors.configSaveFailedTitle', 'Save Failed'),
        description: t('s3Browser.settings.saveError', `Failed to save configuration: ${errorDetail}` ),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSavingConfig(false);
    }
  };

  const handleClearConfig = async () => {
    onClearConfirmClose();
    setIsSavingConfig(true);
    setConfigError(null);
    try {
      await clearS3Config();
      setCurrentRoleArn('');
      setInputRoleArn('');
      setConfig(null);
      toast({
        title: t('s3Browser.settings.clearSuccessTitle', 'Configuration Cleared'),
        description: t('s3Browser.settings.clearSuccessDesc', 'AWS Role ARN has been removed.'),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      setIsConfigured(false);
      setBuckets([]);
      setSelectedBucket('');
      setObjects([]);
      setCurrentPrefix('');
    } catch (err: any) {
      console.error("Failed to clear S3 config:", err);
      const errorDetail = err.response?.data?.detail || err.message || 'Unknown error';
      setConfigError(t('s3Browser.settings.clearError', `Failed to clear configuration: ${errorDetail}` ));
      toast({
        title: t('s3Browser.errors.configClearFailedTitle', 'Clear Failed'),
        description: t('s3Browser.settings.clearError', `Failed to clear configuration: ${errorDetail}` ),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSavingConfig(false);
    }
  };

  if (isLoadingConfig) {
    return (
      <Center py={10}>
        <Spinner size="xl" />
        <Text ml={4}>{t('s3Browser.loadingConfig', 'Checking S3 Configuration...')}</Text>
      </Center>
    );
  }

  if (error) {
    return (
      <Container maxW="container.xl" py={5}>
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          {error}
          {!isLoadingConfig && error.includes('load S3 buckets') && (
            <Button ml={4} size="sm" onClick={fetchBuckets} isLoading={isLoadingBuckets}>
              {t('common.retry', 'Retry')}
            </Button>
          )}
        </Alert>
      </Container>
    );
  }

  if (!isConfigured) {
    return (
      <Container maxW="container.xl" py={5}>
        <Alert status="warning" borderRadius="md" flexDirection={{ base: 'column', md: 'row' }} alignItems="center" justifyContent="space-between" p={4}>
          <Box display="flex" alignItems="center">
            <AlertIcon />
            <Text ml={2}>{t('s3Browser.notConfigured', 'AWS S3 integration is not configured. Please provide your IAM Role ARN.')}</Text>
          </Box>
          <Button 
            as={RouterLink} 
            to="/settings/s3" 
            colorScheme="orange" 
            variant="solid" 
            size="sm" 
            mt={{ base: 3, md: 0 }}
            ml={{ md: 4 }}
          >
            {t('s3Browser.configureButton', 'Configure S3')}
          </Button>
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxW="container.xl" py={5} bg={bgColor}>
      <Heading as="h1" size="lg" mb={4}>
        {t('s3Browser.title', 'S3 Browser')}
      </Heading>

      <Tabs isLazy variant="soft-rounded" colorScheme="blue" mt={6}>
        <TabList mb="1em">
          <Tab>{t('s3Browser.tabs.browseSync', 'Browse & Sync')}</Tab>
          <Tab>{t('s3Browser.tabs.history', 'History')}</Tab>
          <Tab>{t('s3Browser.tabs.settings', 'Settings')}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel p={0}>
            <VStack spacing={4} align="stretch">
              <HStack spacing={4}>
                <Icon as={FaAws} boxSize="1.8em" color="orange.400" />
                <Select
                  placeholder={t('s3Browser.selectBucketPlaceholder', 'Select a Bucket...')}
                  value={selectedBucket}
                  onChange={(e) => setSelectedBucket(e.target.value)}
                  isDisabled={isLoadingBuckets || buckets.length === 0}
                  maxW={{ base: "100%", md: "400px" }}
                  bg={useColorModeValue('white', 'gray.700')}
                >
                  {buckets.map((bucket) => (
                    <option key={bucket.name} value={bucket.name}>
                      {bucket.name}
                    </option>
                  ))}
                </Select>
                {isLoadingBuckets && <Spinner size="sm" />}
              </HStack>

              <Divider />

              {selectedBucket && (
                <VStack spacing={4} align="stretch">
                  <Breadcrumb spacing='8px' separator={<ChevronRightIcon color='gray.500' />} fontSize="sm" width="100%" textAlign="left">
                    <BreadcrumbItem>
                      <BreadcrumbLink onClick={() => handleBreadcrumbClick(0)} isCurrentPage={currentPrefix === ''} fontWeight={currentPrefix === '' ? 'bold' : 'normal'} textAlign="left">
                        {selectedBucket}
                      </BreadcrumbLink>
                    </BreadcrumbItem>
                    {currentPrefix.split('/').filter(p => p).map((part, index, arr) => (
                      <BreadcrumbItem key={index} isCurrentPage={index === arr.length - 1}>
                        <BreadcrumbLink onClick={() => handleBreadcrumbClick(index + 1)} fontWeight={index === arr.length - 1 ? 'bold' : 'normal'} textAlign="left">
                          {part}
                        </BreadcrumbLink>
                      </BreadcrumbItem>
                    ))}
                  </Breadcrumb>

                  <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
                    {isLoadingObjects ? (
                      <ItemTableSkeleton />
                    ) : (
                      <TableContainer>
                        <Table variant='simple'>
                          <Thead>
                            <Tr>
                              <Th width="40%" textAlign="left">{t('common.name', 'Name')}</Th>
                              <Th width="30%" textAlign="left">{t('common.lastModified', 'Last Modified')}</Th>
                              <Th isNumeric width="15%">{t('common.size', 'Size')}</Th>
                              <Th width="15%" textAlign="center">{t('s3Browser.syncAction', 'Sync')}</Th>
                            </Tr>
                          </Thead>
                          <Tbody>
                            {objects.length === 0 && (
                              <Tr>
                                <Td colSpan={4} textAlign="center">
                                  <Text width="100%" textAlign="center">{t('s3Browser.emptyFolder', 'This location is empty.')}</Text>
                                </Td>
                              </Tr>
                            )}
                            {objects.map((obj) => {
                              const alreadyInList = isInSyncList(obj.key);
                              const currentlyDisabled = alreadyInList || isProcessingSyncList;
                              return (
                                <Tr key={obj.key} _hover={{ bg: tableHoverBg }}>
                                  <Td
                                    onClick={() => obj.is_folder && handleNavigate(obj.key)}
                                    cursor={obj.is_folder ? 'pointer' : 'default'}
                                    title={obj.key.substring(currentPrefix.length)}
                                    textAlign="left"
                                    width="40%"
                                  >
                                    <HStack spacing={2} width="100%">
                                      <Icon
                                        as={obj.is_folder ? FaFolder : FaFileAlt}
                                        color={obj.is_folder ? folderColor : fileColor}
                                        boxSize="1.2em"
                                        flexShrink={0}
                                      />
                                      <Text noOfLines={1} textAlign="left" width="100%">
                                        {obj.key.substring(currentPrefix.length) || (obj.is_folder ? obj.key : obj.key.split('/').pop())}
                                      </Text>
                                    </HStack>
                                  </Td>
                                  <Td textAlign="left" width="30%">{formatDateTime(obj.last_modified)}</Td>
                                  <Td isNumeric width="15%">{formatFileSize(obj.size)}</Td>
                                  <Td width="15%" textAlign="center">
                                    <IconButton
                                      aria-label={alreadyInList ? t('s3Browser.alreadyInSyncList', 'Already in sync list') : t('s3Browser.addToSyncList', 'Add to sync list')}
                                      icon={alreadyInList ? <Icon as={FaCheckCircle} color="green.500" /> : <Icon as={FaPlusCircle} />}
                                      size="xs"
                                      colorScheme={alreadyInList ? "green" : "blue"}
                                      onClick={() => !alreadyInList && handleAddSyncItem(obj)}
                                      isDisabled={currentlyDisabled}
                                      title={alreadyInList ? t('s3Browser.alreadyInSyncList', 'Already in sync list') : t('s3Browser.addToSyncList', 'Add to sync list')}
                                    />
                                  </Td>
                                </Tr>
                              );
                            })}
                          </Tbody>
                        </Table>
                      </TableContainer>
                    )}
                  </Box>
                </VStack>
              )}

              {!selectedBucket && !isLoadingBuckets && (
                <Text color="gray.500" mt={4} textAlign="center" width="100%">{t('s3Browser.selectBucketPrompt', 'Please select a bucket above to view its contents.')}</Text>
              )}

              {(isIngestionPolling || ingestionTaskStatus) && ingestionTaskId && (
                <Box 
                  mt={4} p={4} borderWidth="1px" borderRadius="md" 
                  borderColor={
                    ingestionTaskStatus?.status === TaskStatusEnum.FAILED || ingestionTaskStatus?.status === TaskStatusEnum.POLLING_ERROR ? "red.300" : 
                    ingestionTaskStatus?.status === TaskStatusEnum.COMPLETED ? "green.300" : "blue.300"
                  } 
                  bg={useColorModeValue(
                    ingestionTaskStatus?.status === TaskStatusEnum.FAILED || ingestionTaskStatus?.status === TaskStatusEnum.POLLING_ERROR ? "red.50" : 
                    ingestionTaskStatus?.status === TaskStatusEnum.COMPLETED ? "green.50" : "blue.50", 
                    ingestionTaskStatus?.status === TaskStatusEnum.FAILED || ingestionTaskStatus?.status === TaskStatusEnum.POLLING_ERROR ? "red.900" : 
                    ingestionTaskStatus?.status === TaskStatusEnum.COMPLETED ? "green.900" : "blue.900"
                  )}
                  mb={4}
                >
                  <VStack spacing={2} align="stretch">
                    <HStack justify="space-between">
                      <Text fontSize="sm" fontWeight="bold">{t('s3Browser.ingestionTaskProgressTitle', 'S3 Ingestion Task')}</Text>
                      <Tag 
                          size="sm"
                          colorScheme={
                            ingestionTaskStatus?.status === TaskStatusEnum.COMPLETED ? 'green' :
                            ingestionTaskStatus?.status === TaskStatusEnum.FAILED || ingestionTaskStatus?.status === TaskStatusEnum.POLLING_ERROR ? 'red' : 
                            'blue'
                          }
                        >
                          {t(`s3Browser.status.${ingestionTaskStatus?.status?.toLowerCase() || 'pending'}`, ingestionTaskStatus?.status || 'Initializing...')}
                        </Tag>
                    </HStack>
                    <Text fontSize="xs">{t('common.taskID')} {ingestionTaskId}</Text>
                    {typeof ingestionTaskStatus?.progress === 'number' && (
                      <Progress 
                        value={ingestionTaskStatus.progress} size="xs" 
                        colorScheme={
                          ingestionTaskStatus?.status === TaskStatusEnum.FAILED || ingestionTaskStatus?.status === TaskStatusEnum.POLLING_ERROR ? 'red' : 
                          ingestionTaskStatus?.status === TaskStatusEnum.COMPLETED ? 'green' : 'blue'
                        } 
                        isAnimated={ingestionTaskStatus?.status === TaskStatusEnum.RUNNING || ingestionTaskStatus?.status === TaskStatusEnum.PENDING}
                        hasStripe={ingestionTaskStatus?.status === TaskStatusEnum.RUNNING || ingestionTaskStatus?.status === TaskStatusEnum.PENDING}
                        borderRadius="full"
                      />
                    )}
                    {(ingestionTaskStatus?.message || ingestionError) && (
                        <Text fontSize="xs" color={ingestionError ? "red.500" : "gray.500"} mt={1} noOfLines={2} title={ingestionError || ingestionTaskStatus?.message || undefined}>
                          {ingestionError || ingestionTaskStatus?.message}
                        </Text>
                    )}
                  </VStack>
                </Box>
              )}
              
              <S3SyncListComponent
                items={pendingSyncItems}
                onRemoveItem={handleRemoveSyncItem}
                onProcessList={handleProcessSyncList}
                isProcessing={isProcessingSyncList}
                isLoading={isLoadingSyncList}
                error={syncListError}
                t={t}
              />
            </VStack>
          </TabPanel>

          <TabPanel p={0}>
            <S3HistoryListComponent
              items={historySyncItems}
              isLoading={isLoadingSyncList} 
              error={syncListError} 
              t={t}
            />
          </TabPanel>

          <TabPanel p={4}>
            <Heading size="md" mb={4}>{t('s3Browser.settings.title', 'AWS S3 Configuration')}</Heading>
            {isLoadingConfig && <Center><Spinner /></Center>}
            {!isLoadingConfig && (
              <Stack spacing={4} maxWidth="xl">
                <FormControl>
                  <FormLabel htmlFor='roleArn'>{t('s3Browser.settings.roleArnLabel', 'IAM Role ARN')}</FormLabel>
                  <Input
                    id='roleArn'
                    placeholder='arn:aws:iam::123456789012:role/YourRoleName'
                    value={inputRoleArn}
                    onChange={(e) => setInputRoleArn(e.target.value)}
                    bg={useColorModeValue('gray.50', 'gray.650')}
                    isDisabled={isSavingConfig}
                  />
                  <FormHelperText>{t('s3Browser.settings.roleArnHelp', 'Enter the ARN of the IAM role this application should assume to access S3.')}</FormHelperText>
                </FormControl>

                {configError && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    {configError}
                  </Alert>
                )}

                <HStack justify="flex-end">
                  <Button 
                    variant="outline"
                    colorScheme="red"
                    onClick={onClearConfirmOpen}
                    isDisabled={!currentRoleArn || isSavingConfig}
                    isLoading={isSavingConfig && currentRoleArn === ''}
                  >
                    {t('s3Browser.settings.clearConfigButton', 'Clear Configuration')}
                  </Button>
                  <Button 
                    colorScheme="orange"
                    onClick={handleSaveConfig}
                    isLoading={isSavingConfig && currentRoleArn !== ''}
                    isDisabled={inputRoleArn === currentRoleArn || isSavingConfig}
                  >
                    {t('common.saveChanges', 'Save Changes')}
                  </Button>
                </HStack>
              </Stack>
            )}
          </TabPanel>
        </TabPanels>
      </Tabs>

      <AlertDialog
        isOpen={isClearConfirmOpen}
        leastDestructiveRef={cancelRef}
        onClose={onClearConfirmClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('s3Browser.settings.clearConfirmTitle', 'Clear S3 Configuration?')}
            </AlertDialogHeader>

            <AlertDialogBody>
              {t('s3Browser.settings.clearConfirmMsg', 'Are you sure you want to remove the configured AWS Role ARN? You will need to re-enter it to access S3 data.')}
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onClearConfirmClose}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button colorScheme="red" onClick={handleClearConfig} ml={3}>
                {t('common.confirmClear', 'Confirm Clear')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

    </Container>
  );
};

export default S3Browser; 