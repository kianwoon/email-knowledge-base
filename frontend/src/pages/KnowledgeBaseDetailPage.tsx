import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Heading,
  Button,
  VStack,
  HStack,
  Text,
  useToast,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Spinner,
  Badge,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  SimpleGrid,
  Card,
  CardBody,
  useColorModeValue,
  IconButton,
} from '@chakra-ui/react';
import { useParams, useNavigate } from 'react-router-dom';
import { FaSync, FaDownload, FaTrash } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';

// Mock interfaces - replace with actual API types
interface KnowledgeBaseDetail {
  id: string;
  name: string;
  description: string;
  documentCount: number;
  lastUpdated: string;
  status: 'active' | 'processing' | 'error';
  stats: {
    totalTokens: number;
    averageResponseTime: string;
    successRate: string;
    dailyQueries: number;
  };
}

const KnowledgeBaseDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const toast = useToast();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [kb, setKb] = useState<KnowledgeBaseDetail | null>(null);

  const cardBg = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Mock data fetch - replace with actual API call
  useEffect(() => {
    const fetchKnowledgeBase = async () => {
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        setKb({
          id: id || '1',
          name: 'Technical Documentation',
          description: 'API and system documentation',
          documentCount: 156,
          lastUpdated: '2024-03-15',
          status: 'active',
          stats: {
            totalTokens: 1234567,
            averageResponseTime: '1.2s',
            successRate: '98.5%',
            dailyQueries: 250,
          },
        });
        setIsLoading(false);
      } catch (error) {
        console.error('Error fetching knowledge base:', error);
        toast({
          title: t('knowledgeBase.errors.fetchDetailsFailed'),
          description: t('knowledgeBase.errors.fetchDetailsFailedDesc'),
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        setIsLoading(false);
      }
    };

    if (id) {
      fetchKnowledgeBase();
    }
  }, [id, t, toast]);

  const handleRefresh = () => {
    // Implement refresh logic
    console.log('Refresh knowledge base');
  };

  const handleExport = () => {
    // Implement export logic
    console.log('Export knowledge base');
  };

  const handleDelete = () => {
    // Implement delete logic
    console.log('Delete knowledge base');
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

  if (!kb) {
    return (
      <Container maxW="container.xl" py={8}>
        <Text>{t('knowledgeBase.errors.notFound', 'Knowledge base not found')}</Text>
      </Container>
    );
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        <HStack justify="space-between">
          <Box>
            <Heading size="lg" mb={2}>
              {kb.name}
            </Heading>
            <Text color="gray.500">{kb.description}</Text>
          </Box>
          <HStack>
            <IconButton
              aria-label={t('knowledgeBase.actions.refresh')}
              icon={<FaSync />}
              onClick={handleRefresh}
            />
            <IconButton
              aria-label={t('knowledgeBase.actions.export')}
              icon={<FaDownload />}
              onClick={handleExport}
            />
            <IconButton
              aria-label={t('knowledgeBase.actions.delete')}
              icon={<FaTrash />}
              colorScheme="red"
              onClick={handleDelete}
            />
          </HStack>
        </HStack>

        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
            <CardBody>
              <Stat>
                <StatLabel>{t('knowledgeBase.stats.totalTokens')}</StatLabel>
                <StatNumber>{kb.stats.totalTokens.toLocaleString()}</StatNumber>
                <StatHelpText>{t('knowledgeBase.stats.tokensHelp')}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
            <CardBody>
              <Stat>
                <StatLabel>{t('knowledgeBase.stats.responseTime')}</StatLabel>
                <StatNumber>{kb.stats.averageResponseTime}</StatNumber>
                <StatHelpText>{t('knowledgeBase.stats.responseTimeHelp')}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
            <CardBody>
              <Stat>
                <StatLabel>{t('knowledgeBase.stats.successRate')}</StatLabel>
                <StatNumber>{kb.stats.successRate}</StatNumber>
                <StatHelpText>{t('knowledgeBase.stats.successRateHelp')}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
            <CardBody>
              <Stat>
                <StatLabel>{t('knowledgeBase.stats.dailyQueries')}</StatLabel>
                <StatNumber>{kb.stats.dailyQueries}</StatNumber>
                <StatHelpText>{t('knowledgeBase.stats.dailyQueriesHelp')}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        <Tabs>
          <TabList>
            <Tab>{t('knowledgeBase.tabs.overview', 'Overview')}</Tab>
            <Tab>{t('knowledgeBase.tabs.search', 'Search')}</Tab>
            <Tab>{t('knowledgeBase.tabs.settings', 'Settings')}</Tab>
          </TabList>

          <TabPanels>
            <TabPanel>
              {/* Overview content */}
              <Text>Overview content goes here</Text>
            </TabPanel>
            <TabPanel>
              {/* Search interface */}
              <Text>Search interface goes here</Text>
            </TabPanel>
            <TabPanel>
              {/* Settings form */}
              <Text>Settings form goes here</Text>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Container>
  );
};

export default KnowledgeBaseDetailPage; 