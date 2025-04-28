import React, { useState, useMemo, useEffect, useRef, memo } from 'react';
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
  Icon,
  TableContainer,
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
  Skeleton,
  Tag,
  IconButton,
  Stack,
  FormHelperText,
  Center,
  Progress,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FaRobot, FaUser, FaSync, FaTrashAlt, FaPlusCircle, FaFileAlt, FaCheckCircle, FaExclamationTriangle } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { sendChatMessage } from '../api/chat';
import { getOpenAIApiKey, saveOpenAIApiKey, getAllApiKeys, getProviderApiKey, saveProviderApiKey, ApiProvider, deleteProviderApiKey, saveDefaultModel, getDefaultModel } from '../api/user';
import { uploadCustomKnowledgeFiles, getCustomKnowledgeHistory } from '../api/customKnowledge';
import { ProcessedFile } from '../models/processedFile';
import axios from 'axios';

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
  { id: 'gpt-4.1-mini', name: 'GPT-4.1 Mini', provider: 'openai', requiresKey: true },
  { id: 'gpt-4.1-nano', name: 'GPT-4.1 Nano', provider: 'openai', requiresKey: true },
  { id: 'claude-3-opus', name: 'Claude 3 Opus', provider: 'anthropic', requiresKey: true },
  { id: 'claude-3-sonnet', name: 'Claude 3 Sonnet', provider: 'anthropic', requiresKey: true },
  { id: 'claude-3-haiku', name: 'Claude 3 Haiku', provider: 'anthropic', requiresKey: true },
  { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'google', requiresKey: true },
  { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', provider: 'google', requiresKey: true },
];

const ALLOWED_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx", "pptx", "ppt", "csv", "txt"];
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB

// --- Helper functions for consistency with S3Browser ---
const formatFileSize = (bytes?: number): string => {
  if (!bytes && bytes !== 0) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
};
const formatDateTime = (dateTimeString?: string): string => {
  if (!dateTimeString) return '-';
  try {
    return new Date(dateTimeString).toLocaleString();
  } catch {
    return dateTimeString;
  }
};

// Skeleton component similar to S3Browser
const ItemTableSkeleton = ({ headers }: { headers: string[] }) => (
  <TableContainer>
    <Table variant="simple" size="sm">
      <Thead>
        <Tr>
          {headers.map((header, index) => (
            <Th key={index}><Skeleton height="20px" /></Th>
          ))}
        </Tr>
      </Thead>
      <Tbody>
        {[...Array(3)].map((_, index) => (
          <Tr key={index}>
            {headers.map((_, tdIndex) => (
              <Td key={tdIndex}><Skeleton height="20px" width={tdIndex === 0 ? "80%" : "60%"} /></Td>
            ))}
          </Tr>
        ))}
      </Tbody>
    </Table>
  </TableContainer>
);

// --- Define chat message type ---
type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

// --- Props for ChatMessageItem ---
interface ChatMessageItemProps {
  msg: ChatMessage;
  components: any; // Type for ReactMarkdown components object
  // Add color props needed inside the item
  userBg: string;
  assistantBg: string;
  textColor: string;
}

// --- Memoized Chat Message Item Component ---
const ChatMessageItem = memo<ChatMessageItemProps>(({ 
  msg, 
  components, 
  userBg, 
  assistantBg, 
  textColor 
}) => {
  console.log(`Rendering message: ${msg.content.substring(0, 20)}...`); // Add console log for debugging renders
  return (
    <Flex
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
          <Box flex="1">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]} 
              components={components}
            >
              {msg.content}
            </ReactMarkdown>
          </Box>
        </HStack>
      </Box>
    </Flex>
  );
});
// Add display name for better debugging
ChatMessageItem.displayName = 'ChatMessageItem';

const JarvisPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  
  // Consistent Color Values
  const bgColor = useColorModeValue('gray.50', 'gray.800');
  const boxBgColor = useColorModeValue('white', 'gray.700');
  const tableHoverBg = useColorModeValue('gray.100', 'gray.600');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const userBg = useColorModeValue('blue.50', 'blue.900');
  const assistantBg = useColorModeValue('gray.100', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'whiteAlpha.900');
  const headingColor = useColorModeValue('gray.700', 'white');
  const inputBg = useColorModeValue('white', 'gray.650');
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');

  // State for model selection and API keys
  const [selectedModel, setSelectedModel] = useState<string>(''); // Initialize as empty, loaded from default
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
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
  const [customFiles, setCustomFiles] = useState<File[]>([]);
  const [customUploadLoading, setCustomUploadLoading] = useState(false);
  const [customUploadError, setCustomUploadError] = useState<string | null>(null);
  const [customUploadProgress, setCustomUploadProgress] = useState<number>(0);
  const [customUploadResults, setCustomUploadResults] = useState<{success: boolean, filename: string, error?: string}[]>([]);
  const [customHistory, setCustomHistory] = useState<ProcessedFile[]>([]);
  const [customHistoryLoading, setCustomHistoryLoading] = useState(false);
  const [customHistoryError, setCustomHistoryError] = useState<string | null>(null);
  const [snippetContent, setSnippetContent] = useState<string>('');
  const [snippetLoading, setSnippetLoading] = useState<boolean>(false);
  const [snippetTag, setSnippetTag] = useState<string>('');

  // Ref for the chat container
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Reference for the refresh interval
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

  // Load saved default model from backend
  useEffect(() => {
    const loadDefaultModel = async () => {
      setModelLoading(true);
      try {
        // Always fetch the default model from the backend
        const model = await getDefaultModel();
        if (model && AVAILABLE_MODELS.some(m => m.id === model)) {
          setSelectedModel(model);
          console.log("Loaded default model from API:", model);
        } else {
          // Fallback to first available model if invalid
          const firstModel = AVAILABLE_MODELS[0]?.id || 'gpt-3.5-turbo';
          setSelectedModel(firstModel);
          console.log("Setting default model to first available:", firstModel);
        }
      } catch (error) {
        console.error("Error loading default model:", error);
        const firstModel = AVAILABLE_MODELS[0]?.id || 'gpt-3.5-turbo';
        setSelectedModel(firstModel);
        console.log("Setting default model to first available on error:", firstModel);
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

  const handleCustomFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const validFiles: File[] = [];
    let error = '';
    files.forEach(file => {
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext || '')) {
        error = `${file.name}: invalid file type.`;
      } else if (file.size > MAX_FILE_SIZE) {
        error = `${file.name}: exceeds 20MB limit.`;
      } else {
        validFiles.push(file);
      }
    });
    setCustomUploadError(error || null);
    setCustomFiles(prev => [...prev, ...validFiles]);
  };

  const handleRemoveCustomFile = (idx: number) => {
    setCustomFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const handleProcessCustomFiles = async () => {
    if (customFiles.length === 0) return;
    setCustomUploadLoading(true);
    setCustomUploadError(null);
    setCustomUploadProgress(0);
    setCustomUploadResults([]);
    let results: {success: boolean, filename: string, error?: string}[] = [];
    for (let i = 0; i < customFiles.length; i++) {
      const file = customFiles[i];
      try {
        await uploadCustomKnowledgeFiles([file]);
        results.push({ success: true, filename: file.name });
      } catch (e: any) {
        let friendlyError = e.message;
        if (
          e.response &&
          e.response.status === 400 &&
          typeof e.response.data === 'object' &&
          e.response.data.detail === 'File with this name has already been processed.'
        ) {
          friendlyError = t(
            'customKnowledge.duplicateFile',
            `This file has already been processed. Please rename the file if you want to upload it again.`
          );
        }
        results.push({ success: false, filename: file.name, error: friendlyError || 'Upload failed' });
      }
      setCustomUploadProgress(Math.round(((i + 1) / customFiles.length) * 100));
      setCustomUploadResults([...results]);
    }
    setCustomFiles([]);
    setCustomUploadLoading(false);
    const failed = results.filter(r => !r.success);
    if (failed.length === 0) {
      toast({ title: t('customKnowledge.uploadSuccess', 'Files uploaded successfully'), status: 'success' });
    } else {
      toast({ title: t('customKnowledge.uploadFailed', 'Some files failed'), description: failed.map(f => `${f.filename}: ${f.error}`).join('\n'), status: 'error', duration: 8000 });
    }
    fetchCustomHistory();
  };

  const fetchCustomHistory = async () => {
    setCustomHistoryLoading(true);
    setCustomHistoryError(null);
    try {
      const data = await getCustomKnowledgeHistory();
      setCustomHistory(data);
    } catch (e: any) {
      if (axios.isAxiosError(e) && e.response?.status === 501) {
        setCustomHistoryError('History feature is temporarily unavailable.');
      } else {
        setCustomHistoryError(e.message || 'Failed to load history');
      }
    } finally {
      setCustomHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 3) {
      fetchCustomHistory();
    }
  }, [activeTab]);

  // Handler to ingest freeform snippet into user's knowledge base
  const handleIngestSnippet = async () => {
    if (!snippetContent.trim() || snippetLoading) return;
    setSnippetLoading(true);
    try {
      const body = { content: snippetContent, metadata: snippetTag ? { tag: snippetTag } : {} };
      const response = await axios.post('/api/v1/knowledge/snippet', body);
      toast({
        title: t('jarvis.addKnowledgeSuccess', 'Knowledge added'),
        description: t('jarvis.addKnowledgeDesc', 'Your text has been added to your knowledge base.'),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      setSnippetContent('');
      setSnippetTag('');
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to add knowledge';
      toast({
        title: t('common.error'),
        description: msg,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setSnippetLoading(false);
    }
  };

  // --- Memoized Markdown Components ---
  const markdownComponents = useMemo(() => ({
    table: (props: any) => (
      <TableContainer whiteSpace="normal" my={4}>
        <Table 
          variant="striped"
          size="sm"
          {...props} 
        />
      </TableContainer>
    ),
    thead: (props: any) => <Thead {...props} />,
    tbody: (props: any) => <Tbody {...props} />,
    tr: (props: any) => <Tr {...props} />,
    th: (props: any) => <Th {...props} />,
    td: (props: any) => <Td {...props} />,
  }), [borderColor]);

  return (
    <Container maxW="container.xl" py={5} bg={bgColor}>
      <VStack spacing={5} align="stretch">
        <Heading as="h1" size="lg" color={headingColor}>{t('jarvis.title')}</Heading>

        {apiKeyError && (
          <Alert status="warning" borderRadius="md">
            <AlertIcon />
            {apiKeyError} - {t('jarvis.continueWithoutKeys', 'You can continue without saved API keys.')}
          </Alert>
        )}

        <Tabs
          variant="soft-rounded"
          colorScheme="blue"
          index={activeTab}
          onChange={setActiveTab}
          isLazy
        >
          <TabList mb="1em">
            <Tab>{t('jarvis.chat')}</Tab>
            <Tab>{t('customKnowledge.uploadTab', 'Customer knowledge')}</Tab>
            <Tab>{t('jarvis.addKnowledge', 'Add Knowledge')}</Tab>
            <Tab>{t('customKnowledge.historyTab', 'History')}</Tab>
            <Tab>{t('jarvis.settings')}</Tab>
          </TabList>
          <TabPanels>
            <TabPanel p={0}>
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
                  bg={boxBgColor}
                  shadow="sm"
                >
                  {chatHistory.map((msg, idx) => (
                    <ChatMessageItem 
                      key={idx} 
                      msg={msg} 
                      components={markdownComponents} 
                      userBg={userBg}
                      assistantBg={assistantBg}
                      textColor={textColor}
                    />
                  ))}
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
                    bg={inputBg}
                    borderColor={borderColor}
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

            <TabPanel p={0}>
              <VStack spacing={4} align="stretch">
                <Box borderWidth={1} borderRadius="lg" p={4} boxShadow="sm" bg={boxBgColor}>
                  <Heading size="md" mb={4} color={headingColor}>
                    {t('customKnowledge.uploadTitle', 'Upload Custom Knowledge Files')}
                  </Heading>
                  <FormControl mb={4}>
                    <FormLabel htmlFor="custom-knowledge-upload" srOnly>
                      {t('customKnowledge.selectFiles', 'Select Files')}
                    </FormLabel>
                    <Input
                      id="custom-knowledge-upload"
                      type="file"
                      multiple
                      accept={ALLOWED_EXTENSIONS.map(ext => '.' + ext).join(',')}
                      onChange={handleCustomFileSelect}
                      disabled={customUploadLoading}
                      p={1.5}
                      bg={inputBg}
                      borderColor={borderColor}
                      sx={{
                          '::file-selector-button': {
                            border: 'none',
                            outline: 'none',
                            mr: 2,
                            bg: useColorModeValue('gray.100', 'gray.600'),
                            px: 3,
                            py: 1.5,
                            borderRadius: 'md',
                            fontSize: 'sm',
                            cursor: 'pointer',
                            _hover: { bg: useColorModeValue('gray.200', 'gray.500') }
                          },
                      }}
                    />
                     <FormHelperText mt={2}>
                       {t('customKnowledge.uploadHelp', `Allowed types: ${ALLOWED_EXTENSIONS.join(', ')}. Max size: ${formatFileSize(MAX_FILE_SIZE)} per file.`)}
                     </FormHelperText>
                  </FormControl>
                  {customUploadError && (
                    <Alert status="error" mt={2} borderRadius="md">
                      <AlertIcon />
                      {customUploadError}
                    </Alert>
                  )}
                  
                  <Heading size="sm" mt={6} mb={2} color={headingColor}>
                    {t('customKnowledge.filesToUpload', 'Files Ready for Upload')} ({customFiles.length})
                  </Heading>
                   <TableContainer borderWidth="1px" borderColor={borderColor} borderRadius="md">
                     <Table variant="simple" size="sm">
                       <Thead>
                         <Tr>
                           <Th width="60%">{t('customKnowledge.filename', 'Filename')}</Th>
                           <Th isNumeric width="25%">{t('customKnowledge.size', 'Size')}</Th>
                           <Th textAlign="center" width="15%">{t('common.actions', 'Actions')}</Th>
                         </Tr>
                       </Thead>
                       <Tbody>
                         {customFiles.length === 0 && (
                           <Tr>
                             <Td colSpan={3}>
                               <Center p={3}>
                                 <Text color="gray.500">{t('customKnowledge.noFilesSelected', 'No files selected yet.')}</Text>
                               </Center>
                             </Td>
                           </Tr>
                         )}
                         {customFiles.map((file, idx) => (
                           <Tr key={idx} _hover={{ bg: tableHoverBg }}>
                             <Td width="60%">
                                <HStack spacing={2}>
                                    <Icon as={FaFileAlt} color={fileColor} />
                                    <Text noOfLines={1} title={file.name}>{file.name}</Text>
                                </HStack>
                             </Td>
                             <Td isNumeric width="25%">{formatFileSize(file.size)}</Td>
                             <Td textAlign="center" width="15%">
                               <IconButton
                                 aria-label={t('common.remove', 'Remove')}
                                 icon={<FaTrashAlt />}
                                 size="xs"
                                 colorScheme="red"
                                 variant="ghost"
                                 onClick={() => handleRemoveCustomFile(idx)}
                                 isDisabled={customUploadLoading}
                                 title={t('common.remove', 'Remove')}
                               />
                             </Td>
                           </Tr>
                         ))}
                       </Tbody>
                     </Table>
                   </TableContainer>
                   
                   <Flex justify="flex-end" mt={4}>
                     <Button
                       colorScheme="blue"
                       leftIcon={<FaPlusCircle />}
                       onClick={handleProcessCustomFiles}
                       isLoading={customUploadLoading}
                       disabled={customFiles.length === 0 || customUploadLoading}
                     >
                       {t('customKnowledge.process', 'Process Selected Files')} ({customFiles.length})
                     </Button>
                   </Flex>
                </Box>
              </VStack>
            </TabPanel>

            <TabPanel p={4}>
              <VStack spacing={4} align="stretch">
                <Heading size="md" color={headingColor}>
                  {t('jarvis.addKnowledge', 'Add Knowledge')}
                </Heading>
                <FormControl>
                  <FormLabel htmlFor="snippet-tag">{t('jarvis.snippetTagLabel', 'Tag (optional)')}</FormLabel>
                  <Input
                    id="snippet-tag"
                    value={snippetTag}
                    onChange={(e) => setSnippetTag(e.target.value)}
                    placeholder={t('jarvis.snippetTagPlaceholder', 'e.g., GIC rate card')}
                    bg={inputBg}
                    borderColor={borderColor}
                    isDisabled={snippetLoading}
                  />
                  <FormHelperText color={useColorModeValue('gray.600','gray.400')}>
                    {t('jarvis.snippetTagHelper', 'Optional: Assign a lowercase tag so you can retrieve this snippet using `tag:<your_tag>` in your query.')}
                  </FormHelperText>
                </FormControl>
                <Textarea
                  value={snippetContent}
                  onChange={(e) => setSnippetContent(e.target.value)}
                  placeholder={t('jarvis.snippetPlaceholder', 'Enter text to add to knowledge base...')}
                  rows={6}
                  resize="vertical"
                  isDisabled={snippetLoading}
                  bg={inputBg}
                  borderColor={borderColor}
                />
                <Button
                  colorScheme="blue"
                  onClick={handleIngestSnippet}
                  isLoading={snippetLoading}
                  isDisabled={!snippetContent.trim() || snippetLoading}
                  alignSelf="flex-end"
                >
                  {t('jarvis.submitSnippet', 'Submit')}
                </Button>
              </VStack>
            </TabPanel>

            <TabPanel p={0}>
              <VStack spacing={4} align="stretch">
                <Box borderWidth={1} borderRadius="lg" p={4} boxShadow="sm" bg={boxBgColor}>
                  <Heading size="md" mb={4} color={headingColor}>
                    {t('customKnowledge.historyTitle', 'Upload History')}
                  </Heading>
                  {customHistoryError && (
                     <Alert status="error" borderRadius="md" mb={4}>
                       <AlertIcon />
                       {customHistoryError}
                       <Button ml={4} size="sm" onClick={fetchCustomHistory} isLoading={customHistoryLoading}>
                          {t('common.retry', 'Retry')}
                       </Button>
                     </Alert>
                  )}
                  {customHistoryLoading ? (
                     <Center p={4}><Spinner /></Center>
                  ) : (
                     <TableContainer borderWidth="1px" borderColor={borderColor} borderRadius="md">
                       <Table variant='simple' size="sm">
                         <Thead>
                           <Tr>
                             <Th width="40%">{t('customKnowledge.filename', 'Filename')}</Th>
                             <Th isNumeric width="20%">{t('customKnowledge.size', 'Size')}</Th>
                             <Th width="20%">{t('customKnowledge.status', 'Status')}</Th>
                             <Th width="20%">{t('customKnowledge.uploadedAt', 'Uploaded At')}</Th>
                           </Tr>
                         </Thead>
                         <Tbody>
                          {customHistory.length === 0 && !customHistoryError && (
                            <Tr>
                              <Td colSpan={4}>
                                <Center p={3}>
                                   <Text color="gray.500">{t('customKnowledge.noHistory', 'No upload history found.')}</Text>
                                </Center>
                              </Td>
                            </Tr>
                          )}
                           {customHistory.map(item => {
                             const isProcessing = item.status === 'processing' || item.status === 'pending_analysis';
                             const displayStatusKey = `processedFile.status.${item.status}`;
                             const displayStatusText = t(displayStatusKey, item.status);
                             
                             return (
                             <Tr key={item.id} _hover={{ bg: tableHoverBg }}>
                               <Td width="40%">
                                 <HStack spacing={2}>
                                      <Icon as={FaFileAlt} color={fileColor} boxSize="1.2em" />
                                      <Text noOfLines={1} title={item.original_filename}>{item.original_filename}</Text>
                                 </HStack>
                               </Td>
                               <Td isNumeric width="20%">{formatFileSize(item.size_bytes ?? undefined)}</Td>
                               <Td width="20%">
                                  <Tag 
                                      size="sm" 
                                      variant="subtle" 
                                      colorScheme={
                                           item.status === 'analysis_complete' || item.status === 'completed' ? 'green'
                                         : item.status.includes('failed') ? 'red' 
                                         : 'yellow'
                                      }
                                  >
                                     <Icon 
                                       as={
                                         item.status === 'analysis_complete' || item.status === 'completed' ? FaCheckCircle : 
                                         item.status.includes('failed') ? FaExclamationTriangle : 
                                         FaSync
                                       } 
                                       mr={1} 
                                     />
                                     {displayStatusText}
                                  </Tag>
                               </Td>
                               <Td width="20%">{formatDateTime(item.uploaded_at)}</Td>
                             </Tr>
                             );
                          })}
                         </Tbody>
                       </Table>
                     </TableContainer>
                  )}
                </Box>
              </VStack>
            </TabPanel>

            <TabPanel p={4}>
              <VStack spacing={4} align="stretch">
                <Heading size="md" color={headingColor}>
                  {t('jarvis.settingsTitle', 'API Settings')}
                </Heading>
                {apiKeyLoading ? (
                   <Center py={10}><Spinner size="xl" /></Center>
                ) : (
                   <Stack spacing={6}>
                      <Box borderWidth="1px" borderRadius="lg" p={4} bg={boxBgColor} shadow="sm">
                        <Heading size="sm" mb={3} color={headingColor}>
                           {t('jarvis.settingsContent.modelSelection', 'Model Selection')}
                        </Heading>
                        <Text fontSize="sm" mb={4} color={useColorModeValue('gray.600', 'gray.400')}>
                           {t('jarvis.settingsContent.modelDescription', 'Select the AI model to use for chat. Models requiring an API key are only selectable if the corresponding key is saved below.')}
                        </Text>
                        
                        <FormControl>
                           <FormLabel htmlFor="modelSelect" srOnly>
                             {t('jarvis.settingsContent.model', 'Model')}
                           </FormLabel>
                           <HStack>
                             {modelLoading ? (
                               <Skeleton height="40px" flex="1" />
                             ) : (
                               <Select
                                 id="modelSelect"
                                 value={selectedModel}
                                 onChange={handleModelChange}
                                 flex="1"
                                 bg={inputBg}
                                 borderColor={borderColor}
                               >
                                 {AVAILABLE_MODELS.map((model) => {
                                   const hasRequiredKey = !model.requiresKey || !!apiKeys[model.provider];
                                   return (
                                     <option
                                       key={model.id}
                                       value={model.id}
                                       disabled={!hasRequiredKey}
                                     >
                                       {model.name} {!hasRequiredKey ? ` (${t('jarvis.requiresKey', 'Requires API Key')})` : ''}
                                     </option>
                                   );
                                 })}
                               </Select>
                             )}
                             <Button
                               colorScheme="blue"
                               onClick={setModelAsDefault}
                               isLoading={savingDefaultModel}
                               isDisabled={modelLoading || !selectedModel}
                             >
                               {t('jarvis.setAsDefault', 'Set as Default')}
                             </Button>
                           </HStack>
                           <FormHelperText mt={2}>
                             {t('jarvis.settingsContent.modelDefaultHelp', 'The selected model will be used for new chat sessions. You can change it anytime.')}
                           </FormHelperText>
                        </FormControl>
                      </Box>
                      
                      <Text color={useColorModeValue('gray.600', 'gray.400')} pt={2}>
                        {t('jarvis.apiKeyDescription', 'To use certain models, provide API keys from the respective providers:')}
                      </Text>
                      
                      <VStack spacing={4} align="stretch">
                         {(['openai', 'anthropic', 'google'] as ApiProvider[]).map(provider => {
                           const hasModels = AVAILABLE_MODELS.some(model => model.provider === provider && model.requiresKey);
                           if (!hasModels) return null;
                           
                           return (
                             <Box key={provider} borderWidth="1px" borderRadius="lg" p={4} bg={boxBgColor} shadow="sm">
                               <Heading size="sm" mb={3} color={headingColor}>{provider.toUpperCase()} {t('jarvis.settingsContent.apiKeyTitle')}</Heading>
                               <Text fontSize="sm" mb={4} color={useColorModeValue('gray.600', 'gray.400')}>
                                 {t(`jarvis.settingsContent.${provider}ApiKeyDescription`,
                                    `Enter your ${provider.toUpperCase()} API key to enable ${provider.toUpperCase()}-powered models.`)}
                               </Text>
                               
                                <Stack direction={{ base: 'column', sm: 'row' }} spacing={3} align="center">
                                  <FormControl flex={1}>
                                    <FormLabel htmlFor={`${provider}-apiKey`} srOnly>
                                      {t('jarvis.settingsContent.apiKey', { provider: provider.toUpperCase() })}
                                    </FormLabel>
                                    <InputGroup size="md">
                                      <Input
                                        id={`${provider}-apiKey`}
                                        type="password"
                                        value={apiKeys[provider] || ''}
                                        onChange={(e) => handleApiKeyUpdate(provider, e.target.value)}
                                        placeholder={t('jarvis.settingsContent.apiKeyPlaceholder')}
                                        bg={inputBg}
                                        borderColor={borderColor}
                                        pr="6rem"
                                      />
                                      <InputRightElement width="auto" pr={1}>
                                         <HStack spacing={1}> 
                                             {apiKeys[provider] && (
                                                <IconButton
                                                  aria-label={t('jarvis.delete', 'Delete Key')}
                                                  icon={<FaTrashAlt />}
                                                  size="sm"
                                                  variant="ghost"
                                                  colorScheme="red"
                                                  onClick={() => handleDeleteApiKey(provider)}
                                                  title={t('jarvis.deleteApiKeyTooltip', 'Delete Saved Key')}
                                                />
                                             )}
                                             <Button h="1.75rem" size="sm"
                                              onClick={() => handleSaveApiKey(provider)}
                                              isDisabled={!apiKeys[provider] || apiKeys[provider].length < 5}
                                              colorScheme={apiKeys[provider] ? 'green' : 'blue'}
                                              title={t('jarvis.saveApiKeyTooltip', 'Save This Key')}
                                            >
                                              {t('common.save', 'Save')}
                                            </Button>
                                          </HStack>
                                      </InputRightElement>
                                    </InputGroup>
                                  </FormControl>
                                </Stack>
                                
                                {apiKeys[provider] && (
                                   <HStack mt={2}>
                                     <Icon as={FaCheckCircle} color="green.500" />
                                     <Text fontSize="xs" color="green.500">
                                      {t('jarvis.apiKeySet', 'API key is set')}
                                     </Text>
                                   </HStack>
                                )}
                                 <FormControl> 
                                   <FormHelperText mt={2}>
                                     {t(`jarvis.settingsContent.${provider}ApiKeyHelp`, `Needed for models like ${AVAILABLE_MODELS.filter(m => m.provider === provider).map(m => m.name).join(', ')}.`)}
                                   </FormHelperText>
                                 </FormControl>
                               </Box>
                             );
                           })}
                        </VStack>
                        {apiKeyError && (
                          <Alert status="error" borderRadius="md">
                            <AlertIcon />
                            {apiKeyError}
                          </Alert>
                        )}
                   </Stack>
                )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Container>
  );
};

export default JarvisPage; 