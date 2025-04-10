import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Container,
  Heading,
  VStack,
  Text,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Progress,
  useToast,
  Spinner,
  useColorModeValue,
  HStack,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Button,
  Divider,
  SimpleGrid,
  Icon,
  Flex
} from '@chakra-ui/react';
import { FiRefreshCw, FiAlertCircle, FiCheckCircle, FiClock } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { getTaskStatus, getMyLatestKbTask, TaskStatus } from '../api/tasks';

// Mock interfaces - replace with actual API types
interface Task {
  id: string;
  type: string;
  status: 'running' | 'completed' | 'failed';
  progress: number;
  startTime: string;
  endTime?: string;
  error?: string;
  details: string;
}

const BackgroundTasksPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  
  const [activeTask, setActiveTask] = useState<TaskStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  // Function to fetch the latest active knowledge base task
  const fetchLatestTask = useCallback(async () => {
    try {
      const task = await getMyLatestKbTask();
      setActiveTask(task);
      return task;
    } catch (error) {
      toast({
        title: t('common.error'),
        description: t('tasks.fetchError'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [toast, t]);

  // Function to refresh tasks manually
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchLatestTask();
  }, [fetchLatestTask]);

  // Start polling for task updates when there's an active task
  useEffect(() => {
    const startPolling = async () => {
      // Clear any existing interval
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }

      // Check if there's an active task
      const task = await fetchLatestTask();
      
      // If there's an active task, start polling for updates
      if (task && ['PENDING', 'STARTED', 'PROGRESS', 'RECEIVED', 'RETRY'].includes(task.status)) {
        const interval = setInterval(async () => {
          try {
            const updatedTask = await getTaskStatus(task.task_id);
            setActiveTask(updatedTask);
            
            // If task is complete, stop polling
            if (['SUCCESS', 'FAILURE', 'REVOKED'].includes(updatedTask.status)) {
              if (pollingInterval) clearInterval(pollingInterval);
              setPollingInterval(null);
            }
          } catch (error) {
            console.error('Error polling task status:', error);
            // Stop polling on error
            if (pollingInterval) clearInterval(pollingInterval);
            setPollingInterval(null);
          }
        }, 3000); // Poll every 3 seconds
        
        setPollingInterval(interval);
        
        // Cleanup function
        return () => {
          if (interval) clearInterval(interval);
        };
      }
    };
    
    startPolling();
    
    // Cleanup when component unmounts
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [fetchLatestTask, pollingInterval]);

  // Helper function to render the status badge
  const renderStatusBadge = (status: string) => {
    let colorScheme = 'blue';
    let icon = FiClock;

    switch (status) {
      case 'SUCCESS':
        colorScheme = 'green';
        icon = FiCheckCircle;
        break;
      case 'FAILURE':
      case 'REVOKED':
        colorScheme = 'red';
        icon = FiAlertCircle;
        break;
      case 'PROGRESS':
        colorScheme = 'yellow';
        icon = FiClock;
        break;
      default:
        colorScheme = 'blue';
        icon = FiClock;
    }

    return (
      <Badge colorScheme={colorScheme} fontSize="sm" display="flex" alignItems="center" p={1} borderRadius="md">
        <Icon as={icon} mr={1} />
        {status}
      </Badge>
    );
  };

  if (loading) {
    return (
      <Container maxW="container.xl" py={8}>
        <Box textAlign="center" py={10}>
          <Spinner size="xl" />
        </Box>
      </Container>
    );
  }

  return (
    <Box p={5} maxW="1200px" mx="auto">
      <VStack spacing={5} align="stretch">
        <HStack justifyContent="space-between">
          <Heading size="lg">{t('tasks.title', 'Background Tasks')}</Heading>
          <Button 
            leftIcon={<FiRefreshCw />} 
            colorScheme="blue" 
            variant="outline" 
            onClick={handleRefresh}
            isLoading={refreshing}
            loadingText={t('common.refreshing')}
          >
            {t('common.refresh')}
          </Button>
        </HStack>
        
        <Divider />
        
        {loading ? (
          <Flex justify="center" align="center" height="200px">
            <Spinner size="xl" />
          </Flex>
        ) : !activeTask ? (
          <Card variant="outline">
            <CardBody>
              <Text align="center">{t('tasks.noActiveTasks', 'No active background tasks')}</Text>
            </CardBody>
          </Card>
        ) : (
          <Card variant="outline">
            <CardHeader>
              <HStack justifyContent="space-between">
                <Heading size="md">{t('tasks.taskId')}: {activeTask.task_id.substring(0, 8)}...</Heading>
                {renderStatusBadge(activeTask.status)}
              </HStack>
            </CardHeader>
            
            <CardBody>
              <VStack spacing={4} align="stretch">
                <SimpleGrid columns={2} spacing={4}>
                  <Box>
                    <Text fontWeight="bold">{t('tasks.status')}:</Text>
                    <Text>{activeTask.status}</Text>
                  </Box>
                  
                  <Box>
                    <Text fontWeight="bold">{t('tasks.type')}:</Text>
                    <Text>{t('tasks.knowledgeBaseProcessing', 'Knowledge Base Processing')}</Text>
                  </Box>
                </SimpleGrid>
                
                {activeTask.progress !== null && activeTask.progress !== undefined && (
                  <Box>
                    <Text mb={1}>{t('tasks.progress')}: {Math.round(activeTask.progress * 100)}%</Text>
                    <Progress value={activeTask.progress * 100} colorScheme="blue" size="sm" borderRadius="md" />
                  </Box>
                )}
                
                {activeTask.details && (
                  <Box>
                    <Text fontWeight="bold">{t('tasks.details')}:</Text>
                    <Text>{typeof activeTask.details === 'string' 
                      ? activeTask.details 
                      : JSON.stringify(activeTask.details, null, 2)}</Text>
                  </Box>
                )}
              </VStack>
            </CardBody>
            
            <CardFooter>
              <Text fontSize="sm" color="gray.500">
                {['SUCCESS', 'FAILURE', 'REVOKED'].includes(activeTask.status) 
                  ? t('tasks.completed') 
                  : t('tasks.inProgress')}
              </Text>
            </CardFooter>
          </Card>
        )}
      </VStack>
    </Box>
  );
};

export default BackgroundTasksPage; 