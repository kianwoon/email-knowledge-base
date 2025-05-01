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
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { testTokenSearch, SharedMilvusResult } from '../../api/token'; // Adjust path as needed

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
  const [results, setResults] = useState<SharedMilvusResult[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Use theme colors for diagnostic box
  const diagnosticBg = useColorModeValue('gray.100', 'gray.700');
  const diagnosticColor = useColorModeValue('gray.700', 'gray.200');

  // Reset state when modal is closed or tokenId changes
  useEffect(() => {
    if (!isOpen) {
      setQuery('');
      setResults(null);
      setIsLoading(false);
      setError(null);
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

  const handleTestSearch = async () => {
    if (!tokenId || !query.trim()) {
      setError(t(`${KEY_PREFIX}.errors.missingInput`, 'Please enter a query.'));
      return;
    }

    setIsLoading(true);
    setError(null);
    setResults(null);

    try {
      const searchResults = await testTokenSearch(tokenId, query);
      setResults(searchResults);
      if (searchResults.length === 0) {
           toast({
            title: t(`${KEY_PREFIX}.toast.noResultsTitle`, 'No Results'),
            description: t(`${KEY_PREFIX}.toast.noResultsDesc`, 'Your test query returned no results based on the token permissions.'),
            status: 'info',
            duration: 3000,
            isClosable: true,
          });
      }
    } catch (err: any) {
      const errorMessage = err.message || t(`${KEY_PREFIX}.errors.searchFailed`, 'Test search failed.');
      setError(errorMessage);
      toast({
        title: t('common.error', 'Error'),
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const resultBg = useColorModeValue('gray.50', 'gray.800');
  const resultBorderColor = useColorModeValue('gray.200', 'gray.600');

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent as="div">
        <ModalHeader>
          {t(`${KEY_PREFIX}.title`, 'Test Token Search')}
          {tokenName && `: ${tokenName}`} 
          {tokenId && ` (ID: ${tokenId})`}
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          {/* Debug info - only visible in development */}
          {process.env.NODE_ENV === 'development' && (
            <Box 
              bg={diagnosticBg} // Use theme-aware background
              color={diagnosticColor} // Use theme-aware text color
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
            <FormControl isRequired>
              <FormLabel htmlFor="test-query">{t(`${KEY_PREFIX}.queryLabel`, 'Test Query')}</FormLabel>
              <Input
                id="test-query"
                placeholder={t(`${KEY_PREFIX}.queryPlaceholder`, 'Enter search query...')}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                     if (e.key === 'Enter') {
                        e.preventDefault();
                        handleTestSearch();
                     }
                }}
                isDisabled={isLoading}
              />
            </FormControl>
            
            <Button 
              colorScheme="blue" 
              onClick={handleTestSearch} 
              isLoading={isLoading}
              isDisabled={!query.trim() || isLoading}
            >
              {t(`${KEY_PREFIX}.runButton`, 'Run Test Search')}
            </Button>

            {error && (
              <Alert status="error" borderRadius="md">
                <AlertIcon />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {isLoading && (
              <Box textAlign="center" p={4}>
                <Spinner size="lg" />
                <Text mt={2}>{t(`${KEY_PREFIX}.loading`, 'Searching...')}</Text>
              </Box>
            )}

            {results !== null && (
              <Box mt={4}>
                <Heading size="sm" mb={2}>{t(`${KEY_PREFIX}.resultsTitle`, 'Results')} ({results.length})</Heading>
                {results.length > 0 ? (
                  <Box 
                    maxHeight="40vh" 
                    overflowY="auto" 
                    borderWidth="1px" 
                    borderRadius="md" 
                    p={3}
                    borderColor={resultBorderColor}
                    bg={resultBg}
                  >
                    <Code 
                        display="block" 
                        whiteSpace="pre-wrap" 
                        wordBreak="break-word" 
                        fontSize="sm"
                     >
                      {JSON.stringify(results, null, 2)}
                    </Code>
                  </Box>
                ) : (
                  <Text color="gray.500">{t(`${KEY_PREFIX}.noResultsFound`, 'No results found matching the query and token permissions.')}</Text>
                )}
              </Box>
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

export default TestTokenModal; 