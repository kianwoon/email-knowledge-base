import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Heading,
  Button,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  IconButton,
  useToast,
  VStack,
  HStack,
  Text,
  Badge,
  useColorModeValue,
  Spinner,
} from '@chakra-ui/react';
import { FaPlus, FaEdit, FaTrash, FaSync } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

// Mock data interface - replace with actual API types
interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  documentCount: number;
  lastUpdated: string;
  status: 'active' | 'processing' | 'error';
}

const KnowledgeBaseListPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);

  // Mock data - replace with actual API call
  useEffect(() => {
    const fetchKnowledgeBases = async () => {
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        setKnowledgeBases([
          {
            id: '1',
            name: 'Technical Documentation',
            description: 'API and system documentation',
            documentCount: 156,
            lastUpdated: '2024-03-15',
            status: 'active',
          },
          {
            id: '2',
            name: 'Customer Support',
            description: 'Support tickets and FAQs',
            documentCount: 432,
            lastUpdated: '2024-03-14',
            status: 'processing',
          },
          {
            id: '3',
            name: 'Product Knowledge',
            description: 'Product specifications and guides',
            documentCount: 89,
            lastUpdated: '2024-03-13',
            status: 'active',
          },
        ]);
        setIsLoading(false);
      } catch (error) {
        console.error('Error fetching knowledge bases:', error);
        toast({
          title: t('knowledgeBase.errors.fetchFailed'),
          description: t('knowledgeBase.errors.fetchFailedDesc'),
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        setIsLoading(false);
      }
    };

    fetchKnowledgeBases();
  }, [t, toast]);

  const handleCreateNew = () => {
    // Implement create new knowledge base logic
    console.log('Create new knowledge base');
  };

  const handleEdit = (id: string) => {
    navigate(`/knowledge/${id}`);
  };

  const handleDelete = (id: string) => {
    // Implement delete logic
    console.log('Delete knowledge base:', id);
  };

  const handleRefresh = (id: string) => {
    // Implement refresh/sync logic
    console.log('Refresh knowledge base:', id);
  };

  const getStatusBadge = (status: KnowledgeBase['status']) => {
    const statusProps = {
      active: { colorScheme: 'green', label: t('knowledgeBase.status.active') },
      processing: { colorScheme: 'yellow', label: t('knowledgeBase.status.processing') },
      error: { colorScheme: 'red', label: t('knowledgeBase.status.error') },
    };

    const { colorScheme, label } = statusProps[status];
    return <Badge colorScheme={colorScheme}>{label}</Badge>;
  };

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        <HStack justify="space-between">
          <Box>
            <Heading size="lg" mb={2}>
              {t('knowledgeBase.title', 'Knowledge Bases')}
            </Heading>
            <Text color="gray.500">
              {t('knowledgeBase.description', 'Manage your AI-powered knowledge bases')}
            </Text>
          </Box>
          <Button
            leftIcon={<FaPlus />}
            colorScheme="blue"
            onClick={handleCreateNew}
          >
            {t('knowledgeBase.actions.create', 'Create New')}
          </Button>
        </HStack>

        {isLoading ? (
          <Box textAlign="center" py={10}>
            <Spinner size="xl" />
          </Box>
        ) : (
          <Box
            borderWidth="1px"
            borderRadius="lg"
            overflow="hidden"
            bg={useColorModeValue('white', 'gray.700')}
          >
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>{t('knowledgeBase.table.name', 'Name')}</Th>
                  <Th>{t('knowledgeBase.table.description', 'Description')}</Th>
                  <Th isNumeric>{t('knowledgeBase.table.documents', 'Documents')}</Th>
                  <Th>{t('knowledgeBase.table.lastUpdated', 'Last Updated')}</Th>
                  <Th>{t('knowledgeBase.table.status', 'Status')}</Th>
                  <Th>{t('knowledgeBase.table.actions', 'Actions')}</Th>
                </Tr>
              </Thead>
              <Tbody>
                {knowledgeBases.map((kb) => (
                  <Tr key={kb.id}>
                    <Td fontWeight="medium">{kb.name}</Td>
                    <Td>{kb.description}</Td>
                    <Td isNumeric>{kb.documentCount}</Td>
                    <Td>{kb.lastUpdated}</Td>
                    <Td>{getStatusBadge(kb.status)}</Td>
                    <Td>
                      <HStack spacing={2}>
                        <IconButton
                          aria-label={t('knowledgeBase.actions.edit')}
                          icon={<FaEdit />}
                          size="sm"
                          onClick={() => handleEdit(kb.id)}
                        />
                        <IconButton
                          aria-label={t('knowledgeBase.actions.refresh')}
                          icon={<FaSync />}
                          size="sm"
                          onClick={() => handleRefresh(kb.id)}
                        />
                        <IconButton
                          aria-label={t('knowledgeBase.actions.delete')}
                          icon={<FaTrash />}
                          size="sm"
                          colorScheme="red"
                          onClick={() => handleDelete(kb.id)}
                        />
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        )}
      </VStack>
    </Container>
  );
};

export default KnowledgeBaseListPage; 