import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  AlertDescription,
  Code,
  Box,
  Text,
  Divider,
  Heading,
  useColorModeValue,
  HStack,
  Tag,
  Badge,
  FormErrorMessage,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { testTokenSearch, getTokenDetails } from '../../api/token';
import { SharedMilvusResult } from '../../api/token'; // Import SharedMilvusResult if not already

interface TestTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  tokenId: number | null; // Pass the ID of the token to test
  tokenName?: string; // Optional: Pass token name for display
}

// Define key prefix to ensure consistency
const KEY_PREFIX = 'testTokenModal';

const TestTokenModal: React.FC<TestTokenModalProps> = ({ 
    isOpen, 
    onClose, 
    tokenId, 
    tokenName 
}) => {
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SharedMilvusResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- State for Token Configuration ---
  const [tokenConfig, setTokenConfig] = useState<any | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState<boolean>(false);
  const [configError, setConfigError] = useState<string | null>(null);
  // --- End State ---

  // Reset state when modal is closed or tokenId changes
  useEffect(() => {
    if (!isOpen) {
      setQuery('');
      setResults([]);
      setIsLoading(false);
      setError(null);
      setTokenConfig(null);
      setIsLoadingConfig(false);
      setConfigError(null);
    }
  }, [isOpen]);

  // Debug logging to help diagnose translation issues
  useEffect(() => {
    if (isOpen) {
      console.log('Current language:', i18n.language);
      console.log('Close button translation:', t('common.close'));
      console.log('Modal title translation:', t(`${KEY_PREFIX}.title`));
      
      // Log the raw translation data to inspect
      console.log('Translation data:', i18n.store.data);
    }
  }, [isOpen, i18n.language, t]);

  // --- Effect to fetch token details when modal opens ---
  useEffect(() => {
    if (isOpen && tokenId) {
      // Reset states
      setQuery('');
      setResults([]);
      setError(null);
      setTokenConfig(null);
      setIsLoadingConfig(true);

      const fetchConfig = async () => {
        try {
          const config = await getTokenDetails(tokenId);
          setTokenConfig(config);
        } catch (err: any) {
          setConfigError(err.message || 'Failed to load token configuration.');
        } finally {
          setIsLoadingConfig(false);
        }
      };

      fetchConfig();
    } else {
      // Clear config when modal closes or tokenId is null
      setTokenConfig(null);
      setIsLoadingConfig(false);
      setConfigError(null);
    }
  }, [isOpen, tokenId]);
  // --- End Effect ---

  const handleSearch = async () => {
    if (!tokenId || !query.trim()) {
      setError(t(`${KEY_PREFIX}.errors.missingInput`, 'Please enter a query.'));
      return;
    }

    setIsLoading(true);
    setError(null);
    setResults([]); // Clear previous results

    try {
      const searchResults = await testTokenSearch(tokenId, query);
      setResults(searchResults);
      if (searchResults.length === 0) {
        toast({
          title: t(`${KEY_PREFIX}.toast.noResultsTitle`, 'No Results'),
          description: t(`${KEY_PREFIX}.toast.noResultsDesc`, 'Your test query returned no results based on the token permissions.'),
          status: 'info',
          duration: 4000,
          isClosable: true,
        });
      }
    } catch (err: any) {
      setError(err.message || t(`${KEY_PREFIX}.errors.searchFailed`, 'Test search failed.'));
    } finally {
      setIsLoading(false);
    }
  };

  const resultBg = useColorModeValue('gray.50', 'gray.800');
  const resultBorderColor = useColorModeValue('gray.200', 'gray.600');

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="2xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent as="div">
        <ModalHeader>
          {t(`${KEY_PREFIX}.title`, 'Test Token:')}
          {tokenName && `"${tokenName}"`}
          {tokenId && ` (ID: ${tokenId})`}
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          {/* Debug info - only visible in development */}
          {process.env.NODE_ENV === 'development' && (
            <Box 
              bg={useColorModeValue('gray.100', 'gray.700')}
              color={useColorModeValue('gray.700', 'gray.200')}
              p={2} 
              mb={4} 
              fontSize="xs" 
              borderRadius="md"
            >
              <Text fontWeight="bold">Diagnostic Info:</Text>
              <Text>Current Language: {i18n.language}</Text>
              <Text>Title Key: {`${KEY_PREFIX}.title`}</Text>
              <Text>Title Value: {t(`${KEY_PREFIX}.title`)}</Text>
              <Text>Close Key: common.close</Text>
              <Text>Close Value: {t('common.close')}</Text>
            </Box>
          )}
          
          <VStack spacing={4} align="stretch">
            {/* --- Token Configuration Display --- */}
            <Box borderWidth="1px" borderRadius="md" p={4} bg={useColorModeValue('gray.50', 'gray.700')}>
              <Text fontSize="lg" fontWeight="semibold" mb={2}>Token Configuration</Text>
              {isLoadingConfig ? (
                <Spinner size="md" />
              ) : configError ? (
                <Alert status="error" borderRadius="md">
                  <AlertIcon />
                  {configError}
                </Alert>
              ) : tokenConfig ? (
                <VStack align="stretch" spacing={2}>
                  <HStack>
                    <Text fontWeight="medium" minW="120px">Sensitivity:</Text>
                    <Badge colorScheme={getSensitivityColorScheme(tokenConfig?.sensitivity)}>{tokenConfig?.sensitivity ?? 'N/A'}</Badge>
                  </HStack>
                  <HStack align="start">
                    <Text fontWeight="medium" minW="120px" mt={1}>Allow Rules:</Text>
                    <Box>
                      {tokenConfig?.allow_rules && tokenConfig.allow_rules.length > 0 ? (
                        tokenConfig.allow_rules.map((rule: string, index: number) => (
                          <Tag key={`allow-${index}`} size="sm" mr={1} mb={1} variant="outline" colorScheme="green">{rule}</Tag>
                        ))
                      ) : (
                        <Text fontStyle="italic" color={useColorModeValue('gray.500', 'gray.400')}>None defined</Text>
                      )}
                    </Box>
                  </HStack>
                  <HStack align="start">
                    <Text fontWeight="medium" minW="120px" mt={1}>Deny Rules:</Text>
                    <Box>
                      {tokenConfig?.deny_rules && tokenConfig.deny_rules.length > 0 ? (
                        tokenConfig.deny_rules.map((rule: string, index: number) => (
                          <Tag key={`deny-${index}`} size="sm" mr={1} mb={1} variant="outline" colorScheme="red">{rule}</Tag>
                        ))
                      ) : (
                        <Text fontStyle="italic" color={useColorModeValue('gray.500', 'gray.400')}>None defined</Text>
                      )}
                    </Box>
                  </HStack>
                  {/* Optional: Add other fields like row limit, etc. here */}
                </VStack>
              ) : (
                <Text>Could not load configuration.</Text>
              )}
            </Box>
            {/* --- End Token Configuration Display --- */}

            {/* Query Input */}
            <FormControl isInvalid={!!error}>
              <FormLabel htmlFor="test-query">{t(`${KEY_PREFIX}.queryLabel`, 'Test Query')}</FormLabel>
              <Input
                id="test-query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t(`${KEY_PREFIX}.queryPlaceholder`, 'Enter search query...')}
              />
              {error && <FormErrorMessage>{error}</FormErrorMessage>}
            </FormControl>

            {/* Run Button */}
            <Button
              colorScheme="blue"
              onClick={handleSearch}
              isLoading={isLoading}
              loadingText={t(`${KEY_PREFIX}.loading`, 'Searching...')}
            >
              {t(`${KEY_PREFIX}.runButton`, 'Run Test Search')}
            </Button>

            {/* Results Section */}
            {results.length > 0 && (
              <Box mt={4}>
                <Text fontSize="lg" fontWeight="semibold" mb={2}>
                  {t(`${KEY_PREFIX}.resultsTitle`, "Results")} ({results.length})
                </Text>
                <VStack spacing={3} align="stretch" maxHeight="300px" overflowY="auto" pr={2}>
                  {results.map((result) => (
                    <Box key={result.id} borderWidth="1px" borderRadius="md" p={3} bg={useColorModeValue('white', 'gray.800')}>
                      <Text fontSize="sm" color="gray.500">ID: {result.id}</Text>
                      <Text fontSize="sm" color="gray.500">Score: {result.score?.toFixed(4)}</Text>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: '0.8em', marginTop: '4px' }}>
                        {JSON.stringify(result.metadata || {}, null, 2)}
                      </pre>
                    </Box>
                  ))}
                </VStack>
              </Box>
            )}

            {/* Show message only if NOT loading and query HAS been run (results is an empty array) but NOT if there was an error */}
            {!isLoading && !error && query && results.length === 0 && (
              <Text mt={4} fontStyle="italic" color={useColorModeValue('gray.600', 'gray.400')}>
                {t(`${KEY_PREFIX}.noResultsFound`, 'No results found matching the query and token permissions.')}
              </Text>
            )}
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button onClick={onClose}>
            {t('common.close', 'Close')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

// Helper function for sensitivity badge color (you might already have this elsewhere)
const getSensitivityColorScheme = (sensitivity?: string): string => {
  switch (sensitivity?.toLowerCase()) {
    case 'public': return 'green';
    case 'internal': return 'blue';
    case 'confidential': return 'orange';
    case 'strictly confidential': return 'red';
    default: return 'gray';
  }
};

export default TestTokenModal; 