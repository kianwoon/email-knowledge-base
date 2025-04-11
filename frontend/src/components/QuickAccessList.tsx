import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Link,
  Image,
  Icon,
  useColorModeValue,
  Wrap, 
  WrapItem,
  Tag,
  Center
} from '@chakra-ui/react';
import { FaExternalLinkAlt } from 'react-icons/fa'; // Example icon
import { useTranslation } from 'react-i18next';
import { getQuickAccessItems } from '../api/apiClient'; // Adjust path if needed
import { UsedInsight } from '../models/sharepoint'; // Adjust path if needed

// Helper to get a generic file icon or specific one based on type
const getFileTypeIcon = (fileType?: string) => {
    // Add more specific icons later (e.g., FaFileWord, FaFileExcel)
    return FaExternalLinkAlt; // Placeholder
};

const QuickAccessList: React.FC = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState<UsedInsight[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cardBg = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');

  useEffect(() => {
    const fetchItems = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getQuickAccessItems();
        setItems(data || []);
      } catch (err: any) {
        console.error('[QuickAccessList] Fetch error:', err);
        setError(err.response?.data?.detail || err.message || t('errors.unknown'));
        setItems([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchItems();
  }, [t]);

  if (isLoading) {
    return (
      <Center py={10}>
        <Spinner size="xl" />
      </Center>
    );
  }

  if (error) {
    return (
      <Alert status="error">
        <AlertIcon />
        <AlertTitle mr={2}>{t('quickAccess.errorTitle')}</AlertTitle> {/* Add translation */} 
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (items.length === 0) {
    return (
      <Center py={10}>
        <Text color="gray.500">{t('quickAccess.noItems')}</Text> {/* Add translation */} 
      </Center>
    );
  }

  return (
    <Box>
      <Text fontSize="lg" mb={4} fontWeight="medium">
        {t('quickAccess.title')} {/* Add translation */} 
      </Text>
      <Wrap spacing="4">
        {items.map((item) => (
          <WrapItem key={item.id} width={{ base: '100%', sm: 'calc(50% - 1rem)', md: 'calc(33.33% - 1rem)' }}>
            <Link 
              href={item.resourceReference?.webUrl || '#'} 
              isExternal 
              _hover={{ textDecoration: 'none' }}
              width="100%"
            >
              <HStack 
                p={3} 
                bg={cardBg}
                borderRadius="md" 
                borderWidth="1px"
                spacing={3} 
                alignItems="center"
                width="100%"
                _hover={{ bg: hoverBg, shadow: 'sm' }}
                transition="background-color 0.2s"
              >
                {item.resourceVisualization?.previewImageUrl ? (
                    <Image src={item.resourceVisualization.previewImageUrl} boxSize="40px" objectFit="cover" borderRadius="sm" alt="Preview"/>
                ) : (
                    <Icon as={getFileTypeIcon(item.resourceVisualization?.type)} boxSize={6} color="gray.500" />
                )}
                <VStack align="start" spacing={0} flex={1} overflow="hidden">
                  <Text 
                    fontWeight="medium" 
                    fontSize="sm" 
                    isTruncated 
                    title={item.resourceVisualization?.title || 'Untitled'}
                  >
                      {item.resourceVisualization?.title || 'Untitled'}
                  </Text>
                  {item.resourceVisualization?.type && (
                    <Tag size="sm" variant="subtle" colorScheme="blue">
                        {item.resourceVisualization.type}
                    </Tag>
                  )}
                  {/* Can add last accessed time here if available later */} 
                </VStack>
              </HStack>
            </Link>
          </WrapItem>
        ))}
      </Wrap>
    </Box>
  );
};

export default QuickAccessList; 