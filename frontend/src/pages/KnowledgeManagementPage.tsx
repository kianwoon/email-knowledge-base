import React, { useState, useEffect, useCallback } from 'react';
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
} from '@chakra-ui/react';
import { RepeatIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';
import PageBanner from '../components/PageBanner';
import { getKnowledgeBaseSummary, KnowledgeSummaryResponse } from '../api/knowledge';
import { getUserTokens, Token } from '../api/token';

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

  const cardBg = useColorModeValue('white', 'gray.700');
  const cardBorder = useColorModeValue('gray.200', 'gray.600');

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

  useEffect(() => {
    fetchAllSummaries();
  }, [fetchAllSummaries]);

  const formatDateTime = (isoString: string | null): string => {
    if (!isoString) return t('common.notAvailable', 'N/A');
    try {
      return new Date(isoString).toLocaleString();
    } catch (e) {
      console.error("Error formatting date:", e);
      return isoString;
    }
  };

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