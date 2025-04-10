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
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FaRobot, FaUser } from 'react-icons/fa';
import { sendChatMessage } from '../api/chat';
import { getOpenAIApiKey, saveOpenAIApiKey } from '../api/user';

// Types for LLM models
interface LLMModel {
  id: string;
  name: string;
  provider: string;
  requiresKey: boolean;
}

// Reduced list of models to improve initial load time
const AVAILABLE_MODELS: LLMModel[] = [
  { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', provider: 'OpenAI', requiresKey: true },
  { id: 'gpt-4', name: 'GPT-4', provider: 'OpenAI', requiresKey: true },
  { id: 'claude-3-opus', name: 'Claude 3 Opus', provider: 'Anthropic', requiresKey: true },
  { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'Google', requiresKey: true },
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
  const [selectedModel, setSelectedModel] = useState<string>('gpt-3.5-turbo'); // Default model
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<Array<{ role: 'user' | 'assistant', content: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [apiKeyLoading, setApiKeyLoading] = useState(false); // Changed to false initially to prevent blocking UI
  const [apiKeyError, setApiKeyError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);

  // Initialize with a welcome message immediately
  useEffect(() => {
    setChatHistory([
      { 
        role: 'assistant', 
        content: t('jarvis.welcomeMessage', 'Hello! I am Jarvis, your AI assistant. How can I help you today?')
      }
    ]);
  }, [t]);

  // Load saved API keys separately after the UI has rendered
  useEffect(() => {
    const loadApiKeys = async () => {
      try {
        setApiKeyLoading(true);
        setApiKeyError(null);
        
        const openaiKey = await getOpenAIApiKey();
        
        if (openaiKey) {
          setApiKeys(prev => ({
            ...prev,
            'OpenAI': openaiKey
          }));
        }
        
      } catch (error) {
        console.error("Failed to load API keys:", error);
        setApiKeyError("Failed to load saved API keys");
      } finally {
        setApiKeyLoading(false);
      }
    };
    
    // Small delay to allow page to render first
    const timer = setTimeout(() => {
      loadApiKeys();
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
    setApiKeys(prev => ({
      ...prev,
      [provider]: key
    }));
  };

  // Save API keys
  const handleSaveApiKey = async (provider: string) => {
    try {
      if (provider === 'OpenAI' && apiKeys['OpenAI']) {
        await saveOpenAIApiKey(apiKeys['OpenAI']);
        toast({
          title: t('common.success'),
          description: t('jarvis.apiKeySaved', 'API key saved successfully'),
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error(`Failed to save ${provider} API key:`, error);
      toast({
        title: t('common.error'),
        description: t('jarvis.apiKeySaveError', 'Failed to save API key'),
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
              {/* Settings Interface */}
              <VStack spacing={6} align="stretch">
                <FormControl>
                  <FormLabel>{t('jarvis.settingsContent.selectModel')}</FormLabel>
                  <Select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                  >
                    {AVAILABLE_MODELS.map(model => (
                      <option key={model.id} value={model.id}>
                        {model.name} ({model.provider})
                      </option>
                    ))}
                  </Select>
                </FormControl>

                {/* API Key Inputs - Grouped by Provider with Save Buttons */}
                {uniqueProviders.map(provider => (
                  <FormControl key={provider}>
                    <FormLabel>
                      {t('jarvis.settingsContent.apiKey', { provider })}
                    </FormLabel>
                    <HStack>
                      <Input
                        type="password"
                        value={apiKeys[provider] || ''}
                        onChange={(e) => handleApiKeyUpdate(provider, e.target.value)}
                        placeholder={t('jarvis.settingsContent.apiKeyPlaceholder')}
                      />
                      <Button
                        onClick={() => handleSaveApiKey(provider)}
                        isDisabled={!apiKeys[provider]}
                        colorScheme="green"
                        size="md"
                      >
                        {t('common.save')}
                      </Button>
                    </HStack>
                  </FormControl>
                ))}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Container>
  );
};

export default JarvisPage; 