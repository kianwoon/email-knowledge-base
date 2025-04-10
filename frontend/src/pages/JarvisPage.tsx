import React, { useState, useMemo, useEffect } from 'react';
import {
  Box,
  Container,
  VStack,
  Heading,
  Select,
  FormControl,
  FormLabel,
  Input,
  Button,
  Text,
  useToast,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Textarea,
  HStack,
  Flex,
  useColorModeValue,
  Spinner,
  Alert,
  AlertIcon,
  InputGroup,
  InputRightElement,
  Divider,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FaRobot, FaUser, FaSync } from 'react-icons/fa';
import { sendChatMessage } from '../api/chat';
import { getOpenAIApiKey, saveOpenAIApiKey, getAllApiKeys, getProviderApiKey, saveProviderApiKey, ApiProvider, deleteProviderApiKey, saveDefaultModel, getDefaultModel } from '../api/user';

// Types for LLM models
interface LLMModel {
  id: string;
  name: string;
  provider: ApiProvider;
  requiresKey: boolean;
}

// Expanded list of models with multiple providers
const AVAILABLE_MODELS: LLMModel[] = [
  { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', provider: 'openai', requiresKey: true },
  { id: 'gpt-4', name: 'GPT-4', provider: 'openai', requiresKey: true },
  { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', provider: 'openai', requiresKey: true },
  { id: 'claude-3-opus', name: 'Claude 3 Opus', provider: 'anthropic', requiresKey: true },
  { id: 'claude-3-sonnet', name: 'Claude 3 Sonnet', provider: 'anthropic', requiresKey: true },
  { id: 'claude-3-haiku', name: 'Claude 3 Haiku', provider: 'anthropic', requiresKey: true },
  { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'google', requiresKey: true },
  { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', provider: 'google', requiresKey: true },
];

const JarvisPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  
  // Memoize color values to prevent recalculations
  const userBg = useColorModeValue('blue.50', 'blue.900');
  const assistantBg = useColorModeValue('gray.100', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const textColor = useColorModeValue('gray.800', 'whiteAlpha.900');

  // State for model selection and API keys
  const [selectedModel, setSelectedModel] = useState<string>('gpt-3.5-turbo'); // Default model initially, will be updated
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<Array<{ role: 'user' | 'assistant', content: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [apiKeyLoading, setApiKeyLoading] = useState(false); 
  const [modelLoading, setModelLoading] = useState(true); // Added loading state for model
  const [apiKeyError, setApiKeyError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [isRetry, setIsRetry] = useState(false);
  const [lastLoadTime, setLastLoadTime] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [savingDefaultModel, setSavingDefaultModel] = useState(false);

  // Initialize with a welcome message immediately
  useEffect(() => {
    setChatHistory([
      { 
        role: 'assistant', 
        content: t('jarvis.welcomeMessage', 'Hello! I am Jarvis, your AI assistant. How can I help you today?')
      }
    ]);
  }, [t]);

  // Load saved default model
  useEffect(() => {
    const loadDefaultModel = async () => {
      try {
        setModelLoading(true);
        const model = await getDefaultModel();
        setSelectedModel(model);
      } catch (error) {
        console.error("Error loading default model:", error);
      } finally {
        setModelLoading(false);
      }
    };
    
    loadDefaultModel();
  }, []);

  // Load saved API keys
  useEffect(() => {
    // Small delay to allow page to render first
    const timer = setTimeout(() => {
      loadApiKeys(false);
      
      // Also set up a refresh interval to check for API keys periodically
      const refreshInterval = setInterval(() => {
        loadApiKeys(true);
      }, 30000); // Check every 30 seconds
      
      return () => {
        clearInterval(refreshInterval);
      };
    }, 100);
    
    return () => clearTimeout(timer);
  }, []);

  // Get unique providers from the models list - memoized
  const uniqueProviders = useMemo(() => {
    const providers = new Set<string>();
    AVAILABLE_MODELS.forEach(model => {
      if (model.requiresKey) {
        providers.add(model.provider);
      }
    });
    return Array.from(providers);
  }, []);

  // Handle API key updates
  const handleApiKeyUpdate = (provider: string, key: string) => {
    console.log(`Updating ${provider} API key to length: ${key.length}`);
    setApiKeys(prev => ({
      ...prev,
      [provider]: key
    }));
  };

  // Save API keys
  const handleSaveApiKey = async (provider: string) => {
    try {
      if (!apiKeys[provider]) return;
      
      console.log(`Saving ${provider} API key of length: ${apiKeys[provider].length}`);
      
      if (provider === 'openai') {
        // Use legacy endpoint for backward compatibility
        await saveOpenAIApiKey(apiKeys[provider]);
      } else {
        // Use new provider-specific endpoint
        await saveProviderApiKey(provider as ApiProvider, apiKeys[provider]);
      }
      
      toast({
        title: t('jarvis.apiKeySaved', 'API Key Saved'),
        description: t('jarvis.apiKeySavedDesc', 'Your {{provider}} API key has been saved successfully.', { provider: provider.toUpperCase() }),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      
      setHasApiKey(true);
      localStorage.setItem('jarvis_had_api_key', 'true');
    } catch (error) {
      console.error(`Error saving ${provider} API key:`, error);
      toast({
        title: t('jarvis.apiKeySaveError', 'Error Saving API Key'),
        description: error instanceof Error ? error.message : String(error),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Delete API key
  const handleDeleteApiKey = async (provider: string) => {
    try {
      if (provider === 'openai') {
        // Use legacy endpoint for backward compatibility
        await deleteProviderApiKey('openai');
      } else {
        // Use new provider-specific endpoint
        await deleteProviderApiKey(provider as ApiProvider);
      }
      
      // Update local state
      setApiKeys(prev => {
        const newKeys = { ...prev };
        delete newKeys[provider];
        return newKeys;
      });
      
      toast({
        title: t('jarvis.apiKeyDeleted', 'API Key Deleted'),
        description: t('jarvis.apiKeyDeletedDesc', 'Your {{provider}} API key has been deleted.', { provider: provider.toUpperCase() }),
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      
      // Check if we still have any keys
      setTimeout(() => {
        loadApiKeys();
      }, 500);
    } catch (error) {
      console.error(`Error deleting ${provider} API key:`, error);
      toast({
        title: t('jarvis.apiKeyDeleteError', 'Error Deleting API Key'),
        description: error instanceof Error ? error.message : String(error),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Update chat submission handler
  const handleSendMessage = async () => {
    if (!message.trim() || isLoading) return;

    const userMessage = { role: 'user' as const, content: message };
    // Optimistically update UI
    setChatHistory(prev => [...prev, userMessage]);
    setMessage('');
    setIsLoading(true);

    try {
      // Send message with selected model
      const reply = await sendChatMessage(userMessage.content, chatHistory, selectedModel);
      
      // Add assistant response
      setChatHistory(prev => [...prev, { role: 'assistant', content: reply }]);
      
    } catch (error) {
      console.error("Failed to send message:", error);
      const errorMsg = (error instanceof Error) ? error.message : 'Failed to get response';
      setChatHistory(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${errorMsg}` }
      ]);
      toast({
        title: t('common.error'),
        description: errorMsg || t('errors.chatFailed'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const loadApiKeys = async (isBackgroundRefresh = false) => {
    const now = Date.now();
    if (!isRetry && !isBackgroundRefresh && now - lastLoadTime < 1000) {
      console.log("Throttling API key load requests");
      return;
    }
    setLastLoadTime(now);

    if (!isBackgroundRefresh) {
      setApiKeyLoading(true);
      if (!isRetry) setApiKeyError(null);
    }

    try {
      // List of providers to check
      const providersToCheck: ApiProvider[] = ['openai', 'anthropic', 'google'];
      
      // Create an array of promises for fetching keys
      const keyPromises = providersToCheck.map(async (provider) => {
        try {
          let apiKey: string | null = null;
          // Special handling for OpenAI: try legacy endpoint first
          if (provider === 'openai') {
            try {
              apiKey = await getOpenAIApiKey();
              // If legacy returns null, still try the provider-specific one
              if (apiKey === null) {
                console.log("OpenAI legacy returned null, trying provider endpoint...");
                apiKey = await getProviderApiKey(provider);
              }
            } catch (legacyError) {
              console.warn("Error loading OpenAI key via legacy, trying provider endpoint...", legacyError);
              // Fallback to provider-specific endpoint on error
              apiKey = await getProviderApiKey(provider);
            }
          } else {
            // For other providers, use the standard endpoint
            apiKey = await getProviderApiKey(provider);
          }
          console.log(`${provider} fetch result: ${apiKey ? 'Found' : 'Not found'}`);
          return { provider, apiKey }; // Return object with provider and key
        } catch (error) {
          console.error(`Error loading ${provider} API key:`, error);
          // Return null key on error for this specific provider
          return { provider, apiKey: null };
        }
      });

      // Wait for all promises to settle (either succeed or fail)
      const results = await Promise.allSettled(keyPromises);

      // Process the results
      const newApiKeys: Record<string, string> = {};
      let hasAnyKey = false;
      
      results.forEach((result) => {
        if (result.status === 'fulfilled' && result.value.apiKey) {
          newApiKeys[result.value.provider] = result.value.apiKey;
          hasAnyKey = true;
        }
        // We don't need to do anything for 'rejected' status here 
        // because the individual promises already catch errors and return apiKey: null
      });

      console.log("Final API keys state after parallel fetch:", newApiKeys);

      // Update state
      setApiKeys(newApiKeys);
      setHasApiKey(hasAnyKey);

      // Reset retry count on success
      if (hasAnyKey) {
        setRetryCount(0);
        localStorage.setItem('jarvis_had_api_key', 'true');
      } 
      // Keep toast logic for non-background refreshes if no keys are found
      else if (!isBackgroundRefresh) {
        const hadApiKey = localStorage.getItem('jarvis_had_api_key') === 'true';
        if (hadApiKey && activeTab === 0) {
          toast({
            title: t('jarvis.apiKeyMissing', 'API Key Missing'),
            description: t('jarvis.apiKeyMissingAfterLogin', 'Your API key could not be loaded after login. Please try refreshing the page or re-entering your API key.'),
            status: 'warning',
            duration: 8000,
            isClosable: true,
          });
        } else if (activeTab === 0 && !hadApiKey) {
          toast({
            title: t('jarvis.noApiKey', 'API Key Required'),
            description: t('jarvis.apiKeyRequired', 'You need to provide your API key to use Jarvis. Please add it in the settings tab.'),
            status: 'info',
            duration: 8000,
            isClosable: true,
          });
        }
      }

    } catch (error) { // Catch potential errors from Promise.allSettled or state updates
      console.error("Failed to load API keys (outer catch):", error);
      if (!isBackgroundRefresh) {
        setApiKeyError("Failed to load saved API keys");
      }
    } finally {
      if (!isBackgroundRefresh) {
        setApiKeyLoading(false);
      }
    }
  };

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newModel = e.target.value;
    setSelectedModel(newModel);
  };

  const setModelAsDefault = async () => {
    try {
      setSavingDefaultModel(true);
      // Call the API to save the default model
      await saveDefaultModel(selectedModel);
      
      toast({
        title: t('jarvis.defaultModelSaved', 'Default Model Saved'),
        description: t('jarvis.defaultModelSavedDesc', 'Your default model preference has been saved.'),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error("Error saving default model:", error);
      toast({
        title: t('jarvis.defaultModelError', 'Error Saving Default Model'),
        description: error instanceof Error ? error.message : String(error),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setSavingDefaultModel(false);
    }
  };

  return (
    <Container maxW="container.xl" py={5}>
      <VStack spacing={5} align="stretch">
        <Heading>{t('jarvis.title')}</Heading>

        {apiKeyError && (
          <Alert status="warning">
            <AlertIcon />
            {apiKeyError} - {t('jarvis.continueWithoutKeys', 'You can continue without saved API keys.')}
          </Alert>
        )}

        <Tabs isLazy index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>{t('jarvis.chat')}</Tab>
            <Tab>{t('jarvis.settings')}</Tab>
          </TabList>

          <TabPanels>
            <TabPanel>
              {/* Chat Interface */}
              <VStack spacing={4} align="stretch">
                <Box
                  borderWidth={1}
                  borderColor={borderColor}
                  borderRadius="md"
                  p={4}
                  h={{ base: '50vh', md: '60vh' }}
                  overflowY="auto"
                  display="flex"
                  flexDirection="column"
                >
                  {chatHistory.map((msg, idx) => (
                    <Flex
                      key={idx}
                      w="full"
                      justify={msg.role === 'user' ? 'flex-end' : 'flex-start'}
                      mb={3}
                    >
                      <Box
                        maxW="80%"
                        bg={msg.role === 'user' ? userBg : assistantBg}
                        color={textColor}
                        px={4}
                        py={2}
                        borderRadius="lg"
                        boxShadow="sm"
                      >
                        <Text whiteSpace="pre-wrap">{msg.content}</Text>
                      </Box>
                    </Flex>
                  ))}
                  <Box flexGrow={1} />
                  {apiKeyLoading && (
                    <Flex justify="center" align="center" mt={2}>
                      <Spinner size="sm" mr={2} />
                      <Text fontSize="sm">{t('jarvis.loadingApiKeys', 'Loading API keys...')}</Text>
                    </Flex>
                  )}
                </Box>

                <HStack>
                  <Textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder={t('jarvis.messagePlaceholder')}
                    rows={3}
                    flex={1}
                    resize="none"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    disabled={isLoading}
                  />
                  <Button
                    colorScheme="blue"
                    onClick={handleSendMessage}
                    isDisabled={!message.trim() || isLoading}
                    isLoading={isLoading}
                    alignSelf="flex-end"
                  >
                    {t('common.send')}
                  </Button>
                </HStack>
              </VStack>
            </TabPanel>

            <TabPanel>
              {/* Settings Interface - Model Selection moved to top */}
              <Box>
                <Heading size="md" mb={4}>{t('jarvis.settingsTitle', 'API Settings')}</Heading>
                
                {/* Model Selection moved to top */}
                <Box mb={6} p={4} borderWidth="1px" borderRadius="md">
                  <Heading size="sm" mb={2}>{t('jarvis.settingsContent.modelSelection', 'Model Selection')}</Heading>
                  <Text fontSize="sm" mb={4}>
                    {t('jarvis.settingsContent.modelDescription', 'Select the AI model to use for chat')}
                  </Text>
                  
                  <FormControl>
                    <FormLabel>{t('jarvis.settingsContent.model', 'Model')}</FormLabel>
                    <HStack>
                      <Select 
                        value={selectedModel} 
                        onChange={handleModelChange}
                        flex="1"
                      >
                        {AVAILABLE_MODELS.map((model) => {
                          const hasRequiredKey = !model.requiresKey || !!apiKeys[model.provider];
                          return (
                            <option 
                              key={model.id} 
                              value={model.id}
                              disabled={!hasRequiredKey}
                            >
                              {model.name} {!hasRequiredKey ? `(${t('jarvis.requiresKey', 'Requires API Key')})` : ''}
                            </option>
                          );
                        })}
                      </Select>
                      <Button 
                        colorScheme="blue"
                        onClick={setModelAsDefault}
                        isLoading={savingDefaultModel}
                      >
                        {t('jarvis.setAsDefault', 'Set as Default')}
                      </Button>
                    </HStack>
                  </FormControl>
                </Box>
                
                <Text mb={4}>{t('jarvis.apiKeyDescription', 'To use Jarvis, you need to provide your own API keys from the following providers:')}</Text>
                
                {/* API Key sections */}
                {(['openai', 'anthropic', 'google'] as ApiProvider[]).map(provider => {
                  // Check if this provider has any models
                  const hasModels = AVAILABLE_MODELS.some(model => model.provider === provider);
                  if (!hasModels) return null;
                  
                  return (
                    <Box key={provider} mb={6} p={4} borderWidth="1px" borderRadius="md">
                      <Heading size="sm" mb={2}>{provider.toUpperCase()} {t('jarvis.settingsContent.apiKeyTitle')}</Heading>
                      <Text fontSize="sm" mb={4}>
                        {t(`jarvis.settingsContent.${provider}ApiKeyDescription`, 
                           `Enter your ${provider.toUpperCase()} API key to use ${provider.toUpperCase()} models.`)}
                      </Text>
                      
                      <FormControl mb={2}>
                        <FormLabel>{t('jarvis.settingsContent.apiKey', { provider: provider.toUpperCase() })}</FormLabel>
                        <InputGroup size="md">
                          <Input
                            type="password"
                            value={apiKeys[provider] || ''}
                            onChange={(e) => handleApiKeyUpdate(provider, e.target.value)}
                            placeholder={t('jarvis.settingsContent.apiKeyPlaceholder')}
                            borderColor={apiKeys[provider] ? 'green.300' : undefined}
                          />
                          <InputRightElement width="5.5rem">
                            <Button h="1.75rem" size="sm" mr={1}
                              onClick={() => handleSaveApiKey(provider)}
                              isDisabled={!apiKeys[provider]}
                              colorScheme={apiKeys[provider] ? 'green' : 'blue'}
                            >
                              {t('jarvis.save', 'Save')}
                            </Button>
                          </InputRightElement>
                        </InputGroup>
                      </FormControl>
                      
                      {apiKeys[provider] && (
                        <HStack justifyContent="space-between" mt={2}>
                          <Text fontSize="xs" color="green.500">
                            {t('jarvis.apiKeySet', '✓ API key set')}
                          </Text>
                          <Button 
                            size="xs" 
                            colorScheme="red" 
                            variant="ghost"
                            onClick={() => handleDeleteApiKey(provider)}
                          >
                            {t('jarvis.delete', 'Delete')}
                          </Button>
                        </HStack>
                      )}
                    </Box>
                  );
                })}
              </Box>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Container>
  );
};

export default JarvisPage; 