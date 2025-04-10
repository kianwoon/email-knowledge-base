import React, { useState, useMemo, useEffect, useRef } from 'react';
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
  Icon,
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
  const [lastKeyRefresh, setLastKeyRefresh] = useState(0);

  // Ref for the chat container
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Reference for the refresh interval
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Define chat message type
  type ChatMessage = {
    role: 'user' | 'assistant';
    content: string;
  };

  // Initialize with a welcome message or load existing chat history
  useEffect(() => {
    // Try to load existing chat history from sessionStorage
    const savedHistory = sessionStorage.getItem('jarvis_chat_history');
    if (savedHistory) {
      try {
        const parsedHistory = JSON.parse(savedHistory) as ChatMessage[];
        // Validate the parsed history
        if (Array.isArray(parsedHistory) && parsedHistory.every(msg => 
          (msg.role === 'user' || msg.role === 'assistant') && typeof msg.content === 'string'
        )) {
          setChatHistory(parsedHistory);
        } else {
          throw new Error('Invalid chat history format');
        }
      } catch (e) {
        console.error("Failed to parse saved chat history:", e);
        // If parsing fails, set default welcome message
        setChatHistory([
          { 
            role: 'assistant' as const, 
            content: t('jarvis.welcomeMessage', 'Hello! I am Jarvis, your AI assistant. How can I help you today?')
          }
        ]);
      }
    } else {
      // If no saved history, set default welcome message
      setChatHistory([
        { 
          role: 'assistant' as const, 
          content: t('jarvis.welcomeMessage', 'Hello! I am Jarvis, your AI assistant. How can I help you today?')
        }
      ]);
    }
  }, [t]);

  // Save chat history to sessionStorage whenever it changes
  useEffect(() => {
    if (chatHistory.length > 0) {
      sessionStorage.setItem('jarvis_chat_history', JSON.stringify(chatHistory));
    }
  }, [chatHistory]);

  // Load saved default model
  useEffect(() => {
    const loadDefaultModel = async () => {
      try {
        // Check sessionStorage first
        const cachedModel = sessionStorage.getItem('jarvis_default_model');
        if (cachedModel) {
          setSelectedModel(cachedModel);
          setModelLoading(false);
          return;
        }

        setModelLoading(true);
        const model = await getDefaultModel();
        setSelectedModel(model);
        // Cache the result
        sessionStorage.setItem('jarvis_default_model', model);
      } catch (error) {
        console.error("Error loading default model:", error);
      } finally {
        setModelLoading(false);
      }
    };
    
    loadDefaultModel();
  }, []);

  // Initial load of API keys
  useEffect(() => {
    const loadInitialKeys = async () => {
      // Check if we already have keys in sessionStorage
      const cachedKeys = sessionStorage.getItem('jarvis_api_keys');
      if (cachedKeys) {
        try {
          const parsed = JSON.parse(cachedKeys);
          setApiKeys(parsed);
          setHasApiKey(Object.keys(parsed).length > 0);
          return;
        } catch (e) {
          console.error("Failed to parse cached API keys:", e);
        }
      }

      // If no cached keys, load from database
      await loadApiKeys(false);
    };

    loadInitialKeys();
  }, []); // Run only on mount

  // Load keys only when entering Settings tab
  useEffect(() => {
    if (activeTab === 1) { // Settings tab
      loadApiKeys(false);
    }
  }, [activeTab]);

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

  const loadApiKeys = async (isBackgroundRefresh = false) => {
    if (!isBackgroundRefresh) {
      setApiKeyLoading(true);
      setApiKeyError(null);
    }

    try {
      const providersToCheck: ApiProvider[] = ['openai', 'anthropic', 'google'];
      
      const keyPromises = providersToCheck.map(async (provider) => {
        try {
          let apiKey: string | null = null;
          if (provider === 'openai') {
            try {
              apiKey = await getOpenAIApiKey();
              if (apiKey === null) {
                apiKey = await getProviderApiKey(provider);
              }
            } catch (legacyError) {
              apiKey = await getProviderApiKey(provider);
            }
          } else {
            apiKey = await getProviderApiKey(provider);
          }
          return { provider, apiKey };
        } catch (error) {
          console.error(`Error loading ${provider} API key:`, error);
          return { provider, apiKey: null };
        }
      });

      const results = await Promise.allSettled(keyPromises);
      const newApiKeys: Record<string, string> = {};
      let hasAnyKey = false;
      
      results.forEach((result) => {
        if (result.status === 'fulfilled' && result.value.apiKey) {
          newApiKeys[result.value.provider] = result.value.apiKey;
          hasAnyKey = true;
        }
      });

      setApiKeys(newApiKeys);
      setHasApiKey(hasAnyKey);
      sessionStorage.setItem('jarvis_api_keys', JSON.stringify(newApiKeys));

      if (hasAnyKey) {
        setRetryCount(0);
        localStorage.setItem('jarvis_had_api_key', 'true');
      }
    } catch (error) {
      console.error("Failed to load API keys:", error);
      if (!isBackgroundRefresh) {
        setApiKeyError("Failed to load saved API keys");
      }
    } finally {
      if (!isBackgroundRefresh) {
        setApiKeyLoading(false);
      }
    }
  };

  // Handle API key updates
  const handleApiKeyUpdate = (provider: string, key: string) => {
    const newKeys = {
      ...apiKeys,
      [provider]: key
    };
    setApiKeys(newKeys);
  };

  // Save API keys
  const handleSaveApiKey = async (provider: string) => {
    try {
      if (!apiKeys[provider]) return;
      
      if (provider === 'openai') {
        await saveOpenAIApiKey(apiKeys[provider]);
      } else {
        await saveProviderApiKey(provider as ApiProvider, apiKeys[provider]);
      }
      
      // Update sessionStorage after successful save to DB
      sessionStorage.setItem('jarvis_api_keys', JSON.stringify(apiKeys));
      
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
        await deleteProviderApiKey('openai');
      } else {
        await deleteProviderApiKey(provider as ApiProvider);
      }
      
      // Update local state
      setApiKeys(prev => {
        const newKeys = { ...prev };
        delete newKeys[provider];
        return newKeys;
      });

      // Clear the cache to force a fresh load
      localStorage.removeItem('jarvis_api_keys');
      setLastKeyRefresh(0);
      
      toast({
        title: t('jarvis.apiKeyDeleted', 'API Key Deleted'),
        description: t('jarvis.apiKeyDeletedDesc', 'Your {{provider}} API key has been deleted.', { provider: provider.toUpperCase() }),
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      
      // Check if we still have any keys
      setTimeout(() => {
        loadApiKeys(false);
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

  // Update handleSendMessage to handle errors without breaking history
  const handleSendMessage = async () => {
    if (!message.trim() || isLoading) return;

    const userMessage: ChatMessage = { role: 'user', content: message };
    const currentHistory = [...chatHistory, userMessage];
    
    // Update UI and save to sessionStorage
    setChatHistory(currentHistory);
    sessionStorage.setItem('jarvis_chat_history', JSON.stringify(currentHistory));
    
    setMessage('');
    setIsLoading(true);

    try {
      // Send message with selected model
      const reply = await sendChatMessage(userMessage.content, chatHistory, selectedModel);
      
      // Add assistant response and save to sessionStorage
      const updatedHistory = [...currentHistory, { role: 'assistant' as const, content: reply }];
      setChatHistory(updatedHistory);
      sessionStorage.setItem('jarvis_chat_history', JSON.stringify(updatedHistory));
      
    } catch (error) {
      console.error("Failed to send message:", error);
      const errorMsg = (error instanceof Error) ? error.message : 'Failed to get response';
      
      // Add error message and save to sessionStorage
      const errorHistory = [...currentHistory, { role: 'assistant' as const, content: `Error: ${errorMsg}` }];
      setChatHistory(errorHistory);
      sessionStorage.setItem('jarvis_chat_history', JSON.stringify(errorHistory));
      
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

  // useEffect to scroll chat to bottom
  useEffect(() => {
    if (chatContainerRef.current) {
      const { scrollHeight, clientHeight, scrollTop } = chatContainerRef.current;
      // Optional: Only auto-scroll if user isn't scrolled up significantly
      // You can adjust the threshold (e.g., 100 pixels)
      // const isScrolledUp = scrollHeight - scrollTop - clientHeight > 100;
      // if (!isScrolledUp) {
          chatContainerRef.current.scrollTop = scrollHeight;
      // }
    }
  }, [chatHistory]); // Dependency array includes chatHistory

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
                  ref={chatContainerRef}
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
                        <HStack align="flex-start">
                          <Icon as={msg.role === 'user' ? FaUser : FaRobot} mt={1} />
                          <Text whiteSpace="pre-wrap" flex="1">{msg.content}</Text>
                        </HStack>
                      </Box>
                    </Flex>
                  ))}
                  {/* Typing Indicator */} 
                  {isLoading && (
                    <Flex w="full" justify="flex-start" mb={3}>
                      <Box maxW="80%" bg={assistantBg} color={textColor} px={4} py={2} borderRadius="lg" boxShadow="sm">
                        <HStack>
                          <Spinner size="xs" />
                          <Text fontSize="sm" fontStyle="italic">{t('jarvis.thinking', 'Jarvis is thinking...')}</Text>
                        </HStack>
                      </Box>
                    </Flex>
                  )}
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