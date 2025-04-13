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
  Checkbox,
  useToast,
  IconButton,
  Tag,
  List,
  ListItem,
  CloseButton,
  Progress
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink } from 'react-router-dom';
import {
  getS3Config,
  listS3Buckets,
  listS3Objects,
  ingestS3Objects,
  S3Config,
  S3Bucket,
  S3Object
} from '../api/s3';
import { getTaskStatus } from '../api/tasks';
import { TaskStatusEnum, TaskStatus as TaskStatusInterface } from '../models/tasks';
import { FaAws, FaFolder, FaFileAlt, FaSync, FaTimes, FaPlusCircle, FaCheckCircle } from 'react-icons/fa';
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
          <Th><Skeleton height="20px" /></Th>
          <Th><Skeleton height="20px" /></Th>
          <Th isNumeric><Skeleton height="20px" /></Th>
        </Tr>
      </Thead>
      <Tbody>
        {[...Array(5)].map((_, index) => (
          <Tr key={index}>
            <Td><Skeleton height="20px" width="80%" /></Td>
            <Td><Skeleton height="20px" width="60%" /></Td>
            <Td isNumeric><Skeleton height="20px" width="40px" /></Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  </TableContainer>
);

interface SelectedItemsProps {
  selectedKeys: Set<string>;
  objects: S3Object[];
  currentPrefix: string;
  onRemove: (key: string) => void;
  onIngest: () => void;
  isIngesting: boolean;
  t: (key: string, options?: any) => string;
}

const SelectedItemsList: React.FC<SelectedItemsProps> = (
  { selectedKeys, objects, currentPrefix, onRemove, onIngest, isIngesting, t }
) => {
  if (selectedKeys.size === 0) {
    return null;
  }

  const selectedObjects = objects.filter(obj => selectedKeys.has(obj.key));

  return (
    <Box mt={6} p={4} borderWidth="1px" borderRadius="lg" bg={useColorModeValue('gray.50', 'gray.800')} shadow="sm">
      <VStack align="stretch" spacing={4}>
        <HStack justify="space-between">
          <Heading size="sm">{t('s3Browser.selectedListTitle', 'Selected for Ingestion')}</Heading>
          <Tag size="md" variant='solid' colorScheme='orange'>
            {t('s3Browser.selectedCount', { count: selectedKeys.size })}
          </Tag>
        </HStack>
        <Box maxHeight="200px" overflowY="auto" px={2}> 
          <List spacing={2}>
            {selectedObjects.map(obj => (
              <ListItem key={obj.key} display="flex" justifyContent="space-between" alignItems="center">
                <HStack spacing={2}>
                   <Icon 
                      as={obj.is_folder ? FaFolder : FaFileAlt} 
                      color={obj.is_folder ? useColorModeValue('blue.500', 'blue.300') : useColorModeValue('gray.600', 'gray.400')} 
                      boxSize="1.1em"
                    />
                   <Text fontSize="sm" noOfLines={1} title={obj.key}>
                    {obj.key.substring(currentPrefix.length) || obj.key}
                   </Text>
                </HStack>
                <IconButton 
                  aria-label={t('common.remove', 'Remove')}
                  icon={<Icon as={FaTimes} />} 
                  size="xs" 
                  variant="ghost"
                  colorScheme="red"
                  onClick={() => onRemove(obj.key)}
                  isDisabled={isIngesting}
                />
              </ListItem>
            ))}
          </List>
        </Box>
        <Button
          leftIcon={<FaSync />}
          colorScheme="orange"
          onClick={onIngest}
          isDisabled={isIngesting || selectedKeys.size === 0}
          isLoading={isIngesting}
          loadingText={t('s3Browser.ingestingButton', 'Ingesting...')}
          alignSelf="flex-end"
        >
          {t('s3Browser.ingestSelectedButton', 'Ingest Selected Items')}
        </Button>
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
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [isIngesting, setIsIngesting] = useState<boolean>(false);

  // +++ State for Ingestion Task Polling +++
  const [ingestionTaskId, setIngestionTaskId] = useState<string | null>(null);
  const [isIngestionPolling, setIsIngestionPolling] = useState<boolean>(false);
  const [ingestionTaskStatus, setIngestionTaskStatus] = useState<TaskStatusInterface | null>(null);
  const [ingestionError, setIngestionError] = useState<string | null>(null);
  const ingestionPollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  // +++ End Task Polling State +++

  useEffect(() => {
    const checkConfig = async () => {
      setIsLoadingConfig(true);
      setError(null);
      try {
        const config: S3Config = await getS3Config();
        setIsConfigured(!!config && !!config.role_arn);
      } catch (err) {
        console.error("Error checking S3 config:", err);
        setError(t('s3Browser.errors.configCheckFailed', 'Failed to check S3 configuration. Please ensure you are logged in and the backend is running.'));
        setIsConfigured(false);
      } finally {
        setIsLoadingConfig(false);
      }
    };
    checkConfig();
  }, [t]);

  const fetchBuckets = useCallback(async () => {
    if (!isConfigured) return;
    setIsLoadingBuckets(true);
    setError(null);
    setBuckets([]);
    setSelectedBucket('');
    setCurrentPrefix('');
    setObjects([]);
    try {
      const fetchedBuckets = await listS3Buckets();
      setBuckets(fetchedBuckets);
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
    if (selectedBucket && currentPrefix !== '') {
      fetchObjects();
    }
  }, [currentPrefix, fetchObjects]);

  useEffect(() => {
    if (selectedBucket) {
      const initialFetchDone = objects.length > 0 || !isLoadingObjects;
      if (initialFetchDone) {
        fetchObjects();
      }
    }
  }, [currentPrefix]);

  const handleNavigate = (key: string) => {
    if (key.endsWith('/')) {
      setCurrentPrefix(key);
    }
    setSelectedKeys(new Set());
  };

  const handleBreadcrumbClick = (index: number) => {
    if (isLoadingObjects) return;
    const prefixParts = currentPrefix.split('/').filter(p => p);
    const newPrefix = prefixParts.slice(0, index).join('/') + (index > 0 ? '/' : '');
    setCurrentPrefix(newPrefix);
    setSelectedKeys(new Set());
  };

  const handleCheckboxChange = (key: string, isChecked: boolean) => {
    setSelectedKeys(prev => {
      const newSet = new Set(prev);
      if (isChecked) {
        newSet.add(key);
      } else {
        newSet.delete(key);
      }
      return newSet;
    });
  };

  // +++ Polling Functions (similar to SharePoint) +++
  const stopIngestionPolling = useCallback(() => {
    if (ingestionPollingIntervalRef.current) {
      console.log('[S3 Polling] Stopping polling interval.');
      clearInterval(ingestionPollingIntervalRef.current);
      ingestionPollingIntervalRef.current = null;
    }
  }, []);

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
        setIsIngestionPolling(false); // Polling finished
        // Consider clearing ingestionTaskId here or leave it for display?
        // setIngestionTaskId(null);

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
      console.error(`[S3 Polling] Error fetching status for task ${taskId}:`, error);
      const errorMsg = `Polling failed: ${error.message}`;
      setIngestionError(errorMsg);
      setIngestionTaskStatus(prev => prev ? { ...prev, status: TaskStatusEnum.POLLING_ERROR } : { task_id: taskId, status: TaskStatusEnum.POLLING_ERROR, progress: null, message: errorMsg });
      stopIngestionPolling();
      setIsIngestionPolling(false);
      toast({ title: t('errors.errorPollingStatus'), description: error.message, status: 'error' });
    }
  }, [stopIngestionPolling, t, toast]);

  const startIngestionPolling = useCallback((taskId: string) => {
    stopIngestionPolling(); // Ensure no previous polling is running
    console.log(`[S3 Polling] Starting polling for task ${taskId}...`);
    setIngestionTaskId(taskId);
    setIsIngestionPolling(true);
    setIngestionError(null);
    // Set initial status while waiting for first poll
    setIngestionTaskStatus({ task_id: taskId, status: TaskStatusEnum.PENDING, progress: 0, message: 'Ingestion task submitted, starting...' });
    pollIngestionTaskStatus(taskId); // Poll immediately
    ingestionPollingIntervalRef.current = setInterval(() => pollIngestionTaskStatus(taskId), 5000); // Poll every 5 seconds
  }, [stopIngestionPolling, pollIngestionTaskStatus]);
  // +++ End Polling Functions +++

  // Cleanup polling on unmount
  useEffect(() => {
      return () => {
          stopIngestionPolling();
      };
  }, [stopIngestionPolling]);

  const handleIngest = async () => {
    if (!selectedBucket || selectedKeys.size === 0) {
      toast({
        title: t('s3Browser.toast.noSelectionTitle', 'Nothing Selected'),
        description: t('s3Browser.toast.noSelectionDescription', 'Please select at least one file or folder to ingest.'),
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsIngesting(true);
    setError(null);
    setIngestionError(null);
    setIngestionTaskStatus(null);
    setIngestionTaskId(null);
    
    try {
      const keysToIngest = Array.from(selectedKeys);
      console.log(`Submitting ingestion for bucket: ${selectedBucket}, keys:`, keysToIngest);
      const result = await ingestS3Objects(selectedBucket, keysToIngest);
      
      if (result && result.task_id) {
           toast({
             title: t('s3Browser.toast.ingestSubmittedTitle', 'Ingestion Submitted'),
             description: result.message || t('s3Browser.toast.ingestSubmittedDesc', 'Task submitted for background processing.'),
             status: 'info',
             duration: 5000,
             isClosable: true,
           });
           setSelectedKeys(new Set());
           startIngestionPolling(result.task_id);
      } else {
           console.warn("Ingestion endpoint did not return a task_id.", result);
           toast({
                title: t('common.warning', 'Warning'),
                description: result.message || t('s3Browser.errors.noTaskId', 'Ingestion started but could not get task ID for status tracking.'),
                status: 'warning',
                duration: 5000,
           });
           setSelectedKeys(new Set());
      }

    } catch (err: any) {
      console.error('Failed to submit S3 ingestion task:', err);
      const errorMsg = err.response?.data?.detail || err.message || t('s3Browser.errors.ingestFailed', 'Failed to submit ingestion task.');
      setError(errorMsg);
      toast({
        title: t('s3Browser.toast.ingestErrorTitle', 'Submission Failed'),
        description: errorMsg,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsIngesting(false);
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
      <VStack spacing={4} align="stretch">
        <Heading as="h1" size="lg" mb={2}>
          {t('s3Browser.title', 'S3 Browser')}
        </Heading>

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
            <Breadcrumb spacing='8px' separator={<ChevronRightIcon color='gray.500' />} fontSize="sm">
              <BreadcrumbItem>
                <BreadcrumbLink onClick={() => handleBreadcrumbClick(0)} isCurrentPage={currentPrefix === ''} fontWeight={currentPrefix === '' ? 'bold' : 'normal'}>
                  {selectedBucket}
                </BreadcrumbLink>
              </BreadcrumbItem>
              {currentPrefix.split('/').filter(p => p).map((part, index, arr) => (
                <BreadcrumbItem key={index} isCurrentPage={index === arr.length - 1}>
                  <BreadcrumbLink onClick={() => handleBreadcrumbClick(index + 1)} fontWeight={index === arr.length - 1 ? 'bold' : 'normal'}>
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
                        <Th>{t('common.name', 'Name')}</Th>
                        <Th>{t('common.lastModified', 'Last Modified')}</Th>
                        <Th isNumeric>{t('common.size', 'Size')}</Th>
                        <Th>{t('common.actions', 'Actions')}</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {objects.length === 0 && (
                        <Tr>
                          <Td colSpan={4} textAlign="center">
                            {t('s3Browser.emptyFolder', 'This location is empty.')}
                          </Td>
                        </Tr>
                      )}
                      {objects.map((obj) => {
                        const isSelected = selectedKeys.has(obj.key);
                        return (
                          <Tr key={obj.key} _hover={{ bg: tableHoverBg }}>
                            <Td
                              onClick={() => obj.is_folder && handleNavigate(obj.key)}
                              cursor={obj.is_folder ? 'pointer' : 'default'}
                              title={obj.key.substring(currentPrefix.length)}
                            >
                              <HStack>
                                <Icon
                                  as={obj.is_folder ? FaFolder : FaFileAlt}
                                  color={obj.is_folder ? folderColor : fileColor}
                                  boxSize="1.2em"
                                />
                                <Text noOfLines={1}>
                                  {obj.key.substring(currentPrefix.length)}
                                </Text>
                              </HStack>
                            </Td>
                            <Td>{formatDateTime(obj.last_modified)}</Td>
                            <Td isNumeric>{formatFileSize(obj.size)}</Td>
                            <Td>
                              <IconButton
                                aria-label={isSelected ? t('s3Browser.removeFromSelection', 'Remove from selection') : t('s3Browser.addToSelection', 'Add to selection')}
                                icon={isSelected ? <Icon as={FaCheckCircle} color="green.500" /> : <Icon as={FaPlusCircle} />}
                                size="sm"
                                variant="ghost"
                                onClick={() => handleCheckboxChange(obj.key, !isSelected)}
                                isDisabled={isIngesting}
                                title={isSelected ? t('s3Browser.removeFromSelection', 'Remove from selection') : t('s3Browser.addToSelection', 'Add to selection')}
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
          <Text color="gray.500" mt={4} textAlign="center">{t('s3Browser.selectBucketPrompt', 'Please select a bucket above to view its contents.')}</Text>
        )}

        {selectedBucket && !isLoadingObjects && (
           <SelectedItemsList
             selectedKeys={selectedKeys}
             objects={objects}
             currentPrefix={currentPrefix}
             onRemove={(key) => handleCheckboxChange(key, false)}
             onIngest={handleIngest}
             isIngesting={isIngesting}
             t={t}
           />
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
                      {ingestionTaskStatus?.status || 'Initializing...'}
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
      </VStack>
    </Container>
  );
};

export default S3Browser; 