import React, { useState, useEffect } from 'react';
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
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { getCollectionSummary } from '../api/knowledge'; // <<< UNCOMMENTED

interface CollectionSummary {
  count: number;
  // Add other stats here later if needed
}

const KnowledgeManagementPage: React.FC = () => {
  const { t } = useTranslation();
  const [rawDataSummary, setRawDataSummary] = useState<CollectionSummary | null>(null);
  const [vectorDataSummary, setVectorDataSummary] = useState<CollectionSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  const cardBg = useColorModeValue('white', 'rgba(255, 255, 255, 0.05)');
  const cardBorder = useColorModeValue('gray.200', 'rgba(255, 255, 255, 0.16)');

  // --- UNCOMMENTED useEffect ---
  useEffect(() => {
    const fetchSummaries = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [rawSummary, vectorSummary] = await Promise.all([
          getCollectionSummary('email_knowledge'), 
          getCollectionSummary('email_knowledge_base')
        ]);
        setRawDataSummary(rawSummary);
        setVectorDataSummary(vectorSummary);
      } catch (err: any) {
        setError(err.message || t('knowledgeManagement.errors.loadSummary'));
        setRawDataSummary(null);
        setVectorDataSummary(null);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSummaries();
  }, [t]);
  // --- END UNCOMMENTED useEffect ---

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={6} align="stretch">
        <Heading size="lg">{t('knowledgeManagement.title')}</Heading>

        {isLoading && (
          <Center py={10}>
            <Spinner size="xl" />
          </Center>
        )}

        {error && (
          <Alert status="error" borderRadius="md">
            <AlertIcon />
            {error}
          </Alert>
        )}

        {!isLoading && !error && (
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
            {/* Raw Data Summary Card */}
            <Card bg={cardBg} borderRadius="xl" boxShadow="md" borderWidth="1px" borderColor={cardBorder}>
              <CardHeader>
                <Heading size="md">{t('knowledgeManagement.rawData.title')}</Heading>
              </CardHeader>
              <CardBody>
                <Stat>
                  <StatLabel>{t('knowledgeManagement.itemCount')}</StatLabel>
                  <StatNumber>{rawDataSummary?.count ?? '-'}</StatNumber>
                  <StatHelpText>{t('knowledgeManagement.rawData.description')}</StatHelpText>
                </Stat>
                {/* Add more stats or actions here later */}
              </CardBody>
            </Card>

            {/* Vector Data Summary Card */}
            <Card bg={cardBg} borderRadius="xl" boxShadow="md" borderWidth="1px" borderColor={cardBorder}>
              <CardHeader>
                <Heading size="md">{t('knowledgeManagement.vectorData.title')}</Heading>
              </CardHeader>
              <CardBody>
                <Stat>
                  <StatLabel>{t('knowledgeManagement.itemCount')}</StatLabel>
                  <StatNumber>{vectorDataSummary?.count ?? '-'}</StatNumber>
                  <StatHelpText>{t('knowledgeManagement.vectorData.description')}</StatHelpText>
                </Stat>
                {/* Add more stats or actions here later */}
              </CardBody>
            </Card>
          </SimpleGrid>
        )}
      </VStack>
    </Container>
  );
};

export default KnowledgeManagementPage; 