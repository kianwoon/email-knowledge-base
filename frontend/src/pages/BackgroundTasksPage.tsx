import React, { useState, useEffect } from 'react';
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
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';

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
  const [isLoading, setIsLoading] = useState(true);
  const [tasks, setTasks] = useState<Task[]>([]);

  // Mock data fetch - replace with actual API call
  useEffect(() => {
    const fetchTasks = async () => {
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        setTasks([
          {
            id: '1',
            type: 'Knowledge Base Update',
            status: 'running',
            progress: 45,
            startTime: '2024-03-15T10:30:00Z',
            details: 'Updating Technical Documentation KB',
          },
          {
            id: '2',
            type: 'Data Export',
            status: 'completed',
            progress: 100,
            startTime: '2024-03-15T09:00:00Z',
            endTime: '2024-03-15T09:05:00Z',
            details: 'Exported Customer Support KB',
          },
          {
            id: '3',
            type: 'Vector Index Build',
            status: 'failed',
            progress: 67,
            startTime: '2024-03-15T08:00:00Z',
            endTime: '2024-03-15T08:15:00Z',
            error: 'Connection timeout',
            details: 'Building vector index for Product Knowledge KB',
          },
        ]);
        setIsLoading(false);
      } catch (error) {
        console.error('Error fetching tasks:', error);
        toast({
          title: t('tasks.errors.fetchFailed'),
          description: t('tasks.errors.fetchFailedDesc'),
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        setIsLoading(false);
      }
    };

    fetchTasks();
    // Set up polling interval
    const interval = setInterval(fetchTasks, 5000);
    return () => clearInterval(interval);
  }, [t, toast]);

  const getStatusBadge = (status: Task['status']) => {
    const statusProps = {
      running: { colorScheme: 'blue', label: t('tasks.status.running') },
      completed: { colorScheme: 'green', label: t('tasks.status.completed') },
      failed: { colorScheme: 'red', label: t('tasks.status.failed') },
    };

    const { colorScheme, label } = statusProps[status];
    return <Badge colorScheme={colorScheme}>{label}</Badge>;
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (isLoading) {
    return (
      <Container maxW="container.xl" py={8}>
        <Box textAlign="center" py={10}>
          <Spinner size="xl" />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        <Box>
          <Heading size="lg" mb={2}>
            {t('tasks.title', 'Background Tasks')}
          </Heading>
          <Text color="gray.500">
            {t('tasks.description', 'Monitor and manage background tasks')}
          </Text>
        </Box>

        <Box
          borderWidth="1px"
          borderRadius="lg"
          overflow="hidden"
          bg={useColorModeValue('white', 'gray.700')}
        >
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>{t('tasks.table.type', 'Type')}</Th>
                <Th>{t('tasks.table.status', 'Status')}</Th>
                <Th>{t('tasks.table.progress', 'Progress')}</Th>
                <Th>{t('tasks.table.startTime', 'Start Time')}</Th>
                <Th>{t('tasks.table.endTime', 'End Time')}</Th>
                <Th>{t('tasks.table.details', 'Details')}</Th>
              </Tr>
            </Thead>
            <Tbody>
              {tasks.map((task) => (
                <Tr key={task.id}>
                  <Td fontWeight="medium">{task.type}</Td>
                  <Td>{getStatusBadge(task.status)}</Td>
                  <Td>
                    <Box>
                      <Progress
                        value={task.progress}
                        size="sm"
                        colorScheme={
                          task.status === 'failed'
                            ? 'red'
                            : task.status === 'completed'
                            ? 'green'
                            : 'blue'
                        }
                      />
                      <Text fontSize="sm" mt={1}>
                        {task.progress}%
                      </Text>
                    </Box>
                  </Td>
                  <Td>{formatDateTime(task.startTime)}</Td>
                  <Td>{task.endTime ? formatDateTime(task.endTime) : '-'}</Td>
                  <Td>
                    <Text>{task.details}</Text>
                    {task.error && (
                      <Text color="red.500" fontSize="sm" mt={1}>
                        Error: {task.error}
                      </Text>
                    )}
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      </VStack>
    </Container>
  );
};

export default BackgroundTasksPage; 