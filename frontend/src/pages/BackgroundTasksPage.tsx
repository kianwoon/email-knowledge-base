import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Spinner,
  VStack,
  HStack,
  Progress,
  useToast,
  Card,
  CardBody,
  Button,
  IconButton,
  Tooltip,
} from '@chakra-ui/react';
import { FiRefreshCw } from 'react-icons/fi';
import { getTaskStatus, getMyLatestKbTask } from '../api/tasks';
import { TaskStatus } from '../api/tasks';
import { useTranslation } from 'react-i18next';

const BackgroundTasksPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [latestTask, setLatestTask] = useState<TaskStatus | null>(null);
  const [activeTasks, setActiveTasks] = useState<TaskStatus[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  // Function to fetch latest knowledge base task
  const fetchLatestKbTask = async () => {
    try {
      const task = await getMyLatestKbTask();
      if (task) {
        setLatestTask(task);
        // If the task is active, also add it to active tasks list
        if (['PENDING', 'STARTED', 'PROGRESS'].includes(task.status)) {
          setActiveTasks(prev => {
            // Check if task already exists in the list
            const exists = prev.some(t => t.task_id === task.task_id);
            if (!exists) {
              return [...prev, task];
            }
            return prev.map(t => t.task_id === task.task_id ? task : t);
          });
        }
      } else {
        setLatestTask(null);
      }
    } catch (error) {
      console.error('Error fetching latest KB task:', error);
      toast({
        title: t('errors.failed_to_fetch_tasks'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Function to refresh task statuses
  const refreshTasks = async () => {
    setRefreshing(true);
    try {
      // First get the latest KB task
      await fetchLatestKbTask();
      
      // Then update all active tasks
      const updatedTasks = await Promise.all(
        activeTasks.map(async (task) => {
          try {
            return await getTaskStatus(task.task_id);
          } catch (error) {
            console.error(`Error updating task ${task.task_id}:`, error);
            return task; // Return the original task if fetching fails
          }
        })
      );
      
      // Filter out completed tasks after a while
      setActiveTasks(updatedTasks.filter(
        task => ['PENDING', 'STARTED', 'PROGRESS'].includes(task.status)
      ));
    } catch (error) {
      console.error('Error refreshing tasks:', error);
      toast({
        title: t('errors.failed_to_refresh_tasks'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setRefreshing(false);
    }
  };

  // Initial load
  useEffect(() => {
    const loadInitialData = async () => {
      setIsLoading(true);
      try {
        await fetchLatestKbTask();
      } catch (error) {
        console.error('Error loading initial task data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, []);

  // Periodically refresh active tasks
  useEffect(() => {
    // Only set interval if there are active tasks
    if (activeTasks.length === 0) return;

    const intervalId = setInterval(() => {
      refreshTasks();
    }, 5000); // Check every 5 seconds

    return () => clearInterval(intervalId);
  }, [activeTasks]);

  // Helper function to render task status badge
  const renderStatusBadge = (status: string) => {
    let color = 'gray';
    
    switch (status) {
      case 'SUCCESS':
        color = 'green';
        break;
      case 'FAILURE':
        color = 'red';
        break;
      case 'STARTED':
      case 'PROGRESS':
        color = 'blue';
        break;
      case 'PENDING':
        color = 'yellow';
        break;
      default:
        color = 'gray';
    }
    
    return <Badge colorScheme={color}>{status}</Badge>;
  };

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={6} align="stretch">
        <HStack justify="space-between">
          <Heading size="lg">{t('tasks.background_tasks')}</Heading>
          <Tooltip label={t('common.refresh')}>
            <IconButton
              aria-label={t('common.refresh')}
              icon={<FiRefreshCw />}
              onClick={refreshTasks}
              isLoading={refreshing}
            />
          </Tooltip>
        </HStack>

        {isLoading ? (
          <Box textAlign="center" py={10}>
            <Spinner size="xl" />
            <Text mt={4}>{t('common.loading')}</Text>
          </Box>
        ) : (
          <>
            {/* Latest Knowledge Base Task */}
            <Card>
              <CardBody>
                <Heading size="md" mb={4}>{t('tasks.latest_kb_task')}</Heading>
                {latestTask ? (
                  <VStack align="stretch" spacing={4}>
                    <HStack justify="space-between">
                      <Text fontWeight="bold">{t('tasks.task_id')}</Text>
                      <Text>{latestTask.task_id}</Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text fontWeight="bold">{t('tasks.status')}</Text>
                      {renderStatusBadge(latestTask.status)}
                    </HStack>
                    {latestTask.status === 'PROGRESS' && (
                      <VStack align="stretch" spacing={1}>
                        <Text fontWeight="bold">{t('tasks.progress')}</Text>
                        <Progress 
                          value={latestTask.progress || 0} 
                          size="sm" 
                          colorScheme="blue"
                        />
                        <Text textAlign="right" fontSize="sm">
                          {`${latestTask.progress || 0}%`}
                        </Text>
                      </VStack>
                    )}
                    {latestTask.details && (
                      <VStack align="stretch" spacing={1}>
                        <Text fontWeight="bold">{t('tasks.details')}</Text>
                        <Text>{latestTask.details}</Text>
                      </VStack>
                    )}
                  </VStack>
                ) : (
                  <Text>{t('tasks.no_active_tasks')}</Text>
                )}
              </CardBody>
            </Card>

            {/* Active Tasks List */}
            {activeTasks.length > 0 && (
              <Box>
                <Heading size="md" mb={4}>{t('tasks.active_tasks')}</Heading>
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>{t('tasks.task_id')}</Th>
                      <Th>{t('tasks.status')}</Th>
                      <Th>{t('tasks.progress')}</Th>
                      <Th>{t('tasks.details')}</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {activeTasks.map((task) => (
                      <Tr key={task.task_id}>
                        <Td>{task.task_id}</Td>
                        <Td>{renderStatusBadge(task.status)}</Td>
                        <Td>
                          {task.status === 'PROGRESS' ? (
                            <Progress 
                              value={task.progress || 0} 
                              size="xs" 
                              width="100px" 
                              colorScheme="blue"
                            />
                          ) : (
                            '-'
                          )}
                        </Td>
                        <Td>{task.details || '-'}</Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            )}
          </>
        )}
      </VStack>
    </Container>
  );
};

export default BackgroundTasksPage; 