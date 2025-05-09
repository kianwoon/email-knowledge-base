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
  UnorderedList,
  OrderedList,
  ListItem,
  Code,
  Link,
  Divider,
  Image,
  FormErrorMessage,
  Switch,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FaRobot, FaUser, FaSync, FaTrashAlt, FaPlusCircle, FaFileAlt, FaCheckCircle, FaExclamationTriangle, FaKey, FaTrash, FaCommentDots, FaUpload, FaEdit, FaHistory, FaCog, FaTools, FaToggleOn, FaToggleOff } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { sendChatMessage } from '../api/chat';
import { getOpenAIApiKey, saveOpenAIApiKey, getAllApiKeys, getProviderApiKey, saveProviderApiKey, ApiProvider, deleteProviderApiKey, saveDefaultModel, getDefaultModel } from '../api/user';
import { uploadCustomKnowledgeFiles, getCustomKnowledgeHistory } from '../api/customKnowledge';
import { ProcessedFile } from '../models/processedFile';
import axios from 'axios';
import { keyframes } from '@emotion/react';
import { listExternalTokens, addExternalToken, deleteExternalToken, JarvisTokenDisplay, JarvisTokenCreate } from '../api/jarvis';
import { CheckIcon, CloseIcon, ViewIcon, ChevronLeftIcon, ChevronRightIcon, InfoIcon } from '@chakra-ui/icons';
import JSONSchemaEditor from '../components/JSONSchemaEditor';
import { MCPTool, MCPToolCreate, listMCPTools, createMCPTool, updateMCPTool, deleteMCPTool, toggleMCPToolStatus } from '../api/mcpTools';
import MCPToolsHelp from '../components/MCPToolsHelp';

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
  { id: 'deepseek-chat', name: 'DeepSeek Chat', provider: 'deepseek', requiresKey: true },
  { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner', provider: 'deepseek', requiresKey: true },
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
}

// --- Memoized Chat Message Item Component ---
const ChatMessageItem = memo<ChatMessageItemProps>(({ msg, components }) => {
  // Use Chakra's theming system for consistent light/dark mode
  const userBubbleBg = useColorModeValue('blue.50', 'blue.900');
  const assistantBubbleBg = useColorModeValue('gray.50', 'gray.700');
  const bubbleBorderColor = useColorModeValue('gray.200', 'gray.600');
  const userBubbleBorderColor = useColorModeValue('blue.200', 'blue.700');
  const timestampColor = useColorModeValue('gray.500', 'gray.400');
  const messageTextColor = useColorModeValue('gray.800', 'gray.100');

  return (
    <Flex w="full" justify={msg.role === 'user' ? 'flex-end' : 'flex-start'} mb={3}>
      <Box
        maxW="80%"
        bg={msg.role === 'user' ? userBubbleBg : assistantBubbleBg}
        color={messageTextColor}
        px={4}
        py={3}
        borderRadius="xl"
        boxShadow="sm"
        borderWidth="1px"
        borderColor={msg.role === 'user' ? userBubbleBorderColor : bubbleBorderColor}
        overflowWrap="break-word"
        whiteSpace="pre-wrap"
        sx={{
          '& p': {
            wordBreak: 'normal',
            overflowWrap: 'break-word',
          },
        }}
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
            <Text fontSize="xs" color={timestampColor} mt={1} textAlign="right">
              {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </Text>
          </Box>
        </HStack>
      </Box>
    </Flex>
  );
});
ChatMessageItem.displayName = 'ChatMessageItem';

// Add these animations when defining the JarvisPage component (after all other consts)
const bounce = keyframes`
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
`;

const typingAnimation = {
  '&:nth-of-type(1)': { animation: `${bounce} 1s infinite ease-in-out 0s` },
  '&:nth-of-type(2)': { animation: `${bounce} 1s infinite ease-in-out 0.2s` },
  '&:nth-of-type(3)': { animation: `${bounce} 1s infinite ease-in-out 0.4s` }
};

const JarvisPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  
  // Consistent Color Values
  const bgColor = useColorModeValue('gray.50', 'gray.800');
  const boxBgColor = useColorModeValue('white', 'gray.700');
  const tableHoverBg = useColorModeValue('gray.100', 'gray.600');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'whiteAlpha.900');
  const headingColor = useColorModeValue('gray.700', 'white');
  const inputBg = useColorModeValue('white', 'gray.650');
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');

  // State for model selection and API keys
  const [selectedModel, setSelectedModel] = useState<string>(''); // Initialize as empty, loaded from default
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [apiBaseUrls, setApiBaseUrls] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [apiKeyLoading, setApiKeyLoading] = useState(false);
  const [savedKeysStatus, setSavedKeysStatus] = useState<Record<string, boolean>>({});
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

  // --- ADDED: State for External Knowledge Tokens ---
  const [externalTokens, setExternalTokens] = useState<JarvisTokenDisplay[]>([]);
  const [isLoadingExternalTokens, setIsLoadingExternalTokens] = useState(true);
  const [newTokenNickname, setNewTokenNickname] = useState('');
  const [newTokenValue, setNewTokenValue] = useState('');
  const [newTokenEndpointUrl, setNewTokenEndpointUrl] = useState('');
  const [isAddingToken, setIsAddingToken] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);
  // --- END ADDED STATE ---

  // Add these new state variables inside the JarvisPage component alongside other state variables
  const [mcpTools, setMcpTools] = useState<MCPTool[]>([]);
  const [isLoadingMcpTools, setIsLoadingMcpTools] = useState(false);
  const [mcpToolsError, setMcpToolsError] = useState<string | null>(null);
  const [isAddingMcpTool, setIsAddingMcpTool] = useState(false);
  const [isEditingMcpTool, setIsEditingMcpTool] = useState(false);
  const [currentMcpTool, setCurrentMcpTool] = useState<MCPTool | null>(null);
  const [newMcpToolData, setNewMcpToolData] = useState<MCPToolCreate>({
    name: '',
    description: '',
    parameters: {},
    entrypoint: '',
    version: '1.0',
    enabled: true
  });

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
          // Initialize savedKeysStatus from parsed keys
          const initialStatus: Record<string, boolean> = {};
          Object.keys(parsed).forEach(provider => {
            initialStatus[provider] = Boolean(parsed[provider]);
          });
          setSavedKeysStatus(initialStatus);
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
    if (activeTab === 4) { // Settings tab index
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
    }
    setApiKeyError(null);
    try {
      const keysData = await getAllApiKeys(); // Fetches all keys including metadata
      
      const fetchedKeys: Record<string, string> = {};
      const fetchedStatus: Record<string, boolean> = {};
      const fetchedBaseUrls: Record<string, string> = {}; // Initialize base URLs record

      let anyKeySet = false;
      keysData.forEach(keyInfo => {
        if (keyInfo.provider && keyInfo.is_active) {
          fetchedStatus[keyInfo.provider] = true; // Mark provider as having a saved key
          anyKeySet = true;
          // --- ADDED: Store the base URL if it exists --- 
          if (keyInfo.model_base_url) {
            fetchedBaseUrls[keyInfo.provider] = keyInfo.model_base_url;
          }
          // --- END ADDED ---
          
          // Note: We don't store the actual key value in state for security display
          // We rely on the checkmark (fetchedStatus) and the masked input
          // fetchedKeys[keyInfo.provider] = '********'; // Placeholder if needed, but status is better
        }
      });
      
      setApiKeys({}); // Clear actual keys from state, rely on status
      setSavedKeysStatus(fetchedStatus);
      setApiBaseUrls(fetchedBaseUrls); // Set the fetched base URLs
      setHasApiKey(anyKeySet); // Update based on if any active key was found
      setLastLoadTime(Date.now()); // Record successful load time
      setRetryCount(0); // Reset retry count on success

    } catch (error) {
      console.error("Error loading API keys:", error);
      setApiKeyError("Failed to load API keys.");
      setSavedKeysStatus({}); // Reset status on error
    } finally {
      if (!isBackgroundRefresh) {
        setApiKeyLoading(false);
      }
    }
  };

  // Handle API key and Base URL updates
  const handleApiKeyUpdate = (provider: string, key: string, baseUrl?: string) => {
    setApiKeys(prev => ({
      ...prev,
      [provider]: key
    }));
    // Also update base URL state if provided (e.g., from its own input)
    if (baseUrl !== undefined) {
      setApiBaseUrls(prev => ({
        ...prev,
        [provider]: baseUrl
      }));
    }
  };
  
  // --- ADDED: Handler specifically for Base URL input changes --- 
  const handleBaseUrlUpdate = (provider: string, baseUrl: string) => {
      setApiBaseUrls(prev => ({
        ...prev,
        [provider]: baseUrl
      }));
  };
  // --- END ---

  // Save API keys and Base URL
  const handleSaveApiKey = async (provider: string) => {
    console.log(`[Save Button Clicked] Provider: ${provider}`); // Log 1: Function entry
    try {
      const apiKeyToSave = apiKeys[provider];
      const baseUrlToSave = apiBaseUrls[provider]; // Get base URL from state
      console.log(`[Save Handler] API Key Input: '${apiKeyToSave}' (Length: ${apiKeyToSave?.length || 0})`); // Log 2: Key Input Value
      console.log(`[Save Handler] Base URL Input: '${baseUrlToSave}'`); // Log 3: Base URL Input Value
      console.log(`[Save Handler] Is Key Saved Status: ${savedKeysStatus[provider]}`); // Log 4: Saved Status

      // RE-ADDED: Prevent saving if the API key input is empty, as the backend requires it.
      if (!apiKeyToSave) {
        console.warn(`[Save Handler] Aborting save for ${provider}: API key input field is empty.`); // Log 5: Abort Reason
        toast({
          title: "Save Not Attempted",
          description: "Please re-enter the API key to save changes.",
          status: "warning",
          duration: 4000,
          isClosable: true,
        });
        return;
      }

      console.log(`[Save Handler] Proceeding to call saveProviderApiKey for ${provider}...`); // Log 6: Proceeding

      // Use the updated API function
      await saveProviderApiKey(provider as ApiProvider, apiKeyToSave, baseUrlToSave);
      console.log(`[Save Handler] saveProviderApiKey call successful for ${provider}.`); // Log 7: API Success
      
      // Update sessionStorage after successful save to DB
      sessionStorage.setItem('jarvis_api_keys', JSON.stringify(apiKeys));
      
      toast({
        title: t('jarvis.apiKeySaved'),
        description: t('jarvis.apiKeySavedDesc', { provider: provider.toUpperCase() }),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      
      setHasApiKey(true);
      localStorage.setItem('jarvis_had_api_key', 'true');
      // No longer clear the input fields after successful save
      // setSavedKeysStatus still updates status
      setSavedKeysStatus(prev => ({ ...prev, [provider]: true })); // <-- Update status on save
      setLastKeyRefresh(Date.now()); // Trigger potential refresh elsewhere if needed
    } catch (error: any) {
      console.error(`Error saving ${provider} API key:`, error);
      toast({
        title: t('jarvis.apiKeySaveError'),
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
        title: t('jarvis.apiKeyDeleted'),
        description: t('jarvis.apiKeyDeletedDesc', { provider: provider.toUpperCase() }),
        status: 'info', // Use info for deletion confirmation
        duration: 3000,
        isClosable: true,
      });
      
      // Check if we still have any keys
      setTimeout(() => {
        loadApiKeys(false);
      }, 500);
      // Clear the input fields after successful delete
      handleApiKeyUpdate(provider, '', '');
      handleBaseUrlUpdate(provider, '');
      setSavedKeysStatus(prev => ({ ...prev, [provider]: false })); // <-- Update status on delete
      setLastKeyRefresh(Date.now()); // Trigger potential refresh elsewhere if needed
    } catch (error: any) {
      console.error(`Error deleting ${provider} API key:`, error);
      toast({
        title: t('jarvis.apiKeyDeleteError'),
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
        title: t('jarvis.defaultModelSaved'),
        description: t('jarvis.defaultModelSavedDesc'),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error("Error saving default model:", error);
      toast({
        title: t('jarvis.defaultModelError'),
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
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [chatHistory]);

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
      toast({ title: t('customKnowledge.uploadSuccess'), status: 'success' });
    } else {
      toast({ title: t('customKnowledge.uploadFailed'), description: failed.map(f => `${f.filename}: ${f.error}`).join('\n'), status: 'error', duration: 8000 });
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
        title: t('jarvis.addKnowledgeSuccess'),
        description: t('jarvis.addKnowledgeDesc'),
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

  // --- ADDED: Load External Tokens when Tab is Active ---
  useEffect(() => {
    if (activeTab === 5) { // New Knowledge Token tab index (will be 5 after adding it)
      fetchExternalTokens();
    }
  }, [activeTab]);

  const fetchExternalTokens = async () => {
    setIsLoadingExternalTokens(true);
    setTokenError(null);
    try {
      const tokens = await listExternalTokens();
      setExternalTokens(tokens);
    } catch (error: any) {
      console.error("Error fetching external tokens:", error);
      setTokenError(error.response?.data?.detail || error.message || "Failed to load external tokens.");
    } finally {
      setIsLoadingExternalTokens(false);
    }
  };
  // --- END ADDED ---

  // --- ADDED: Handlers for External Knowledge Tokens ---
  const handleAddExternalToken = async () => {
    if (!newTokenNickname.trim() || !newTokenValue.trim() || !newTokenEndpointUrl.trim()) {
      setTokenError("Nickname, Token Value, and Endpoint URL cannot be empty.");
      return;
    }
    setIsAddingToken(true);
    setTokenError(null);
    try {
      const tokenData: JarvisTokenCreate = {
        token_nickname: newTokenNickname,
        raw_token_value: newTokenValue,
        endpoint_url: newTokenEndpointUrl
      };
      await addExternalToken(tokenData);
      toast({ title: "Token Added", description: `Token '${newTokenNickname}' added successfully.`, status: "success" });
      setNewTokenNickname('');
      setNewTokenValue('');
      setNewTokenEndpointUrl('');
      fetchExternalTokens(); // Refresh the list
    } catch (error: any) {
      console.error("Error adding external token:", error);
      const detail = error.response?.data?.detail || error.message || "Failed to add token.";
      setTokenError(detail);
      toast({ title: "Error Adding Token", description: detail, status: "error" });
    } finally {
      setIsAddingToken(false);
    }
  };

  const handleDeleteExternalToken = async (tokenId: number, nickname: string) => {
    // Optional: Add confirmation dialog here
    if (!window.confirm(`Are you sure you want to delete the token "${nickname}"?`)) {
      return;
    }
    // Indicate loading state for the specific token being deleted?
    // For simplicity, we'll just refresh the list after.
    try {
      await deleteExternalToken(tokenId);
      toast({ title: "Token Deleted", description: `Token '${nickname}' deleted successfully.`, status: "info" });
      fetchExternalTokens(); // Refresh the list
    } catch (error: any) {
      console.error(`Error deleting token ${tokenId}:`, error);
      const detail = error.response?.data?.detail || error.message || "Failed to delete token.";
      setTokenError(detail); // Show error related to deletion
      toast({ title: "Error Deleting Token", description: detail, status: "error" });
    }
  };
  // --- END ADDED HANDLERS ---

  // --- Memoized Markdown Components ---
  const markdownComponents = useMemo(() => ({
    // Tables
    table: (props: any) => (
      <TableContainer whiteSpace="normal" my={4}>
        <Table 
          variant="striped"
          size="sm"
          {...props} 
        />
      </TableContainer>
    ),
    thead: (props: any) => <Thead bg={useColorModeValue('gray.100', 'gray.700')} {...props} />,
    tbody: (props: any) => <Tbody {...props} />,
    tr: (props: any) => <Tr {...props} />,
    th: (props: any) => <Th {...props} />,
    td: (props: any) => <Td {...props} />,

    // Headings
    h1: (props: any) => <Heading as="h1" size="xl" my={4} {...props} />,
    h2: (props: any) => <Heading as="h2" size="lg" my={3} {...props} />,
    h3: (props: any) => <Heading as="h3" size="md" my={2} {...props} />,
    h4: (props: any) => <Heading as="h4" size="sm" my={2} {...props} />,
    h5: (props: any) => <Heading as="h5" size="xs" my={1} {...props} />,
    h6: (props: any) => <Heading as="h6" size="xs" my={1} {...props} />,

    // Paragraphs
    p: (props: any) => (
      <Text
        my={3}
        lineHeight="tall"
        overflowWrap="break-word"
        wordBreak="break-all"
        whiteSpace="pre-wrap"
        {...props}
      />
    ),

    // Lists
    ul: (props: any) => <UnorderedList spacing={2} my={3} pl={4} {...props} />,
    ol: (props: any) => <OrderedList spacing={2} my={3} pl={4} {...props} />,
    li: (props: any) => <ListItem {...props} />,

    // Code blocks
    code: (props: any) => {
      const { inline, children, className, ...rest } = props;
      if (inline) {
        return (
          <Code
            bg={useColorModeValue('gray.100', 'gray.700')}
            px={1}
            borderRadius="md"
            {...rest}
          >
            {children}
          </Code>
        );
      }
      return (
        <Box
          bg={useColorModeValue('gray.100', 'gray.700')}
          p={3}
          borderRadius="md"
          my={4}
          overflowX="auto"
          maxW="100%"
        >
          <Code
            display="block"
            whiteSpace="pre-wrap"
            overflowX="auto"
            overflowWrap="break-word"
            wordBreak="break-all"
            {...rest}
          >
            {children}
          </Code>
        </Box>
      );
    },

    // Blockquotes
    blockquote: (props: any) => (
      <Box
        borderLeft="4px solid"
        borderColor={useColorModeValue('blue.200', 'blue.700')}
        pl={4}
        py={1}
        my={2}
        bg={useColorModeValue('blue.50', 'blue.900')}
        {...props}
      />
    ),

    // Links
    a: (props: any) => (
      <Link
        color={useColorModeValue('blue.500', 'blue.300')}
        _hover={{ textDecoration: 'underline' }}
        isExternal
        {...props}
      />
    ),

    // Horizontal rule
    hr: (props: any) => (
      <Divider
        my={4}
        borderColor={useColorModeValue('gray.300', 'gray.600')}
        {...props}
      />
    ),

    // Images
    img: (props: any) => (
      <Image
        borderRadius="md"
        my={2}
        maxW="100%"
        {...props}
      />
    ),
  }), [borderColor]);

  // Add this useEffect to load MCP tools when the tab is activated
  useEffect(() => {
    if (activeTab === 6) { // MCP Tools tab index (7th tab)
      fetchMcpTools();
    }
  }, [activeTab]);

  // Add these functions before the return statement
  const fetchMcpTools = async () => {
    setIsLoadingMcpTools(true);
    setMcpToolsError(null);
    try {
      const tools = await listMCPTools();
      setMcpTools(tools);
    } catch (error: any) {
      console.error("Error fetching MCP tools:", error);
      setMcpToolsError(error.response?.data?.detail || error.message || t('jarvis.toolsFetchFailedDesc', "Failed to load MCP tools."));
    } finally {
      setIsLoadingMcpTools(false);
    }
  };

  const handleAddMcpTool = async () => {
    setIsAddingMcpTool(true);
    setMcpToolsError(null);
    try {
      // Use currentMcpTool instead of newMcpToolData
      await createMCPTool(currentMcpTool as MCPToolCreate);
      toast({ 
        title: t('jarvis.toolAddedTitle', "Tool Added"), 
        description: t('jarvis.toolAddedDesc', "Tool '{{name}}' added successfully.", {name: currentMcpTool?.name}), 
        status: "success" 
      });
      // Reset form
      setCurrentMcpTool(null);
      setIsAddingMcpTool(false);
      fetchMcpTools(); // Refresh the list
    } catch (error: any) {
      console.error("Error adding MCP tool:", error);
      const detail = error.response?.data?.detail || error.message || t('jarvis.toolAddFailedDesc', "Failed to add tool.");
      setMcpToolsError(detail);
      toast({ 
        title: t('jarvis.toolAddFailedTitle', "Error Adding Tool"), 
        description: detail, 
        status: "error" 
      });
      setIsAddingMcpTool(false);
    }
  };

  const handleUpdateMcpTool = async () => {
    if (!currentMcpTool || !currentMcpTool.id) return;
    
    setIsEditingMcpTool(true);
    setMcpToolsError(null);
    try {
      await updateMCPTool(currentMcpTool.id, currentMcpTool);
      toast({ 
        title: t('jarvis.toolUpdatedTitle', "Tool Updated"), 
        description: t('jarvis.toolUpdatedDesc', "Tool '{{name}}' updated successfully.", {name: currentMcpTool.name}), 
        status: "success" 
      });
      setIsEditingMcpTool(false);
      setCurrentMcpTool(null);
      fetchMcpTools(); // Refresh the list
    } catch (error: any) {
      console.error("Error updating MCP tool:", error);
      const detail = error.response?.data?.detail || error.message || t('jarvis.toolUpdateFailedDesc', "Failed to update tool.");
      setMcpToolsError(detail);
      toast({ 
        title: t('jarvis.toolUpdateFailedTitle', "Error Updating Tool"), 
        description: detail, 
        status: "error" 
      });
      setIsEditingMcpTool(false);
    }
  };

  const handleDeleteMcpTool = async (id: number, name: string) => {
    if (!window.confirm(t('jarvis.toolDeleteConfirm', 'Are you sure you want to delete the tool "{{name}}"?', {name}))) {
      return;
    }
    
    try {
      await deleteMCPTool(id);
      toast({ 
        title: t('jarvis.toolDeletedTitle', "Tool Deleted"), 
        description: t('jarvis.toolDeletedDesc', "Tool '{{name}}' deleted successfully.", {name}), 
        status: "info" 
      });
      fetchMcpTools(); // Refresh the list
    } catch (error: any) {
      console.error(`Error deleting tool ${id}:`, error);
      const detail = error.response?.data?.detail || error.message || t('jarvis.toolDeleteFailedDesc', "Failed to delete tool.");
      setMcpToolsError(detail);
      toast({ 
        title: t('jarvis.toolDeleteFailedTitle', "Error Deleting Tool"), 
        description: detail, 
        status: "error" 
      });
    }
  };

  const handleToggleMcpToolStatus = async (id: number, enabled: boolean, name: string) => {
    try {
      await toggleMCPToolStatus(id, !enabled);
      toast({ 
        title: !enabled ? t('jarvis.toolEnabledTitle', "Tool Enabled") : t('jarvis.toolDisabledTitle', "Tool Disabled"), 
        description: !enabled 
          ? t('jarvis.toolEnabledDesc', "Tool '{{name}}' enabled successfully.", {name}) 
          : t('jarvis.toolDisabledDesc', "Tool '{{name}}' disabled successfully.", {name}), 
        status: "success" 
      });
      fetchMcpTools(); // Refresh the list
    } catch (error: any) {
      console.error(`Error toggling tool status ${id}:`, error);
      const detail = error.response?.data?.detail || error.message || t('jarvis.toolStatusUpdateFailedDesc', "Failed to update tool status.");
      setMcpToolsError(detail);
      toast({ 
        title: t('jarvis.toolStatusUpdateFailedTitle', "Error Updating Tool"), 
        description: detail, 
        status: "error" 
      });
    }
  };

  const handleEditMcpTool = (tool: MCPTool) => {
    setCurrentMcpTool({...tool});
  };

  const handleCancelEdit = () => {
    setCurrentMcpTool(null);
  };

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
        {Object.values(savedKeysStatus).some(v => v) && !apiKeyError && (
          <Alert status="success" borderRadius="md" mt={2}>
            <AlertIcon />
            {/* Determine model to display using state variables */}
            {(() => {
              const modelNameToDisplay = selectedModel || getDefaultModel();
              const baseText = t('jarvis.keysConfigured', 'API key configured');
              return modelNameToDisplay 
                ? `${baseText} (${t('jarvis.usingModel', 'Using')}: ${modelNameToDisplay})` 
                : baseText;
            })()}
          </Alert>
        )}

        <Tabs
          variant="soft-rounded"
          colorScheme="blue"
          index={activeTab}
          onChange={setActiveTab}
        >
          <TabList mb="1em" flexWrap="wrap">
            <Tab><Icon as={FaCommentDots} mr={2} />{t('jarvis.chat')}</Tab>
            <Tab><Icon as={FaUpload} mr={2} />{t('customKnowledge.uploadTab', 'Customer knowledge')}</Tab>
            <Tab><Icon as={FaEdit} mr={2} />{t('jarvis.addKnowledge', 'Add Knowledge')}</Tab>
            <Tab><Icon as={FaHistory} mr={2} />{t('customKnowledge.historyTab', 'History')}</Tab>
            <Tab><Icon as={FaCog} mr={2} />{t('jarvis.apiSettings')}</Tab>
            <Tab><Icon as={FaKey} mr={2} />{t('jarvis.knowledgeTokens', 'Knowledge Tokens')}</Tab>
            <Tab><Icon as={FaTools} mr={2} />{t('jarvis.mcpTools', 'MCP Tools')}</Tab>
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
                    />
                  ))}
                  {isLoading && (
                    <Flex w="full" justify="flex-start" mb={3}>
                      <Box 
                        maxW="80%" 
                        bg={useColorModeValue('gray.50', 'gray.700')} 
                        color={useColorModeValue('gray.800', 'gray.100')} 
                        px={4} 
                        py={3} 
                        borderRadius="xl" 
                        boxShadow="sm"
                        borderWidth="1px"
                        borderColor={useColorModeValue('gray.200', 'gray.600')}
                      >
                        <HStack align="center" spacing={3}>
                          <Icon as={FaRobot} />
                          <HStack spacing={1} align="center">
                            <Box
                              w="8px"
                              h="8px"
                              borderRadius="full"
                              bg={useColorModeValue('blue.500', 'blue.200')}
                              sx={typingAnimation}
                            />
                            <Box
                              w="8px"
                              h="8px"
                              borderRadius="full"
                              bg={useColorModeValue('blue.500', 'blue.200')}
                              sx={typingAnimation}
                            />
                            <Box
                              w="8px"
                              h="8px"
                              borderRadius="full"
                              bg={useColorModeValue('blue.500', 'blue.200')}
                              sx={typingAnimation}
                            />
                          </HStack>
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
                      {t('customKnowledge.selectFiles', '选择文件')}
                    </FormLabel>
                    <Button as="label" htmlFor="custom-knowledge-upload" colorScheme="blue" mb={2}>
                      {t('customKnowledge.selectFiles', '选择文件')}
                      <Input
                        id="custom-knowledge-upload"
                        type="file"
                        multiple
                        accept={ALLOWED_EXTENSIONS.map(ext => '.' + ext).join(',')}
                        onChange={handleCustomFileSelect}
                        display="none"
                      />
                    </Button>
                    <FormHelperText mt={2}>
                      {t('customKnowledge.uploadHelp', `允许类型：${ALLOWED_EXTENSIONS.join(', ')}。每个文件最大${formatFileSize(MAX_FILE_SIZE)}。`)}
                    </FormHelperText>
                  </FormControl>
                  {/* Display selected file names or 'no files selected' */}
                  <Box mb={4} color="gray.500">
                    {customFiles.length === 0
                      ? t('customKnowledge.noFilesSelected', '尚未选择文件。')
                      : customFiles.map((file, idx) => (
                          <Text key={idx}>{file.name}</Text>
                        ))}
                  </Box>
                  
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
                                   const hasRequiredKey = !model.requiresKey || savedKeysStatus[model.provider] === true;
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
                         {uniqueProviders.map(provider => {
                           const hasModels = AVAILABLE_MODELS.some(model => model.provider === provider && model.requiresKey);
                           if (!hasModels) return null;
                           
                           // Determine if the key is currently saved based on state
                           const isKeySaved = savedKeysStatus[provider] === true;

                           // --- ADDED: Define conditional background color based on saved status ---
                           const cardBgColor = isKeySaved 
                             ? useColorModeValue('green.50', 'gray.750') // Subtle green tint when saved
                             : boxBgColor; // Default background otherwise
                           // --- END ADDITION ---
                           
                           return (
                             <Box 
                               key={provider} 
                               borderWidth="1px" 
                               borderRadius="lg" 
                               p={4} 
                               bg={cardBgColor} 
                               shadow="sm"
                               borderColor={borderColor} 
                             >
                               <Heading size="sm" mb={3} color={headingColor}>{provider.toUpperCase()} {t('jarvis.settingsContent.apiKeyTitle')}</Heading>
                               <Text fontSize="sm" mb={4} color={useColorModeValue('gray.600', 'gray.400')}>
                                 {t(`jarvis.settingsContent.${provider}ApiKeyDescription`,
                                    `Enter your ${provider.toUpperCase()} API key to enable ${provider.toUpperCase()}-powered models.`)}
                               </Text>
                               
                                <VStack spacing={3} align="stretch">
                                  {/* API Key Input */}
                                  <FormControl flex={1}>
                                    <InputGroup size="md">
                                      <Input
                                        id={`${provider}-apiKey`}
                                        type="password" 
                                        value={apiKeys[provider] || ''} 
                                        onChange={(e) => handleApiKeyUpdate(provider, e.target.value, apiBaseUrls[provider])} 
                                        placeholder={isKeySaved ? '********' : t('jarvis.settingsContent.apiKeyPlaceholder')} 
                                        bg={inputBg}
                                        borderColor={borderColor}
                                      />
                                      {isKeySaved && (
                                        <InputRightElement>
                                          <IconButton
                                            aria-label={t('jarvis.deleteApiKeyTooltip', 'Delete Saved Key')}
                                            icon={<FaTrashAlt />}
                                            size="sm"
                                            variant="ghost"
                                            colorScheme="red"
                                            onClick={() => handleDeleteApiKey(provider)}
                                            title={t('jarvis.deleteApiKeyTooltip', 'Delete Saved Key')}
                                          />
                                        </InputRightElement>
                                      )}
                                    </InputGroup>
                                     {isKeySaved && (
                                       <HStack mt={1}>
                                          <Icon as={FaCheckCircle} color="green.500" boxSize="0.8em"/>
                                          <Text fontSize="xs" color="green.500">
                                            {t('jarvis.apiKeySet')}
                                          </Text>
                                        </HStack>
                                     )}
                                  </FormControl>
                                  
                                  {/* Base URL Input */}
                                  <FormControl flex={1}>
                                    <FormLabel htmlFor={`${provider}-baseUrl`} fontWeight="semibold">
                                      {t('jarvis.settingsContent.modelBaseUrl', 'Model Base URL (Optional)')} 
                                    </FormLabel>
                                    <InputGroup size="md">
                                      <Input
                                        id={`${provider}-baseUrl`}
                                        type="text"
                                        value={apiBaseUrls[provider] || ''} 
                                        onChange={(e) => handleBaseUrlUpdate(provider, e.target.value)}
                                        placeholder={t(`jarvis.settingsContent.${provider}BaseUrlPlaceholder`, `e.g., https://api.${provider}.com/v1`)}
                                        bg={inputBg}
                                        borderColor={borderColor}
                                      />
                                      {apiBaseUrls[provider] && (
                                        <InputRightElement>
                                          <IconButton
                                            aria-label={t('jarvis.clearBaseUrlTooltip', 'Clear Base URL')}
                                            icon={<FaTrashAlt />}
                                            size="sm"
                                            variant="ghost"
                                            colorScheme="red" 
                                            onClick={() => handleBaseUrlUpdate(provider, '')}
                                            title={t('jarvis.clearBaseUrlTooltip', 'Clear Base URL')} 
                                          />
                                        </InputRightElement>
                                      )}
                                    </InputGroup>
                                    <FormHelperText fontSize="xs">
                                      {t('jarvis.settingsContent.baseUrlHelp', 'Only needed for custom deployments or proxies.')}
                                    </FormHelperText>
                                  </FormControl>
                                  
                                  {/* Save Button */}
                                  <Button
                                    onClick={() => handleSaveApiKey(provider)}
                                    isDisabled={!(savedKeysStatus[provider] === true || (apiKeys[provider] && apiKeys[provider].length >= 5))}
                                    colorScheme="blue"
                                    title={t('jarvis.saveApiKeyTooltip', 'Save Settings for {{provider}}', { provider: provider.toUpperCase() })}
                                    alignSelf="flex-end"
                                    leftIcon={<FaSync />}
                                  >
                                    {t('common.save', 'Save')}
                                  </Button>
                                </VStack>
                                
                                 {/* Model Help Text */}
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

            <TabPanel p={4}>
              <VStack spacing={6} align="stretch">
                <Heading size="md" color={headingColor}>{t('jarvis.knowledgeTokensTitle', 'External Knowledge Tokens')}</Heading>
                <Text color={useColorModeValue('gray.600', 'gray.400')}>
                  {t('jarvis.knowledgeTokensDesc', 'Add tokens from other users or sources. Jarvis will use these tokens to search their shared knowledge bases via the secure /shared-knowledge/search endpoint, expanding its response capabilities.')}
                </Text>

                {/* Add New Token Form */}
                <Box borderWidth="1px" borderRadius="lg" p={4} bg={boxBgColor} shadow="sm">
                  <Heading size="sm" mb={3} color={headingColor}>{t('jarvis.addKnowledgeToken', 'Add New Token')}</Heading>
                  <VStack spacing={3}>
                    <FormControl isRequired isInvalid={!!tokenError && tokenError.includes("Nickname")}>
                      <FormLabel htmlFor="new-token-nickname">{t('jarvis.tokenNickname', 'Nickname')}</FormLabel>
                      <Input 
                        id="new-token-nickname"
                        value={newTokenNickname}
                        onChange={(e) => setNewTokenNickname(e.target.value)}
                        placeholder={t('jarvis.tokenNicknamePlaceholder', 'e.g., Team Project Alpha Token')}
                        isDisabled={isAddingToken}
                      />
                    </FormControl>
                    <FormControl isRequired isInvalid={!!tokenError && tokenError.includes("Value")}>
                      <FormLabel htmlFor="new-token-value">{t('jarvis.tokenValue', 'Token Value')}</FormLabel>
                      <Input 
                        id="new-token-value"
                        type="password" 
                        value={newTokenValue}
                        onChange={(e) => setNewTokenValue(e.target.value)}
                        placeholder={t('jarvis.tokenValuePlaceholder', 'Paste the shared token here')}
                        isDisabled={isAddingToken}
                      />
                    </FormControl>
                    <FormControl isRequired isInvalid={!!tokenError && tokenError.includes("Endpoint URL")}>
                      <FormLabel htmlFor="new-token-endpoint-url">{t('jarvis.tokenEndpointUrl', 'Token Endpoint URL')}</FormLabel>
                      <Input 
                        id="new-token-endpoint-url"
                        type="text"
                        value={newTokenEndpointUrl}
                        onChange={(e) => setNewTokenEndpointUrl(e.target.value)}
                        placeholder={t('jarvis.tokenEndpointUrlPlaceholder', 'Enter the token endpoint URL')}
                        isDisabled={isAddingToken}
                      />
                    </FormControl>
                    {tokenError && (
                        <Alert status="error" borderRadius="md" fontSize="sm">
                          <AlertIcon boxSize="16px"/>
                          {tokenError}
                        </Alert>
                    )}
                    <Button 
                      alignSelf="flex-end"
                      colorScheme="blue"
                      onClick={handleAddExternalToken}
                      isLoading={isAddingToken}
                      isDisabled={isAddingToken || !newTokenNickname || !newTokenValue || !newTokenEndpointUrl}
                    >
                      {t('jarvis.addTokenButton', 'Add Token')}
                    </Button>
                  </VStack>
                </Box>

                {/* List Existing Tokens */}
                <Box borderWidth="1px" borderRadius="lg" p={0} bg={boxBgColor} shadow="sm" overflow="hidden">
                  <Heading size="sm" p={4} pb={2} color={headingColor}>{t('jarvis.existingKnowledgeTokens', 'Existing Tokens')}</Heading>
                  {isLoadingExternalTokens ? (
                    <Center p={6}><Spinner /></Center>
                  ) : externalTokens.length === 0 ? (
                    <Text p={4} color="gray.500">{t('jarvis.noExternalTokens', 'No external knowledge tokens added yet.')}</Text>
                  ) : (
                    <TableContainer>
                      <Table variant="simple" size="sm">
                        <Thead>
                          <Tr>
                            <Th>{t('jarvis.tokenNickname', 'Nickname')}</Th>
                            <Th>{t('jarvis.tokenEndpointUrl', 'Endpoint URL')}</Th>
                            <Th>{t('jarvis.tokenAddedOn', 'Added On')}</Th>
                            <Th>{t('jarvis.tokenIsValid', 'Valid')}</Th>
                            <Th isNumeric>{t('common.actions', 'Actions')}</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {externalTokens.map(token => (
                            <Tr key={token.id} _hover={{ bg: tableHoverBg }}>
                              <Td fontWeight="medium">{token.token_nickname}</Td>
                              <Td fontSize="sm">{token.endpoint_url || '-'}</Td>
                              <Td>{formatDateTime(token.created_at)}</Td>
                              <Td>
                                <Tag size="sm" colorScheme={token.is_valid ? 'green' : 'red'}>
                                  {token.is_valid ? t('common.yes') : t('common.no')}
                                </Tag>
                              </Td>
                              <Td isNumeric>
                                <IconButton 
                                  aria-label={t('common.delete', 'Delete')}
                                  icon={<FaTrash />}
                                  size="xs"
                                  colorScheme="red"
                                  variant="ghost"
                                  onClick={() => handleDeleteExternalToken(token.id, token.token_nickname)}
                                  // Add disabled state if needed during deletion
                                />
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </TableContainer>
                  )}
                </Box>
              </VStack>
            </TabPanel>

            <TabPanel p={4}>
              <VStack spacing={6} align="stretch">
                <Heading size="md" color={headingColor}>{t('jarvis.mcpToolsTitle', 'MCP Tools Management')}</Heading>
                <Text color={useColorModeValue('gray.600', 'gray.400')}>
                  {t('jarvis.mcpToolsDesc', 'Manage your custom MCP tools. These tools can be called by the AI to perform specific actions or retrieve information.')}
                </Text>

                {/* Add the MCPToolsHelp component here */}
                <MCPToolsHelp />

                {/* Tool List */}
                <Box borderWidth="1px" borderRadius="lg" p={0} bg={boxBgColor} shadow="sm" overflow="hidden">
                  <Flex justifyContent="space-between" alignItems="center" p={4}>
                    <Heading size="sm" color={headingColor}>
                      {t('jarvis.mcpToolsList', 'Available Tools')}
                    </Heading>
                    {!currentMcpTool && (
                      <Button 
                        size="sm" 
                        colorScheme="blue" 
                        leftIcon={<FaPlusCircle />}
                        onClick={() => setCurrentMcpTool({} as MCPTool)}
                      >
                        {t('jarvis.addTool', 'Add Tool')}
                      </Button>
                    )}
                  </Flex>
                  
                  {mcpToolsError && (
                    <Alert status="error" m={4} borderRadius="md">
                      <AlertIcon />
                      {mcpToolsError}
                      <Button ml="auto" size="sm" onClick={fetchMcpTools}>
                        {t('common.retry', 'Retry')}
                      </Button>
                    </Alert>
                  )}
                  
                  {isLoadingMcpTools ? (
                    <Center p={6}><Spinner /></Center>
                  ) : mcpTools.length === 0 && !currentMcpTool ? (
                    <Box p={4}>
                      <Alert status="info" borderRadius="md">
                        <AlertIcon />
                        <Text>{t('jarvis.noMcpTools', 'No MCP tools defined yet. Add your first tool to get started.')}</Text>
                      </Alert>
                    </Box>
                  ) : (
                    !currentMcpTool && (
                      <TableContainer overflowX="auto" maxW="100%" borderRadius="md" borderWidth="1px" borderColor={borderColor}>
                        <Table variant="simple" size="sm" style={{ tableLayout: 'fixed', minWidth: '800px' }}>
                          <Thead>
                            <Tr>
                              <Th width="150px">{t('jarvis.toolName', 'Name')}</Th>
                              <Th width="200px">{t('jarvis.toolDescription', 'Description')}</Th>
                              <Th width="250px">{t('jarvis.toolEndpoint', 'Endpoint')}</Th>
                              <Th width="80px">{t('jarvis.toolVersion', 'Version')}</Th>
                              <Th width="80px">{t('jarvis.toolStatus', 'Status')}</Th>
                              <Th isNumeric width="120px" textAlign="center">{t('common.actions', 'Actions')}</Th>
                            </Tr>
                          </Thead>
                          <Tbody>
                            {mcpTools.map(tool => (
                              <Tr key={tool.id} _hover={{ bg: tableHoverBg }}>
                                <Td width="150px">
                                  <Box overflow="hidden" maxW="150px">
                                    <Text 
                                      fontWeight="medium" 
                                      isTruncated 
                                      whiteSpace="nowrap" 
                                      overflow="hidden" 
                                      textOverflow="ellipsis"
                                      title={tool.name}
                                    >
                                      {tool.name}
                                    </Text>
                                  </Box>
                                </Td>
                                <Td width="200px">
                                  <Box overflow="hidden" maxW="200px">
                                    <Text 
                                      isTruncated 
                                      whiteSpace="nowrap" 
                                      overflow="hidden" 
                                      textOverflow="ellipsis"
                                      title={tool.description}
                                    >
                                      {tool.description}
                                    </Text>
                                  </Box>
                                </Td>
                                <Td width="250px">
                                  <Box overflow="hidden" maxW="250px">
                                    <Code 
                                      fontSize="xs" 
                                      isTruncated 
                                      display="block" 
                                      whiteSpace="nowrap" 
                                      overflow="hidden" 
                                      textOverflow="ellipsis"
                                      title={tool.entrypoint} // Add title attribute for native tooltip
                                    >
                                      {tool.entrypoint}
                                    </Code>
                                  </Box>
                                </Td>
                                <Td>{tool.version}</Td>
                                <Td>
                                  <IconButton
                                    aria-label={tool.enabled ? t('jarvis.disable', 'Disable') : t('jarvis.enable', 'Enable')}
                                    icon={tool.enabled ? <FaToggleOn /> : <FaToggleOff />}
                                    size="sm"
                                    colorScheme={tool.enabled ? "green" : "gray"}
                                    variant="ghost"
                                    onClick={() => handleToggleMcpToolStatus(tool.id!, tool.enabled, tool.name)}
                                  />
                                </Td>
                                <Td isNumeric>
                                  <HStack spacing={2} justifyContent="flex-end">
                                    <IconButton
                                      aria-label={t('common.edit', 'Edit')}
                                      icon={<FaEdit />}
                                      size="sm"
                                      colorScheme="blue"
                                      variant="solid"
                                      onClick={() => handleEditMcpTool(tool)}
                                    />
                                    <IconButton
                                      aria-label={t('common.delete', 'Delete')}
                                      icon={<FaTrash />}
                                      size="sm"
                                      colorScheme="red"
                                      variant="solid"
                                      onClick={() => handleDeleteMcpTool(tool.id!, tool.name)}
                                    />
                                  </HStack>
                                </Td>
                              </Tr>
                            ))}
                          </Tbody>
                        </Table>
                      </TableContainer>
                    )
                  )}
                </Box>

                {/* Add or Edit Tool Form */}
                {currentMcpTool && (
                  <Box borderWidth="1px" borderRadius="lg" p={4} bg={boxBgColor} shadow="sm">
                    <Heading size="sm" mb={4} color={headingColor}>
                      {currentMcpTool.id ? t('jarvis.editTool', 'Edit Tool') : t('jarvis.addNewTool', 'Add New Tool')}
                    </Heading>
                    
                    <VStack spacing={4} align="stretch">
                      <FormControl isRequired>
                        <FormLabel>{t('jarvis.toolName', 'Tool Name')}</FormLabel>
                        <Input
                          value={currentMcpTool.name || ''}
                          onChange={(e) => setCurrentMcpTool({...currentMcpTool, name: e.target.value})}
                          placeholder={t('jarvis.toolNamePlaceholder', 'e.g., jira.create_issue')}
                          isDisabled={isEditingMcpTool || isAddingMcpTool}
                        />
                        <FormHelperText>
                          {t('jarvis.toolNameHelp', 'Use descriptive names with namespaces like "service.action"')}
                        </FormHelperText>
                      </FormControl>
                      
                      <FormControl isRequired>
                        <FormLabel>{t('jarvis.toolDescription', 'Description')}</FormLabel>
                        <Textarea
                          value={currentMcpTool.description || ''}
                          onChange={(e) => setCurrentMcpTool({...currentMcpTool, description: e.target.value})}
                          placeholder={t('jarvis.toolDescriptionPlaceholder', 'Describe what this tool does...')}
                          isDisabled={isEditingMcpTool || isAddingMcpTool}
                        />
                      </FormControl>
                      
                      <FormControl isRequired>
                        <FormLabel>{t('jarvis.toolEndpoint', 'Endpoint')}</FormLabel>
                        <Input
                          value={currentMcpTool.entrypoint || ''}
                          onChange={(e) => setCurrentMcpTool({...currentMcpTool, entrypoint: e.target.value})}
                          placeholder={t('jarvis.toolEndpointPlaceholder', 'e.g., /api/v1/jira/create-issue or function_name')}
                          isDisabled={isEditingMcpTool || isAddingMcpTool}
                        />
                        <FormHelperText>
                          {t('jarvis.toolEndpointHelp', 'API endpoint or function name to call when this tool is invoked')}
                        </FormHelperText>
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>{t('jarvis.toolVersion', 'Version')}</FormLabel>
                        <Input
                          value={currentMcpTool.version || '1.0'}
                          onChange={(e) => setCurrentMcpTool({...currentMcpTool, version: e.target.value})}
                          placeholder={t('jarvis.toolVersionPlaceholder', '1.0')}
                          isDisabled={isEditingMcpTool || isAddingMcpTool}
                        />
                      </FormControl>
                      
                      <FormControl display="flex" alignItems="center">
                        <FormLabel htmlFor="tool-enabled" mb="0">
                          {t('jarvis.toolEnabled', 'Enabled')}
                        </FormLabel>
                        <Switch
                          id="tool-enabled"
                          isChecked={currentMcpTool.enabled}
                          onChange={(e) => setCurrentMcpTool({...currentMcpTool, enabled: e.target.checked})}
                          isDisabled={isEditingMcpTool || isAddingMcpTool}
                        />
                      </FormControl>
                      
                      <Box mt={2}>
                        <JSONSchemaEditor
                          value={currentMcpTool.parameters || {}}
                          onChange={(value) => setCurrentMcpTool({...currentMcpTool, parameters: value})}
                          label={t('jarvis.toolParameters', 'Parameters Schema')}
                          isRequired={true}
                          isDisabled={isEditingMcpTool || isAddingMcpTool}
                          formatButtonText={t('jarvis.formatJSON', 'Format JSON')}
                          loadExampleButtonText={t('jarvis.loadExample', 'Load Example')}
                          helpText={t('jarvis.jsonSchemaHelp', 'This should be a valid JSON Schema for the tool parameters.')}
                        />
                      </Box>
                      
                      <HStack spacing={4} justifyContent="flex-end" mt={4}>
                        <Button
                          onClick={handleCancelEdit}
                          isDisabled={isEditingMcpTool || isAddingMcpTool}
                        >
                          {t('common.cancel', 'Cancel')}
                        </Button>
                        <Button
                          colorScheme="blue"
                          isLoading={isEditingMcpTool || isAddingMcpTool}
                          onClick={currentMcpTool.id ? handleUpdateMcpTool : handleAddMcpTool}
                          leftIcon={currentMcpTool.id ? <FaEdit /> : <FaPlusCircle />}
                        >
                          {currentMcpTool.id 
                            ? t('common.update', 'Update') 
                            : t('common.add', 'Add')}
                        </Button>
                      </HStack>
                    </VStack>
                  </Box>
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