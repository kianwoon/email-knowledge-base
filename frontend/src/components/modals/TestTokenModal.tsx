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
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  SimpleGrid,
  Textarea,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  IconButton,
  Switch,
  List,
  ListItem,
  FormHelperText,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { 
    testTokenSearch, 
    getTokenDetails, 
    SharedMilvusResult,
    testTokenCatalogSearch,
    CatalogSearchRequest,
    CatalogSearchResult,
    Token,
    debugTokenValue,
    ownerTestTokenCatalogSearch
} from '../../api/token';

interface TestTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  tokenId: number | null;
  tokenName?: string;
}

const KEY_PREFIX = 'testTokenModal';

const TestTokenModal: React.FC<TestTokenModalProps> = ({ 
    isOpen, 
    onClose, 
    tokenId, 
    tokenName 
}) => {
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const [searchType, setSearchType] = useState<'milvus' | 'catalog'>('milvus');

  // --- Milvus State ---
  const [milvusQuery, setMilvusQuery] = useState('');
  const [milvusResults, setMilvusResults] = useState<SharedMilvusResult[]>([]);
  const [isMilvusLoading, setIsMilvusLoading] = useState(false);
  const [milvusError, setMilvusError] = useState<string | null>(null);

  // --- Catalog State ---
  const [catalogQuery, setCatalogQuery] = useState('');
  const [catalogSender, setCatalogSender] = useState('');
  const [catalogDateFrom, setCatalogDateFrom] = useState('');
  const [catalogDateTo, setCatalogDateTo] = useState('');
  const [catalogLimit, setCatalogLimit] = useState('10');
  const [catalogResults, setCatalogResults] = useState<CatalogSearchResult[]>([]);
  const [isCatalogLoading, setIsCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  // --- Common State ---
  const [tokenConfig, setTokenConfig] = useState<any | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState<boolean>(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [kbTokenValue, setKbTokenValue] = useState<string | null>(null);
  const [isLoadingTokenValue, setIsLoadingTokenValue] = useState<boolean>(false);

  // Reset state when modal is closed or tokenId changes
  useEffect(() => {
    if (!isOpen) {
      setSearchType('milvus');
      // Milvus
      setMilvusQuery('');
      setMilvusResults([]);
      setIsMilvusLoading(false);
      setMilvusError(null);
      // Catalog
      setCatalogQuery('');
      setCatalogSender('');
      setCatalogDateFrom('');
      setCatalogDateTo('');
      setCatalogResults([]);
      setIsCatalogLoading(false);
      setCatalogError(null);
      // Common
      setTokenConfig(null);
      setIsLoadingConfig(false);
      setConfigError(null);
      setKbTokenValue(null);
      setIsLoadingTokenValue(false);
    }
  }, [isOpen]);

  // Fetch token config AND KB token value using getTokenDetails
  useEffect(() => {
    if (isOpen && tokenId) {
      setTokenConfig(null);
      setKbTokenValue(null);
      // Use a single loading state now as both come from one call
      setIsLoadingConfig(true);
      setConfigError(null); 

      const fetchDetails = async () => {
        try {
          // Fetch details using the modified getTokenDetails
          const detailsResponse = await getTokenDetails(tokenId);
          
          setTokenConfig(detailsResponse); // Store the full details
          
          // Check if the response includes the token_value (backend logic ensures this is only for owner)
          if (detailsResponse && detailsResponse.token_value) {
              const tokenValue = detailsResponse.token_value.trim(); // Trim to remove whitespace
              console.log(`Token value received from API. Length: ${tokenValue.length}, Preview: ${tokenValue.substring(0, 10)}...`);
              
              // Check if the token value is just the prefix (no period)
              if (!tokenValue.includes('.')) {
                console.log(`Token in owner-only mode: ${tokenValue}`);
                setKbTokenValue(tokenValue);
                // Don't show an info message - it's unnecessary
                setConfigError(null);
              } else {
                // Full token value with secret received
                setKbTokenValue(tokenValue);
                setConfigError(null);
              }
          } else {
              // Could not get token value at all
              console.error(`Token value missing for token ID ${tokenId}. User may not be the owner.`);
              setConfigError(t(`${KEY_PREFIX}.errors.missingTokenValueOwner`, 'Could not retrieve token. Ensure you are the owner.'));
              setKbTokenValue(null);
          }

        } catch (err: any) {
          console.error(`Error fetching token details for ID ${tokenId}:`, err);
          setConfigError(err.message || t('common.error.failedToLoadDetails', 'Failed to load token details.'));
          setKbTokenValue(null);
        } finally {
          setIsLoadingConfig(false); // Single loading state controls both now
        }
      };
      fetchDetails(); 
    }
  }, [isOpen, tokenId, t]);

  // --- Handlers ---
  const handleMilvusSearch = async () => {
    if (!tokenId || !milvusQuery.trim()) {
      setMilvusError(t(`${KEY_PREFIX}.errors.missingQuery`, 'Please enter a query.'));
      return;
    }

    setIsMilvusLoading(true);
    setMilvusError(null);
    setMilvusResults([]);

    try {
      const searchResults = await testTokenSearch(tokenId, milvusQuery);
      setMilvusResults(searchResults);
      if (searchResults.length === 0) {
        toast({
          title: t(`${KEY_PREFIX}.toast.noMilvusResultsTitle`, 'No Milvus Results'),
          description: t(`${KEY_PREFIX}.toast.noMilvusResultsDesc`, 'Milvus query returned no results based on token permissions.'),
          status: 'info',
          duration: 4000,
          isClosable: true,
        });
      }
    } catch (err: any) {
      setMilvusError(err.message || t(`${KEY_PREFIX}.errors.milvusSearchFailed`, 'Milvus search failed.'));
    } finally {
      setIsMilvusLoading(false);
    }
  };

  const handleCatalogSearch = async () => {
    if (!tokenId || !catalogQuery.trim()) {
      setCatalogError(t(`${KEY_PREFIX}.errors.missingQuery`, 'Please enter a query.'));
      return;
    }
    
    // We can handle two scenarios for authentication:
    // 1. Full token value with secret (preferred)
    // 2. Just the token prefix (when the user is the owner and has logged in)
    
    // We either need a valid full token value OR at least the token prefix from the config
    if (!kbTokenValue && (!tokenConfig || !tokenConfig.token_prefix)) {
      const errorMsg = t(`${KEY_PREFIX}.errors.missingTokenValue`, 'Could not retrieve token for testing.');
      setCatalogError(errorMsg);
      toast({ title: errorMsg, status: 'error', duration: 3000 });
      return;
    }

    // Either use the full token value OR fall back to just the prefix
    const tokenToUse = kbTokenValue || tokenConfig.token_prefix;
    console.log(`Using token identifier for catalog search. Length: ${tokenToUse.length}, Type: ${kbTokenValue ? 'full token' : 'prefix only'}`);
    
    setIsCatalogLoading(true);
    setCatalogError(null);
    setCatalogResults([]);

    try {
      const searchRequest: CatalogSearchRequest = {
        query: catalogQuery,
        limit: parseInt(catalogLimit, 10) || 10
      };
      
      // Add optional filters if set
      if (catalogSender) {
        searchRequest.sender = catalogSender;
      }
      
      if (catalogDateFrom) {
        searchRequest.date_from = catalogDateFrom;
      }
      
      if (catalogDateTo) {
        searchRequest.date_to = catalogDateTo;
      }

      let results;
      
      // Check if we're working with just a token prefix (no period)
      // If so, use the ownerTestTokenCatalogSearch function which calls the owner endpoint
      if (tokenToUse && !tokenToUse.includes('.')) {
        console.log('Using owner-specific endpoint for catalog search (token prefix only)');
        results = await ownerTestTokenCatalogSearch(tokenId, tokenToUse, searchRequest);
      } else {
        // Use the regular endpoint with full token value
        console.log('Using standard endpoint for catalog search (full token)');
        results = await testTokenCatalogSearch(tokenId, searchRequest, tokenToUse);
      }
      
      setCatalogResults(results);
      if (results.length === 0) {
        setCatalogError(t(`${KEY_PREFIX}.errors.noResults`, 'No results found'));
      }
    } catch (error: any) {
      console.error('Catalog search error:', error);
      setCatalogError(error.message || t(`${KEY_PREFIX}.errors.searchError`, 'Error performing search'));
    } finally {
      setIsCatalogLoading(false);
    }
  };

  // Add a debug function
  const handleDebugToken = async () => {
    if (!tokenId) return;
    
    try {
      const debugInfo = await debugTokenValue(tokenId);
      console.log("Token debug info:", debugInfo);
      
      // Display debug info to user
      toast({
        title: "Token Debug Info",
        description: `Prefix: ${debugInfo.prefix}, Secret length: ${debugInfo.secret_length}, Has period: ${debugInfo.contains_period}`,
        status: "info",
        duration: 5000,
        isClosable: true
      });
    } catch (err: any) {
      console.error("Error debugging token:", err);
      toast({
        title: "Token Debug Failed",
        description: err.message || "Could not debug token value",
        status: "error",
        duration: 3000,
        isClosable: true
      });
    }
  };

  // --- Render ---
  const resultBg = useColorModeValue('gray.50', 'gray.800');
  const resultBorderColor = useColorModeValue('gray.200', 'gray.600');

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="3xl" scrollBehavior="inside"> {/* Increased size */}
      <ModalOverlay />
      <ModalContent as="div">
        <ModalHeader>
          {t(`${KEY_PREFIX}.title`, 'Test Token:')}
          {tokenName && ` "${tokenName}"`}
          {tokenId && ` (ID: ${tokenId})`}
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          <VStack spacing={4} align="stretch">
            {/* Token Configuration Display (Unchanged) */}
            <Box borderWidth="1px" borderRadius="md" p={4} bg={useColorModeValue('gray.50', 'gray.700')}>
               <Text fontSize="lg" fontWeight="semibold" mb={2}>{t(`${KEY_PREFIX}.configuration`, 'Token Configuration')}</Text>
               {isLoadingConfig ? <Spinner size="md" /> : configError && configError.includes('Could not retrieve token') ? (
                 <Box>
                   <Alert status="error" borderRadius="md" mb={2}>
                     <AlertIcon />
                     {configError}
                   </Alert>
                   {tokenConfig && tokenConfig.is_editable !== false && (
                     <Button 
                       size="sm" 
                       colorScheme="orange" 
                       onClick={() => window.location.href = `/tokens/edit/${tokenId}`}
                     >
                       {t(`${KEY_PREFIX}.regenerateToken`, 'Edit/Regenerate Token')}
                     </Button>
                   )}
                 </Box>
               ) : tokenConfig ? (
                 <VStack align="stretch" spacing={2}>
                    {/* Display Sensitivity, Allow/Deny Rules as before */}
                    <HStack>
                        <Text fontWeight="medium" minW="120px">{t(`${KEY_PREFIX}.sensitivity`, 'Sensitivity:')}</Text>
                        <Badge colorScheme={getSensitivityColorScheme(tokenConfig?.sensitivity)}>{tokenConfig?.sensitivity ?? t('common.notAvailable', 'N/A')}</Badge>
                    </HStack>
                    <HStack align="start">
                        <Text fontWeight="medium" minW="120px" mt={1}>{t(`${KEY_PREFIX}.allowRules`, 'Allow Rules:')}</Text>
                        <Box>{tokenConfig?.allow_rules?.length > 0 ? tokenConfig.allow_rules.map((rule: string, index: number) => <Tag key={`allow-${index}`} size="sm" mr={1} mb={1} variant="outline" colorScheme="green">{rule}</Tag>) : <Text fontStyle="italic" color={useColorModeValue('gray.500', 'gray.400')}>{t(`${KEY_PREFIX}.noneDefined`, 'None defined')}</Text>}</Box>
                    </HStack>
                    <HStack align="start">
                        <Text fontWeight="medium" minW="120px" mt={1}>{t(`${KEY_PREFIX}.denyRules`, 'Deny Rules:')}</Text>
                        <Box>{tokenConfig?.deny_rules?.length > 0 ? tokenConfig.deny_rules.map((rule: string, index: number) => <Tag key={`deny-${index}`} size="sm" mr={1} mb={1} variant="outline" colorScheme="red">{rule}</Tag>) : <Text fontStyle="italic" color={useColorModeValue('gray.500', 'gray.400')}>{t(`${KEY_PREFIX}.noneDefined`, 'None defined')}</Text>}</Box>
                    </HStack>
                    {/* Display allow_columns */}
                     <HStack align="start">
                        <Text fontWeight="medium" minW="120px" mt={1}>{t(`${KEY_PREFIX}.allowColumns`, 'Allow Columns:')}</Text>
                        <Box>{tokenConfig?.allow_columns?.length > 0 ? tokenConfig.allow_columns.map((col: string, index: number) => <Tag key={`col-${index}`} size="sm" mr={1} mb={1} variant="subtle" colorScheme="purple">{col}</Tag>) : <Text fontStyle="italic" color={useColorModeValue('gray.500', 'gray.400')}>{t(`${KEY_PREFIX}.allColumns`, 'All columns allowed')}</Text>}</Box>
                    </HStack>
                    {/* Display row_limit */}
                    <HStack>
                        <Text fontWeight="medium" minW="120px">{t(`${KEY_PREFIX}.rowLimit`, 'Row Limit:')}</Text>
                        <Text>{tokenConfig?.row_limit ?? t('common.unlimited', 'Unlimited')}</Text>
                    </HStack>
                    {/* Display KB token status based on whether kbTokenValue state is set */}
                    <HStack>
                      <Text fontWeight="medium" minW="120px">{t(`${KEY_PREFIX}.kbTokenStatus`, 'Auth Status:')}</Text>
                      {kbTokenValue ? 
                        (!kbTokenValue.includes('.') ?
                          <Badge colorScheme="green">{t('common.ready', 'Ready')}</Badge> :
                          <Badge colorScheme="green">{t('common.valid', 'Valid')}</Badge>
                        ) : 
                        <Badge colorScheme="red">{t('common.error', 'Error/Unavailable')}</Badge> 
                      }
                    </HStack>
                 </VStack>
               ) : <Text>{t(`${KEY_PREFIX}.failedToLoadConfig`, 'Could not load configuration.')}</Text>}
             </Box>

            {/* Tabs for Search Types */}
            <Tabs isFitted variant="enclosed" onChange={(index) => setSearchType(index === 0 ? 'milvus' : 'catalog')}>
              <TabList mb="1em">
                <Tab>{t(`${KEY_PREFIX}.tabMilvus`, 'Unstructured Search (Milvus)')}</Tab>
                <Tab>{t(`${KEY_PREFIX}.tabCatalog`, 'Structured Search (Catalog)')}</Tab>
              </TabList>
              <TabPanels>
                {/* Milvus Search Panel */}
                <TabPanel p={0}>
                  <VStack spacing={4} align="stretch">
                    <FormControl isInvalid={!!milvusError}>
                      <FormLabel htmlFor="milvus-query">{t(`${KEY_PREFIX}.queryLabel`, 'Test Query')}</FormLabel>
                      <Input
                        id="milvus-query"
                        value={milvusQuery}
                        onChange={(e) => setMilvusQuery(e.target.value)}
                        placeholder={t(`${KEY_PREFIX}.milvusQueryPlaceholder`, 'Enter search query for Milvus...')}
                      />
                      {milvusError && <FormErrorMessage>{milvusError}</FormErrorMessage>}
                    </FormControl>
                    <Button
                      colorScheme="blue"
                      onClick={handleMilvusSearch}
                      isLoading={isMilvusLoading}
                      loadingText={t(`${KEY_PREFIX}.milvusLoading`, 'Searching Milvus...')}
                    >
                      {t(`${KEY_PREFIX}.runMilvusButton`, 'Run Milvus Search')}
                    </Button>
                    {milvusResults.length > 0 && (
                      <Box mt={4}>
                        <Text fontSize="lg" fontWeight="semibold" mb={2}>{t(`${KEY_PREFIX}.milvusResultsTitle`, "Milvus Results")} ({milvusResults.length})</Text>
                        <VStack spacing={3} align="stretch" maxHeight="300px" overflowY="auto" pr={2}>
                          {milvusResults.map((result) => (
                            <Box key={result.id} borderWidth="1px" borderRadius="md" p={3} bg={useColorModeValue('white', 'gray.800')}>
                              <Text fontSize="sm" color="gray.500">{t('common.id', 'ID')}: {result.id}</Text>
                              <Text fontSize="sm" color="gray.500">{t('common.score', 'Score')}: {result.score?.toFixed(4)}</Text>
                              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: '0.8em', marginTop: '4px' }}>
                                {JSON.stringify(result.metadata || {}, null, 2)}
                              </pre>
                            </Box>
                          ))}
                        </VStack>
                      </Box>
                    )}
                    {!isMilvusLoading && !milvusError && milvusQuery && milvusResults.length === 0 && (
                        <Text mt={4} fontStyle="italic" color={useColorModeValue('gray.600', 'gray.400')}>
                            {t(`${KEY_PREFIX}.noMilvusResultsFound`, 'No Milvus results found matching the query and token permissions.')}
                        </Text>
                    )}
                  </VStack>
                </TabPanel>

                {/* Catalog Search Panel */}
                <TabPanel p={0}>
                   <VStack spacing={4} align="stretch">
                    {/* Query Input (Shared or specific) */}
                     <FormControl isInvalid={!!catalogError}>
                       <FormLabel htmlFor="catalog-query">{t(`${KEY_PREFIX}.queryLabel`, 'Test Query')}</FormLabel>
                       <Input
                         id="catalog-query"
                         value={catalogQuery}
                         onChange={(e) => setCatalogQuery(e.target.value)}
                         placeholder={t(`${KEY_PREFIX}.catalogQueryPlaceholder`, 'Enter search query for Catalog...')}
                       />
                       {/* Display general catalog error here if not field-specific */}
                     </FormControl>

                    {/* Catalog Specific Filters */}
                    <SimpleGrid columns={3} spacing={4}>
                        <FormControl>
                           <FormLabel htmlFor="catalog-sender">{t(`${KEY_PREFIX}.senderLabel`, 'Sender')}</FormLabel>
                           <Input
                             id="catalog-sender"
                             value={catalogSender}
                             onChange={(e) => setCatalogSender(e.target.value)}
                             placeholder={t(`${KEY_PREFIX}.senderPlaceholder`, 'Optional: email or name')}
                           />
                        </FormControl>
                         <FormControl>
                           <FormLabel htmlFor="catalog-date-from">{t(`${KEY_PREFIX}.dateFromLabel`, 'Date From')}</FormLabel>
                           <Input
                             id="catalog-date-from"
                             type="date"
                             value={catalogDateFrom}
                             onChange={(e) => setCatalogDateFrom(e.target.value)}
                           />
                        </FormControl>
                         <FormControl>
                           <FormLabel htmlFor="catalog-date-to">{t(`${KEY_PREFIX}.dateToLabel`, 'Date To')}</FormLabel>
                           <Input
                             id="catalog-date-to"
                             type="date"
                             value={catalogDateTo}
                             onChange={(e) => setCatalogDateTo(e.target.value)}
                           />
                        </FormControl>
                    </SimpleGrid>
                    
                    <FormControl>
                      <FormLabel>{t(`${KEY_PREFIX}.limit`, 'Result Limit')}</FormLabel>
                      <NumberInput min={1} max={100} value={catalogLimit} onChange={(value) => setCatalogLimit(value)}>
                        <NumberInputField placeholder="10" />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                    </FormControl>
                    
                    {/* Display specific catalog error */}
                    {catalogError && (
                        <Alert status="error" borderRadius="md">
                            <AlertIcon />
                            {catalogError}
                        </Alert>
                    )}

                     <Button
                       colorScheme="teal" // Different color for distinction
                       onClick={handleCatalogSearch}
                       isLoading={isCatalogLoading} // Only track catalog search loading here
                       isDisabled={isLoadingConfig || (!kbTokenValue && (!tokenConfig || !tokenConfig.token_prefix))} // Enable if we have either full token OR just prefix
                       loadingText={t(`${KEY_PREFIX}.catalogLoading`, 'Searching Catalog...')}
                     >
                       {t(`${KEY_PREFIX}.runCatalogButton`, 'Run Catalog Search')}
                     </Button>

                    {/* Catalog Results Display */}
                     {catalogResults.length > 0 && (
                       <Box mt={4}>
                         <Text fontSize="lg" fontWeight="semibold" mb={2}>{t(`${KEY_PREFIX}.catalogResultsTitle`, "Catalog Results")} ({catalogResults.length})</Text>
                         {/* Use Textarea for raw JSON display */}
                          <Textarea
                            isReadOnly
                            value={JSON.stringify(catalogResults, null, 2)}
                            fontFamily="monospace"
                            fontSize="sm"
                            height="300px" // Adjust height as needed
                            bg={useColorModeValue('gray.50', 'gray.900')}
                          />
                       </Box>
                     )}
                     {!isCatalogLoading && !catalogError && catalogQuery && catalogResults.length === 0 && (
                        <Text mt={4} fontStyle="italic" color={useColorModeValue('gray.600', 'gray.400')}>
                            {t(`${KEY_PREFIX}.noCatalogResultsFound`, 'No Catalog results found matching the query, filters, and token permissions.')}
                        </Text>
                     )}
                   </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button size="sm" colorScheme="blue" mr={3} onClick={handleDebugToken}>
            Debug Token
          </Button>
          <Button onClick={onClose}>
            {t('common.close', 'Close')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

// Helper function for sensitivity badge color (Unchanged)
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