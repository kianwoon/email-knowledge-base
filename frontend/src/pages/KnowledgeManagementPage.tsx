import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Container,
  Heading,
  SimpleGrid,
  Card,
  CardHeader,
  CardBody,
  Text,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Spinner,
  Alert,
  AlertIcon,
  VStack,
  useColorModeValue,
  Center,
  Divider,
  IconButton,
  HStack,
  Tooltip,
  Progress,
  AlertDescription,
} from '@chakra-ui/react';
import { RepeatIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';
import PageBanner from '../components/PageBanner';
import { getKnowledgeBaseSummary, KnowledgeSummaryResponse } from '../api/knowledge';
import { getUserTokens, Token } from '../api/token';
import { getMyLatestKbTask, getTaskStatus, TaskStatus } from '../api/tasks';

interface CombinedSummary {
  rawDataCount: number;
  vectorDataCount: number;
  totalTokenCount: number;
  activeTokenCount: number;
  lastUpdated: string | null;
}

const KnowledgeManagementPage: React.FC = () => {
  const { t } = useTranslation();
  const [summaryData, setSummaryData] = useState<CombinedSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<TaskStatus | null>(null);
  const [isLoadingTaskStatus, setIsLoadingTaskStatus] = useState(true);
  const taskPollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const cardBg = useColorModeValue('white', 'gray.700');
  const cardBorder = useColorModeValue('gray.200', 'gray.600');

  const stopTaskPolling = useCallback(() => {
    if (taskPollingIntervalRef.current) {
      clearInterval(taskPollingIntervalRef.current);
      taskPollingIntervalRef.current = null;
      console.log('[Task Polling] Polling stopped.');
    }
  }, []);

  const pollTaskStatus = useCallback(async (taskId: string) => {
    console.log(`[Task Polling] Checking status for task ${taskId}...`);
    try {
      const statusResult = await getTaskStatus(taskId);
      setActiveTask(statusResult);

      if (statusResult.status === 'SUCCESS' || statusResult.status === 'FAILURE' || statusResult.status === 'REVOKED') {
        console.log(`[Task Polling] Task ${taskId} reached final state: ${statusResult.status}. Stopping polling.`);
        stopTaskPolling();
      }
    } catch (error) {
      console.error(`[Task Polling] Error fetching status for task ${taskId}:`, error);
      stopTaskPolling();
    }
  }, [stopTaskPolling]);

  const startTaskPolling = useCallback((taskId: string) => {
    stopTaskPolling();
    console.log(`[Task Polling] Starting polling for task ${taskId}...`);
    pollTaskStatus(taskId);
    taskPollingIntervalRef.current = setInterval(() => pollTaskStatus(taskId), 5000);
  }, [pollTaskStatus, stopTaskPolling]);

  const fetchAllSummaries = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    console.log("Fetching all summaries...");
    try {
      const [knowledgeSummary, tokens] = await Promise.all([
        getKnowledgeBaseSummary(),
        getUserTokens()
      ]);
      
      console.log("Knowledge Summary:", knowledgeSummary);
      console.log("Tokens:", tokens);

      const totalTokens = tokens.length;
      const activeTokens = tokens.filter((token: Token) => token.is_active).length;
      
      setSummaryData({
        rawDataCount: knowledgeSummary.raw_data_count ?? 0,
        vectorDataCount: knowledgeSummary.vector_data_count ?? 0,
        totalTokenCount: totalTokens,
        activeTokenCount: activeTokens,
        lastUpdated: knowledgeSummary.last_updated || null,
      });
      console.log("Summaries fetched and processed.");

    } catch (err: any) {
      console.error("Failed to fetch summaries:", err);
      setError(t('knowledgeManagement.errors.loadFailed', 'Failed to load summary data. Please try again.'));
    } finally {
      setIsLoading(false);
      console.log("Finished fetching summaries.");
    }
  }, [t]);

  const checkActiveTask = useCallback(async () => {
    setIsLoadingTaskStatus(true);
    console.log("Checking for active KB task...");
    try {
      const task = await getMyLatestKbTask();
      if (task && task.task_id && !['SUCCESS', 'FAILURE', 'REVOKED'].includes(task.status)) {
        console.log("Active task found:", task);
        setActiveTask(task);
        startTaskPolling(task.task_id);
      } else {
        console.log("No active KB task found or task is finished.");
        setActiveTask(null);
        stopTaskPolling();
      }
    } catch (err) {
      console.error("Failed to check for active task:", err);
      setError(t('knowledgeManagement.errors.taskCheckFailed', 'Failed to check for active background tasks.'));
      setActiveTask(null);
      stopTaskPolling();
    } finally {
      setIsLoadingTaskStatus(false);
    }
  }, [t, startTaskPolling, stopTaskPolling]);

  useEffect(() => {
    fetchAllSummaries();
    checkActiveTask();

    return () => {
      stopTaskPolling();
    };
  }, [fetchAllSummaries, checkActiveTask, stopTaskPolling]);

  const formatDateTime = (isoString: string | null): string => {
    if (!isoString) return t('common.notAvailable', 'N/A');
    try {
      return new Date(isoString).toLocaleString();
    } catch (e) {
      console.error("Error formatting date:", e);
      return isoString;
    }
  };

  let taskProgress = 0;
  let taskStatusMessage = '';
  const isTaskRunning = activeTask && !['SUCCESS', 'FAILURE', 'REVOKED'].includes(activeTask.status);

  if (isTaskRunning && activeTask) {
    taskProgress = typeof activeTask.progress === 'number' ? activeTask.progress : 0;
    taskStatusMessage = typeof activeTask.details === 'string' ? activeTask.details : t('knowledgeManagement.task.calculating', 'Calculating...');
  } else if (activeTask?.status === 'PENDING') {
    taskStatusMessage = t('knowledgeManagement.task.pending', 'Task is pending...');
  } else if (activeTask?.status === 'STARTED') {
    taskStatusMessage = t('knowledgeManagement.task.started', 'Task started...');
  }

  return (
    <Box p={5}>
      <PageBanner title={t('knowledgeManagement.title', 'Knowledge Base Management')} />
      <VStack spacing={6} align="stretch">
        <HStack justify="space-between" align="center">
          <Box>
            <Heading size="lg" mb={1}>{t('knowledgeManagement.summaryTitle', 'Data Summary')}</Heading>
            {!isLoading && summaryData?.lastUpdated && (
              <Text fontSize="sm" color="gray.500">
                {t('knowledgeManagement.summary.lastUpdated', 'Last updated: {{time}}', { time: formatDateTime(summaryData.lastUpdated) })}
              </Text>
            )}
          </Box>
          <Tooltip label={t('common.refresh', 'Refresh Data')} placement="top">
            <IconButton
              aria-label={t('common.refresh', 'Refresh Data')}
              icon={<RepeatIcon />}
              onClick={fetchAllSummaries}
              isLoading={isLoading}
              variant="ghost"
            />
          </Tooltip>
        </HStack>
        
        {isLoading && !summaryData && <Spinner size="xl" />}
        
        {error && (
            <Alert status="error" borderRadius="md">
                <AlertIcon />
                {error} 
            </Alert>
        )}

        {!isLoading && !error && summaryData && (
          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6} opacity={isLoading ? 0.5 : 1}>
            <Box p={5} shadow="md" borderWidth="1px" borderRadius="lg" bg={cardBg} borderColor={cardBorder}>
              <Stat>
                <StatLabel>{t('knowledgeManagement.summary.rawDataLabel', 'Raw Data Items')}</StatLabel>
                <StatNumber>{summaryData.rawDataCount}</StatNumber>
                <StatHelpText>{t('knowledgeManagement.summary.rawDataHelp', 'Source: ')}{`{email}_email_knowledge`}</StatHelpText>
              </Stat>
            </Box>

            <Box p={5} shadow="md" borderWidth="1px" borderRadius="lg" bg={cardBg} borderColor={cardBorder}>
              <Stat>
                <StatLabel>{t('knowledgeManagement.summary.vectorDataLabel', 'Vector Data Items')}</StatLabel>
                <StatNumber>{summaryData.vectorDataCount}</StatNumber>
                <StatHelpText>{t('knowledgeManagement.summary.vectorDataHelp', 'Source: ')}{`{email}_email_knowledge_base`}</StatHelpText>
              </Stat>
            </Box>

            <Box p={5} shadow="md" borderWidth="1px" borderRadius="lg" bg={cardBg} borderColor={cardBorder}>
              <Stat>
                <StatLabel>{t('knowledgeManagement.summary.tokenLabel', 'API Access Tokens')}</StatLabel>
                <StatNumber>{summaryData.totalTokenCount}</StatNumber>
                <StatHelpText>{t('knowledgeManagement.summary.tokenHelp', '{count} active', { count: summaryData.activeTokenCount })}</StatHelpText>
              </Stat>
            </Box>
          </SimpleGrid>
        )}

        {(isLoadingTaskStatus || isTaskRunning) && (
            <Card variant="outline" bg={cardBg} borderColor={cardBorder}>
                <CardHeader>
                    <Heading size='md'>{t('knowledgeManagement.task.title', 'Background Task Status')}</Heading>
                </CardHeader>
                <CardBody>
                    {isLoadingTaskStatus ? (
                        <Center><Spinner size="md" /></Center>
                    ) : isTaskRunning && activeTask ? (
                        <VStack align="stretch" spacing={3}>
                            <Text>
                                {t('knowledgeManagement.task.processing', 'Knowledge base update in progress...')}
                                <Text as='span' fontSize='sm' color='gray.500' ml={2}>
                                    ({t('knowledgeManagement.task.taskId', 'Task ID: {{id}}', { id: activeTask.task_id })})
                                </Text>
                            </Text>
                            <Progress 
                                value={taskProgress} 
                                size='sm' 
                                colorScheme='blue' 
                                borderRadius="md"
                                hasStripe 
                                isAnimated={taskProgress < 100}
                             />
                            <Text fontSize='sm' color='gray.500'>{taskStatusMessage}</Text>
                        </VStack>
                    ) : null}
                </CardBody>
            </Card>
        )}

        <Divider my={6} />

        <Box>
          <Heading size="md" mb={3}>{t('knowledgeManagement.actionsTitle', 'Management Actions')}</Heading>
          <Text>{t('knowledgeManagement.actionsPlaceholder', 'Further actions related to knowledge base management can be added here.')}</Text>
        </Box>
      </VStack>
    </Box>
  );
};

export default KnowledgeManagementPage; 