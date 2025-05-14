import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Card,
  CardHeader,
  CardBody,
  Button,
  Flex,
  Icon,
  useToast,
  VStack,
  HStack,
  Badge,
  Select,
  Input,
  Textarea,
  FormControl,
  FormLabel,
  FormHelperText,
  SimpleGrid,
  Tag,
  Spinner,
  useColorModeValue,
  Avatar,
  InputGroup,
  InputRightElement,
  Alert,
  AlertIcon,
  IconButton,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerOverlay,
  useDisclosure,
  Stack,
  Divider,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Switch
} from '@chakra-ui/react';
import { FaUsers, FaCode, FaSearch, FaRobot, FaUsersCog, FaQuestion, FaComments, FaPaperPlane, FaPlus, FaPen, FaTrash, FaCog, FaChevronDown, FaSave, FaUndo, FaHistory } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { apiClient } from '../api/client';
import { getAllApiKeys, getDefaultModel } from '../api/user';
import { getUserAgents, createAgent, updateAgent, deleteAgent } from '../api/agent';
import { getUserConversations, getConversationById, createConversation, updateConversation, addMessageToConversation, deleteConversation } from '../api/conversation';
import { getUserSettings, updateUserSettings } from '../api/settings';
import { 
  sendHybridChat, 
  type AgentConfig as ApiAgentConfig,
  type ChatHistoryItem 
} from '../api/autogen';

// Model interface matching Jarvis implementation
interface LLMModel {
  id: string;
  name: string;
  provider: string;
  requiresKey: boolean;
}

// Available models constant matching Jarvis implementation
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

interface ResearchForm {
  query: string;
  model_id: string;
  max_rounds: number;
  temperature: number;
}

interface CodeGenForm {
  task_description: string;
  model_id: string;
  max_rounds: number;
  temperature: number;
  work_dir: string;
}

interface QAForm {
  question: string;
  context: string;
  model_id: string;
  temperature: number;
}

interface Message {
  role?: string;
  name?: string;
  content: string;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  agentName?: string;
  isThinking?: boolean;
}

// Updated interface for custom agent definition with server fields
interface CustomAgent {
  id: string;
  name: string;
  type: 'assistant' | 'researcher' | 'coder' | 'critic' | 'custom';
  systemMessage: string;
  isEnabled: boolean;
  // New fields for database stored agents
  createdAt?: Date;
  updatedAt?: Date;
  // Flag to distinguish saved agents from temporary ones
  isSaved?: boolean;
}

// New interface for conversation data
interface ConversationData {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  maxRounds: number;
}

interface ChatForm {
  message: string;
  model_id: string;
  agents: CustomAgent[];
  max_rounds: number;
  conversation_id?: string;
  orchestration_type?: 'parallel' | 'sequential' | null;
  use_mcp_tools?: boolean;
}

// Custom WebSocket type with additional properties
interface CustomWebSocket extends WebSocket {
  pingInterval?: NodeJS.Timeout;
}

const AutoGenPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const chatBgColor = useColorModeValue('gray.50', 'gray.700');
  const messageBgUser = useColorModeValue('blue.50', 'blue.900');
  const messageBgAssistant = useColorModeValue('gray.50', 'gray.700');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [statusChecked, setStatusChecked] = useState(false);
  const [isAvailable, setIsAvailable] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState('');
  
  // New state for API key management
  const [savedKeysStatus, setSavedKeysStatus] = useState<Record<string, boolean>>({});
  const [apiKeyLoading, setApiKeyLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [apiKeyError, setApiKeyError] = useState<string | null>(null);
  const [modelLoading, setModelLoading] = useState(true);
  
  // Form states
  const [researchForm, setResearchForm] = useState<ResearchForm>({
    query: '',
    model_id: '',
    max_rounds: 15,
    temperature: 0.5
  });
  
  const [codeGenForm, setCodeGenForm] = useState<CodeGenForm>({
    task_description: '',
    model_id: '',
    max_rounds: 10,
    temperature: 0.2,
    work_dir: 'workspace'
  });
  
  const [qaForm, setQAForm] = useState<QAForm>({
    question: '',
    context: '',
    model_id: '',
    temperature: 0.3
  });

  // State for agent management
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [customAgents, setCustomAgents] = useState<CustomAgent[]>([]);
  const [savedAgents, setSavedAgents] = useState<CustomAgent[]>([]);
  const [currentAgent, setCurrentAgent] = useState<CustomAgent | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [agentsLoading, setAgentsLoading] = useState(false);
  
  // New state for conversation management
  const [conversations, setConversations] = useState<ConversationData[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [currentConversation, setCurrentConversation] = useState<ConversationData | null>(null);
  
  // Conversation drawer state
  const { 
    isOpen: isConversationDrawerOpen, 
    onOpen: onConversationDrawerOpen, 
    onClose: onConversationDrawerClose 
  } = useDisclosure();
  
  // User settings state
  const [userSettings, setUserSettings] = useState({
    maxRounds: 10,
    defaultModel: ''
  });
  const [settingsLoading, setSettingsLoading] = useState(false);
  
  const [chatForm, setChatForm] = useState<ChatForm>({
    message: '',
    model_id: '',
    agents: [],
    max_rounds: 10,
    conversation_id: undefined,
    orchestration_type: null,
    use_mcp_tools: true
  });
  
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'system',
      content: t('agenticAI.chat.welcomeMessage'),
      timestamp: new Date(),
      agentName: 'System'
    }
  ]);
  
  const [chatLoading, setChatLoading] = useState(false);
  
  // Results states
  const [messages, setMessages] = useState<Message[]>([]);
  const [summary, setSummary] = useState<string>('');
  const [codeOutput, setCodeOutput] = useState<string>('');
  const [answer, setAnswer] = useState<string>('');

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

  // Filtered available models based on user's API keys
  const availableModels = useMemo(() => {
    return AVAILABLE_MODELS.filter(model => 
      !model.requiresKey || savedKeysStatus[model.provider] === true
    );
  }, [savedKeysStatus]);

  // Load API keys
  useEffect(() => {
    const loadApiKeys = async () => {
      setApiKeyLoading(true);
      setApiKeyError(null);
      try {
        const keysData = await getAllApiKeys();
        
        const fetchedStatus: Record<string, boolean> = {};
        
        keysData.forEach(keyInfo => {
          if (keyInfo.provider && keyInfo.is_active) {
            fetchedStatus[keyInfo.provider] = true;
          }
        });
        
        setSavedKeysStatus(fetchedStatus);
      } catch (error) {
        console.error("Error loading API keys:", error);
        setApiKeyError("Failed to load API keys.");
        setSavedKeysStatus({});
      } finally {
        setApiKeyLoading(false);
      }
    };

    loadApiKeys();
  }, []);

  // Load default model
  useEffect(() => {
    const loadDefaultModel = async () => {
      setModelLoading(true);
      try {
        const model = await getDefaultModel();
        if (model && AVAILABLE_MODELS.some(m => m.id === model)) {
          setSelectedModel(model);
          
          // Update all forms with the default model
          setResearchForm(prev => ({ ...prev, model_id: model }));
          setCodeGenForm(prev => ({ ...prev, model_id: model }));
          setQAForm(prev => ({ ...prev, model_id: model }));
          setChatForm(prev => ({ ...prev, model_id: model }));
          
          console.log("Loaded default model from API:", model);
        } else {
          // Fallback to first available model if invalid
          const firstModel = AVAILABLE_MODELS[0]?.id || 'gpt-3.5-turbo';
          setSelectedModel(firstModel);
          
          // Update all forms with the fallback model
          setResearchForm(prev => ({ ...prev, model_id: firstModel }));
          setCodeGenForm(prev => ({ ...prev, model_id: firstModel }));
          setQAForm(prev => ({ ...prev, model_id: firstModel }));
          setChatForm(prev => ({ ...prev, model_id: firstModel, agents: customAgents }));
          
          console.log("Setting default model to first available:", firstModel);
        }
      } catch (error) {
        console.error("Error loading default model:", error);
        const firstModel = AVAILABLE_MODELS[0]?.id || 'gpt-3.5-turbo';
        setSelectedModel(firstModel);
        
        // Update all forms with the fallback model
        setResearchForm(prev => ({ ...prev, model_id: firstModel }));
        setCodeGenForm(prev => ({ ...prev, model_id: firstModel }));
        setQAForm(prev => ({ ...prev, model_id: firstModel }));
        setChatForm(prev => ({ ...prev, model_id: firstModel, agents: customAgents }));
        
        console.log("Setting default model to first available on error:", firstModel);
      } finally {
        setModelLoading(false);
      }
    };
    
    loadDefaultModel();
  }, []);

  // Scroll to bottom of chat
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages]);

  // Add default agents on component mount
  useEffect(() => {
    const defaultAgent: CustomAgent = {
      id: '1',
      name: 'Assistant',
      type: 'assistant',
      systemMessage: 'You are a helpful AI assistant that provides accurate, concise information. Respond to the user\'s queries in a friendly and informative manner.',
      isEnabled: true
    };
    
    setCustomAgents([defaultAgent]);
    setChatForm(prev => ({...prev, agents: [defaultAgent]}));
  }, []);

  // Check AutoGen module status
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await apiClient.get('/autogen/status');
        // Check if status is operational, available, or ok
        setIsAvailable(response.data.status === 'operational' || 
                       response.data.status === 'available' || 
                       response.data.status === 'ok');
        
        // Store the maintenance message if provided
        if (response.data.status === 'maintenance' && response.data.message) {
          setMaintenanceMessage(response.data.message);
        }
        
        setStatusChecked(true);
      } catch (error) {
        setIsAvailable(false);
        setStatusChecked(true);
        toast({
          title: 'Error checking AutoGen status',
          description: 'Could not connect to the AutoGen module',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    };

    checkStatus();
  }, [toast]);

  // Handle form changes
  const handleResearchChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setResearchForm(prev => ({ ...prev, [name]: value }));
  };

  const handleCodeGenChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setCodeGenForm(prev => ({ ...prev, [name]: value }));
  };

  const handleQAChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setQAForm(prev => ({ ...prev, [name]: value }));
  };

  // Agent management functions
  const handleAddAgent = () => {
    setIsEditing(false);
    setCurrentAgent({
      id: Date.now().toString(),
      name: '',
      type: 'assistant',
      systemMessage: '',
      isEnabled: true
    });
    onOpen();
  };

  const handleEditAgent = (agent: CustomAgent) => {
    setIsEditing(true);
    // When showing for editing, convert underscores back to spaces for better UX
    setCurrentAgent({...agent});
    onOpen();
  };

  const handleDeleteAgent = async (agentId: string, isSaved: boolean = false) => {
    try {
      if (isSaved) {
        // Delete from the database if it's a saved agent
        await deleteAgent(agentId);
        
        // Remove from savedAgents state
        setSavedAgents(prev => prev.filter(agent => agent.id !== agentId));
        
        toast({
          title: 'Agent deleted',
          description: 'The agent has been deleted from your saved agents',
          status: 'success',
          duration: 3000,
        });
      }
      
      // Always remove from customAgents state (for current chat)
      const updatedAgents = customAgents.filter(agent => agent.id !== agentId);
      setCustomAgents(updatedAgents);
      setChatForm(prev => ({...prev, agents: updatedAgents}));
      
    } catch (error) {
      console.error("Error deleting agent:", error);
      toast({
        title: 'Error',
        description: 'Failed to delete the agent',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleToggleAgent = (agentId: string) => {
    const updatedAgents = customAgents.map(agent => 
      agent.id === agentId ? {...agent, isEnabled: !agent.isEnabled} : agent
    );
    setCustomAgents(updatedAgents);
    setChatForm(prev => ({...prev, agents: updatedAgents}));
  };

  const handleAgentChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (currentAgent) {
      setCurrentAgent({...currentAgent, [name]: value});
    }
  };

  const handleSaveAgent = async () => {
    if (!currentAgent || !currentAgent.name || !currentAgent.systemMessage) {
      toast({
        title: 'Validation Error',
        description: t('agenticAI.chat.validationError'),
        status: 'error',
        duration: 3000,
      });
      return;
    }
    
    // Sanitize the agent name by replacing spaces with underscores
    const sanitizedAgent = {
      ...currentAgent,
      name: currentAgent.name.replace(/\s+/g, '_')
    };

    try {
      let updatedAgents;
      
      // Check if we need to save this agent to the database
      const shouldSaveToDatabase = document.getElementById('saveToDatabase') as HTMLInputElement;
      
      if (shouldSaveToDatabase && shouldSaveToDatabase.checked) {
        if (isEditing && sanitizedAgent.isSaved) {
          // Update an existing saved agent
          const updatedAgent = await updateAgent(sanitizedAgent.id, {
            name: sanitizedAgent.name,
            type: sanitizedAgent.type,
            systemMessage: sanitizedAgent.systemMessage
          });
          
          // Update savedAgents state
          setSavedAgents(prev => prev.map(agent => 
            agent.id === updatedAgent.id ? {...updatedAgent, isEnabled: false, isSaved: true} : agent
          ));
          
          toast({
            title: 'Agent updated',
            description: 'The agent has been updated in your saved agents',
            status: 'success',
            duration: 3000,
          });
        } else {
          // Create a new saved agent
          const createdAgent = await createAgent({
            name: sanitizedAgent.name,
            type: sanitizedAgent.type,
            systemMessage: sanitizedAgent.systemMessage
          });
          
          // Add to savedAgents state
          setSavedAgents(prev => [...prev, {...createdAgent, isEnabled: false, isSaved: true}]);
          
          // Update the sanitizedAgent with the returned ID and saved status
          sanitizedAgent.id = createdAgent.id;
          sanitizedAgent.isSaved = true;
          
          toast({
            title: 'Agent saved',
            description: 'The agent has been saved to your agent library',
            status: 'success',
            duration: 3000,
          });
        }
      }
      
      // Always update the current chat agents
      if (isEditing) {
        updatedAgents = customAgents.map(agent => 
          agent.id === sanitizedAgent.id ? sanitizedAgent : agent
        );
      } else {
        updatedAgents = [...customAgents, sanitizedAgent];
      }
      
      setCustomAgents(updatedAgents);
      setChatForm(prev => ({...prev, agents: updatedAgents}));
      
      // Show a toast if the name was changed
      if (sanitizedAgent.name !== currentAgent.name) {
        toast({
          title: 'Agent Name Modified',
          description: 'Spaces in agent name were replaced with underscores to ensure compatibility.',
          status: 'info',
          duration: 5000,
        });
      }
      
      onClose();
      
    } catch (error) {
      console.error("Error saving agent:", error);
      toast({
        title: 'Error',
        description: 'Failed to save the agent',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Chat handlers
  const handleChatChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setChatForm(prev => ({ ...prev, [name]: value }));
  };

  const handleMaxRoundsChange = (value: string) => {
    setChatForm(prev => ({ ...prev, max_rounds: parseInt(value) || 5 }));
    
    // Save the max rounds setting to user preferences
    updateUserSettings({ maxRounds: parseInt(value) || 5 })
      .catch(error => {
        console.error("Error saving max rounds setting:", error);
      });
  };

  // Add WebSocket hooks at the component level
  const [socket, setSocket] = useState<CustomWebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef<CustomWebSocket | null>(null);

  // Authentication state (assuming it comes from a context or props, adjust as needed)
  // For demonstration, let's assume auth is a prop or from a context like useAuth()
  // const { isAuthenticated } = useAuth(); // Example if using an auth context
  // For now, let's assume isAuthenticated is a state variable for this example
  const [isAuthenticated, setIsAuthenticated] = useState(false); // Placeholder - REMOVE if auth comes from elsewhere

  // Load user settings and conversations (simplified for focus)
  useEffect(() => {
    // Simulate fetching user and setting isAuthenticated
    // In a real app, this would be your actual auth check
    const token = localStorage.getItem('access_token');
    console.log('[AuthCheck useEffect] Token from localStorage:', token ? 'present' : 'absent'); // ADDED
    if (token) {
      // Replace with actual user validation if needed
      setIsAuthenticated(true);
      console.log('[AuthCheck useEffect] Setting isAuthenticated to true'); // ADDED
    } else {
      setIsAuthenticated(false);
      console.log('[AuthCheck useEffect] Setting isAuthenticated to false'); // ADDED
    }
  }, []);

  // Function to connect to the WebSocket - now wrapped in useCallback
  const connectToWebSocket = useCallback((conversationId: string, token: string) => {
    console.log('[connectToWebSocket] Entered. conversationId:', conversationId, 'token:', token ? 'present' : 'absent');

    if (!conversationId || !token) {
      console.warn('[connectToWebSocket] Missing conversationId or token. Aborting.');
      return;
    }

    if (socketRef.current) {
      console.log('[connectToWebSocket] Closing existing socket before creating a new one.');
      if (socketRef.current.pingInterval) {
        clearInterval(socketRef.current.pingInterval);
      }
      socketRef.current.close();
      socketRef.current = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use a more explicit way to get hostname and port, fallback to window.location.host if needed
    const hostname = window.location.hostname;
    const port = window.location.port ? `:${window.location.port}` : ''; // Vite dev server port (e.g., :5173)
    const hostAndPort = `${hostname}${port}`;

    const wsUrl = `${protocol}//${hostAndPort}/ws/chat/${conversationId}?token=${token}`;
    console.log(`[WebSocket] Attempting to connect to: ${wsUrl}`);

    const newSocket = new WebSocket(wsUrl) as CustomWebSocket;
    socketRef.current = newSocket;
    setSocket(newSocket); 

    newSocket.onopen = () => {
      console.log('[WebSocket] onopen: Connection established.');
      setIsConnected(true);
      const pingInterval = setInterval(() => {
        if (newSocket.readyState === WebSocket.OPEN) {
          newSocket.send('ping');
        }
      }, 30000);
      newSocket.pingInterval = pingInterval;
    };

    newSocket.onclose = (event) => {
      console.log('[WebSocket] onclose: Connection closed.', event.code, event.reason, event.wasClean);
      setIsConnected(false);
      if (newSocket.pingInterval) clearInterval(newSocket.pingInterval);
      if (socketRef.current === newSocket) socketRef.current = null; setSocket(null);
    };

    newSocket.onerror = (errorEvent) => {
      console.error('[WebSocket] onerror: Connection error.', errorEvent);
      setIsConnected(false);
      if (newSocket.pingInterval) clearInterval(newSocket.pingInterval);
      if (socketRef.current === newSocket) socketRef.current = null; setSocket(null);
    };

    newSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[WebSocket] Received data:', JSON.stringify(data));
        if (data.type === 'agent_message') {
          const message = data.data.message;
          console.log('[WebSocket] Processing agent_message:', JSON.stringify(message));
          if (message.role !== 'system' && message.content) {
            const agentMsg: ChatMessage = {
              id: `${Date.now()}-${Math.random()}`,
              role: message.role,
              content: message.content,
              timestamp: new Date(),
              agentName: message.agent || 'Assistant',
              isThinking: false,
            };
            console.log('[WebSocket] agentMsg constructed:', JSON.stringify(agentMsg));
            setChatMessages(prev => {
              console.log('[WebSocket] prevChatMessages before update:', JSON.stringify(prev.map(m => ({ id: m.id, agent: m.agentName, content: m.content.substring(0,20) + "..." }))));
              const filteredMessages = prev.filter(msg => 
                !(msg.isThinking && msg.agentName === agentMsg.agentName)
              );
              return [...filteredMessages, agentMsg];
            });
            // Storing in backend removed for brevity here, but should be present
          }
        } else if (data.type === 'agent_thinking') {
          const thinkingMsg: ChatMessage = {
            id: `thinking-${data.data.agent_name}-${Date.now()}`,
            role: 'assistant',
            content: `${t('agenticAI.chat.thinking', 'Thinking')}...`,
            timestamp: new Date(),
            agentName: data.data.agent_name,
            isThinking: true
          };
          setChatMessages(prev => {
            const hasThinking = prev.some(msg => msg.isThinking && msg.agentName === thinkingMsg.agentName);
            if (hasThinking) return prev;
            return [...prev, thinkingMsg];
          });
        } else if (data.type === 'pong') {
          console.debug('Pong received');
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err);
      }
    };
  }, [t]); // t from useTranslation is a dependency of onmessage if it uses t()

  // Effect to manage WebSocket connection based on conversation and auth state
  useEffect(() => {
    const wsToken = localStorage.getItem('access_token'); // Re-fetch for safety, can also use token from state

    // DETAILED LOGGING ADDED HERE
    console.log(
      `[AutoGenPage useEffect WS] Evaluating conditions. isAuthenticated: ${isAuthenticated}, token: ${wsToken ? 'present' : 'absent'}`
    );
    if (currentConversation) {
      console.log(
        `[AutoGenPage useEffect WS] currentConversation object IS PRESENT. ID: ${currentConversation.id}, Full Object:`,
        JSON.stringify(currentConversation) // Removed .name as it might not exist or cause issues with stringify if undefined
      );
    } else {
      console.log(
        `[AutoGenPage useEffect WS] currentConversation object IS NULL or UNDEFINED.`
      );
    }
    // END DETAILED LOGGING

    if (isAuthenticated && currentConversation && currentConversation.id && wsToken) {
      console.log(
        `[AutoGenPage useEffect WS] Conditions MET. Attempting to connect for conversation ID: ${currentConversation.id}.`
      );
      connectToWebSocket(currentConversation.id, wsToken);
    } else {
      console.log(
        `[AutoGenPage useEffect WS] Conditions NOT met. WebSocket will not be connected or will be closed.`
      );
      // Log condition breakdown
      console.log(
        `[AutoGenPage useEffect WS] Condition check: isAuthenticated=${isAuthenticated}, currentConversationExists=${!!currentConversation}, currentConversationHasId=${!!(currentConversation && currentConversation.id)}, tokenPresent=${!!wsToken}`
      );

      // Assuming socketRef is the correct name for the WebSocket reference
      if (socketRef.current) {
        console.log(
          "[AutoGenPage useEffect WS] Cleanup: Closing existing WebSocket connection due to unmet conditions."
        );
        if (socketRef.current.pingInterval) { // Check if pingInterval exists before clearing
            clearInterval(socketRef.current.pingInterval);
        }
        socketRef.current.close();
        socketRef.current = null;
        // setSocket(null); // These were in the original code block that was replaced, might be needed
        // setIsConnected(false); // Re-evaluate if these are necessary here
      }
    }

    return () => {
      // Assuming socketRef is the correct name for the WebSocket reference
      if (socketRef.current) {
        console.log(
          "[AutoGenPage useEffect WS] Cleanup in hook return: Closing WebSocket if open."
        );
        if (socketRef.current.pingInterval) { // Check if pingInterval exists before clearing
            clearInterval(socketRef.current.pingInterval);
        }
        socketRef.current.close();
        socketRef.current = null;
        // setSocket(null); // Re-evaluate
        // setIsConnected(false); // Re-evaluate
      }
    };
  }, [isAuthenticated, currentConversation, connectToWebSocket]); // Dependencies updated

  // Cleanup WebSocket on component unmount
  useEffect(() => {
    return () => {
      if (socket) {
        if (socket.pingInterval) {
          clearInterval(socket.pingInterval);
        }
        socket.close();
        setSocket(null);
      }
    };
  }, [socket]);

  // Modify the chat submit handler to include conversation_id parameter and connect WebSocket
  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatForm.message.trim()) return;

    // console.log('[handleChatSubmit] Current selectedConversation:', JSON.stringify(currentConversation));
    // console.log('[handleChatSubmit] Current chatForm.conversation_id:', chatForm.conversation_id);
    // console.log('[handleChatSubmit] IsAuthenticated:', isAuthenticated);
    // console.log('[handleChatSubmit] Token in localStorage:', localStorage.getItem('access_token') ? 'present' : 'absent'); // CORRECTED TOKEN KEY FOR LOGGING

    setChatLoading(true);

    const userMessageContent = chatForm.message;
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: userMessageContent,
      timestamp: new Date(),
      agentName: 'User' 
    };
    
    setChatMessages(prev => [...prev, userMessage]);
    setChatForm(prev => ({ ...prev, message: '' }));
    
    try {
      let conversationId = chatForm.conversation_id;
      
      if (!conversationId) {
        const conversationTitle = userMessageContent.substring(0, 50) + (userMessageContent.length > 50 ? '...' : '');
        const conversation = await createConversation({
          title: conversationTitle,
          maxRounds: chatForm.max_rounds || userSettings.maxRounds || 10
        });
        conversationId = conversation.id;
        setCurrentConversation(conversation);
        setChatForm(prev => ({ ...prev, conversation_id: conversationId }));
        setConversations(prev => [conversation, ...prev]);
      }
      
      if (conversationId) {
        // Make sure to pass the token to connectToWebSocket
        // const token = localStorage.getItem('LUMOS_TOKEN'); // This block should be removed / remain commented
        // if (token) {
        //   connectToWebSocket(conversationId, token);
        // } else {
        //   console.error('[handleChatSubmit] LUMOS_TOKEN not found in localStorage. Cannot connect WebSocket.');
        //   toast({
        //     title: t('common.warning'),
        //     description: t('agenticAI.chat.webSocketTokenError', 'Could not retrieve authentication token for real-time updates. Chat will proceed without live updates.'),
        //     status: 'warning',
        //     duration: 7000,
        //     isClosable: true,
        //   });
        // }
      }
      
      const historyForApi: ChatHistoryItem[] = chatMessages
        .filter(msg => !msg.isThinking && msg.id !== userMessage.id) 
        .map(msg => ({
          role: msg.role,
          content: msg.content,
          agent: msg.agentName !== 'User' && msg.agentName !== 'System' ? msg.agentName : undefined
        }));

      const apiAgents: ApiAgentConfig[] = chatForm.agents
        .filter(agent => agent.isEnabled)
        .map(agent => ({
          name: agent.name,
          type: agent.type,
          systemMessage: agent.systemMessage 
        }));
      
      const defaultAgents: ApiAgentConfig[] = [{ name: 'Assistant', type: 'assistant', systemMessage: 'You are a helpful AI assistant.' }];

      if (conversationId) {
        await addMessageToConversation(conversationId, {
            role: 'user',
            content: userMessageContent,
        });
      }

      console.log('[handleChatSubmit] Calling sendHybridChat with userMessage:', userMessageContent, 'apiAgents:', apiAgents.length > 0 ? apiAgents : defaultAgents); // Added log
      const response = await sendHybridChat(
        userMessageContent,
        apiAgents.length > 0 ? apiAgents : defaultAgents,
        {
          modelId: chatForm.model_id || userSettings.defaultModel,
          maxRounds: chatForm.max_rounds || userSettings.maxRounds || 10,
          conversationId: conversationId,
          history: historyForApi,
          orchestrationType: chatForm.orchestration_type,
          useMcpTools: chatForm.use_mcp_tools
        }
      );
      
      console.log('[handleChatSubmit] Received response from sendHybridChat:', JSON.stringify(response, null, 2)); // Added log

      if (response.messages && response.messages.length > 0) {
        console.log('[handleChatSubmit] response.messages is valid and has length:', response.messages.length); // Added log
        const newMessagesFromApi = response.messages.map((msg: ChatHistoryItem) => ({
          id: Date.now().toString() + Math.random().toString(),
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
          timestamp: new Date(),
          agentName: msg.agent || 'Assistant'
        }));
        
        console.log('[handleChatSubmit] Mapped newMessagesFromApi:', JSON.stringify(newMessagesFromApi, null, 2)); // Added log
        
        setChatMessages(prev => {
            console.log('[handleChatSubmit setChatMessages] Previous chatMessages:', JSON.stringify(prev.map(m => ({ id: m.id, agent: m.agentName, content: m.content.substring(0,30) + "..." })), null, 2)); // Added log
            const updatedMessages = [...prev];
            newMessagesFromApi.forEach(newMessage => {
                // Remove "thinking" message for this agent if one exists
                const thinkingIndex = updatedMessages.findIndex(m => m.isThinking && m.agentName === newMessage.agentName);
                if (thinkingIndex !== -1) {
                    updatedMessages.splice(thinkingIndex, 1);
                }
                // Add new message (temporarily bypassing duplicate check for diagnostics)
                // if (!updatedMessages.some(p => p.content === newMessage.content && p.agentName === newMessage.agentName && p.role === newMessage.role)) {
                updatedMessages.push(newMessage);
                // }
            });
            console.log('[handleChatSubmit setChatMessages] New chatMessages to be set:', JSON.stringify(updatedMessages.map(m => ({ id: m.id, agent: m.agentName, content: m.content.substring(0,30) + "..." })), null, 2)); // Added log
            return updatedMessages;
        });

        if (conversationId) {
            for (const msg of newMessagesFromApi) {
                if (msg.role === 'assistant') {
                     await addMessageToConversation(conversationId, {
                        role: 'assistant',
                        content: msg.content,
                        agentName: msg.agentName
                    });
                }
            }
        }
      }
    } catch (error) {
      console.error('Error sending hybrid chat message:', error);
      toast({
        title: t('common.error'),
        description: t('agenticAI.chat.errorSending'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setChatLoading(false);
    }
  };

  // Reset chat
  const handleResetChat = () => {
    setChatMessages([
      {
        id: '1',
        role: 'system',
        content: t('agenticAI.chat.welcomeMessage'),
        timestamp: new Date(),
        agentName: 'System'
      }
    ]);
  };

  // Submit handlers
  const handleResearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setMessages([]);
    setSummary('');
    
    try {
      const response = await apiClient.post('/autogen/research', researchForm);
      setMessages(response.data.messages);
      setSummary(response.data.summary.summary);
      toast({
        title: 'Research completed',
        description: 'The multi-agent research workflow has completed',
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
    } catch (error) {
      toast({
        title: 'Research failed',
        description: 'There was an error running the research workflow',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCodeGenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setMessages([]);
    setCodeOutput('');
    
    try {
      const response = await apiClient.post('/autogen/code-generation', codeGenForm);
      setMessages(response.data.messages);
      setCodeOutput(response.data.output_path);
      toast({
        title: 'Code generation completed',
        description: 'The multi-agent code generation workflow has completed',
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
    } catch (error) {
      toast({
        title: 'Code generation failed',
        description: 'There was an error running the code generation workflow',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleQASubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setAnswer('');
    
    try {
      // Split context by newlines into array
      const contextArray = qaForm.context.split('\n').filter(line => line.trim() !== '');
      
      const response = await apiClient.post('/autogen/qa', {
        ...qaForm,
        context: contextArray
      });
      setAnswer(response.data.answer);
      toast({
        title: 'Question answered',
        description: 'The QA workflow has completed',
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
    } catch (error) {
      toast({
        title: 'QA failed',
        description: 'There was an error running the QA workflow',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Add useEffect to load saved agents
  useEffect(() => {
    const loadSavedAgents = async () => {
      setAgentsLoading(true);
      try {
        const agents = await getUserAgents();
        setSavedAgents(agents.map(agent => ({
          ...agent,
          isEnabled: false,
          isSaved: true
        })));
        console.log("Loaded saved agents:", agents);
      } catch (error) {
        console.error("Error loading saved agents:", error);
        toast({
          title: 'Error',
          description: 'Failed to load your saved agents',
          status: 'error',
          duration: 5000,
        });
      } finally {
        setAgentsLoading(false);
      }
    };

    loadSavedAgents();
  }, [toast]);

  // Add useEffect to load conversations
  useEffect(() => {
    const loadConversations = async () => {
      setConversationsLoading(true);
      try {
        const conversationData = await getUserConversations();
        setConversations(conversationData);
        console.log("Loaded conversations:", conversationData);
      } catch (error) {
        console.error("Error loading conversations:", error);
        toast({
          title: 'Error',
          description: 'Failed to load your conversation history',
          status: 'error',
          duration: 5000,
        });
      } finally {
        setConversationsLoading(false);
      }
    };

    loadConversations();
  }, [toast]);

  // Add useEffect to load user settings
  useEffect(() => {
    const loadUserSettings = async () => {
      setSettingsLoading(true);
      try {
        const settings = await getUserSettings();
        setUserSettings({
          maxRounds: settings.maxRounds,
          defaultModel: settings.defaultModel
        });
        
        // Update chat form with the loaded max rounds setting
        setChatForm(prev => ({
          ...prev,
          max_rounds: settings.maxRounds
        }));
        
        console.log("Loaded user settings:", settings);
      } catch (error) {
        console.error("Error loading user settings:", error);
        // Don't show toast for this, just silently fall back to default values
      } finally {
        setSettingsLoading(false);
      }
    };

    loadUserSettings();
  }, []);

  // Add function to load a specific conversation
  const loadConversation = async (conversationId: string) => {
    try {
      setChatLoading(true);
      
      // Get the conversation data with messages
      const conversation = await getConversationById(conversationId);
      
      // Update the current conversation
      setCurrentConversation(conversation);
      
      // Update messages
      setChatMessages(conversation.messages.map(msg => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.timestamp),
        agentName: msg.agentName
      })));
      
      // Update agents from the conversation config
      if (conversation.agentsConfig && Array.isArray(conversation.agentsConfig)) {
        const loadedAgents = conversation.agentsConfig.map(agentConfig => ({
          id: agentConfig.id || String(Date.now() + Math.random()),
          name: agentConfig.name,
          type: agentConfig.type as 'assistant' | 'researcher' | 'coder' | 'critic' | 'custom',
          systemMessage: agentConfig.systemMessage,
          isEnabled: true
        }));
        
        setCustomAgents(loadedAgents);
        setChatForm(prev => ({
          ...prev,
          agents: loadedAgents,
          max_rounds: conversation.maxRounds,
          conversation_id: conversationId
        }));
      }
      
      toast({
        title: 'Conversation loaded',
        description: `Loaded conversation: ${conversation.title}`,
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      console.error("Error loading conversation:", error);
      toast({
        title: 'Error',
        description: 'Failed to load the conversation',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setChatLoading(false);
    }
  };

  if (!statusChecked) {
    return (
      <Container maxW="container.xl" py={8}>
        <Flex justify="center" align="center" h="50vh">
          <Spinner size="xl" />
          <Text ml={4}>Checking AutoGen module status...</Text>
        </Flex>
      </Container>
    );
  }

  if (!isAvailable) {
    return (
      <Container maxW="container.xl" py={8}>
        <Card bg={cardBg} boxShadow="md" borderWidth="1px" borderColor={borderColor}>
          <CardHeader>
            <Heading size="lg">AutoGen Module Unavailable</Heading>
          </CardHeader>
          <CardBody>
            <Text>
              {maintenanceMessage || 
                "The AutoGen module appears to be unavailable or not installed. Please contact your administrator or refer to the documentation for installation instructions."}
            </Text>
            <Button 
              mt={4} 
              colorScheme="blue" 
              onClick={() => window.location.reload()}
            >
              Retry Connection
            </Button>
          </CardBody>
        </Card>
      </Container>
    );
  }

  // No API key warning
  const noApiKeys = !apiKeyLoading && Object.keys(savedKeysStatus).length === 0;

  return (
    <Container maxW="container.xl" py={8}>
      <Box mb={8}>
        <Heading as="h1" size="2xl" mb={2}>
          {t('agenticAI.title')}
        </Heading>
        <Text fontSize="lg" color="gray.500">
          {t('agenticAI.subtitle')}
        </Text>
      </Box>

      {noApiKeys && (
        <Alert status="warning" mb={4}>
          <AlertIcon />
          {t('jarvis.continueWithoutKeys', 'You need to configure API keys in the Jarvis assistant to use most models.')}
        </Alert>
      )}

      <Tabs variant="enclosed" colorScheme="blue">
        <TabList>
          <Tab><Icon as={FaComments} mr={2} /> {t('agenticAI.chat.title')}</Tab>
          <Tab><Icon as={FaUsers} mr={2} /> {t('agenticAI.research.title')}</Tab>
          <Tab><Icon as={FaCode} mr={2} /> {t('agenticAI.codeGeneration.title')}</Tab>
          <Tab><Icon as={FaQuestion} mr={2} /> {t('agenticAI.qa.title')}</Tab>
        </TabList>

        <TabPanels>
          {/* Chat Tab */}
          <TabPanel>
            <Card bg={cardBg} borderWidth="1px" borderColor={borderColor} h="70vh" display="flex" flexDirection="column">
              <CardHeader borderBottomWidth="1px" borderColor={borderColor} pb={2}>
                <Flex justify="space-between" align="center" wrap="wrap" gap={2}>
                  <HStack>
                    <Heading size="md">{t('agenticAI.chat.title')}</Heading>
                    {currentConversation && (
                      <Text fontSize="sm" color="gray.500">- {currentConversation.title}</Text>
                    )}
                  </HStack>
                  <HStack>
                    <Button 
                      size="sm" 
                      leftIcon={<Icon as={FaHistory} />}
                      onClick={onConversationDrawerOpen}
                      colorScheme="blue"
                      variant="outline"
                    >
                      {t('agenticAI.chat.conversations')}
                    </Button>
                    <Button 
                      size="sm" 
                      leftIcon={<Icon as={FaCog} />}
                      onClick={() => onOpen()}
                      colorScheme="teal"
                    >
                      {t('agenticAI.chat.manageAgents')}
                    </Button>
                    <FormControl w="200px">
                      {modelLoading ? (
                        <Spinner size="sm" />
                      ) : (
                        <Select 
                          name="model_id"
                          value={chatForm.model_id}
                          onChange={handleChatChange}
                          size="sm"
                        >
                          {availableModels.map((model) => (
                            <option 
                              key={model.id} 
                              value={model.id}
                              disabled={model.requiresKey && !savedKeysStatus[model.provider]}
                            >
                              {model.name} {model.requiresKey && !savedKeysStatus[model.provider] ? 
                                ` (${t('jarvis.requiresKey')})` : ''}
                            </option>
                          ))}
                        </Select>
                      )}
                    </FormControl>
                    <Button size="sm" onClick={handleResetChat}>{t('agenticAI.chat.reset')}</Button>
                  </HStack>
                </Flex>
                
                {/* Max rounds configuration */}
                <Flex mt={2} justify="space-between" align="center">
                  <FormControl display="flex" alignItems="center" maxW="300px">
                    <FormLabel htmlFor="max_rounds" mb="0" fontSize="sm" mr={2}>
                      {t('agenticAI.chat.maxRounds')}:
                    </FormLabel>
                    <NumberInput 
                      size="sm" 
                      maxW="100px" 
                      min={1} 
                      max={30} 
                      value={chatForm.max_rounds}
                      onChange={handleMaxRoundsChange}
                    >
                      <NumberInputField id="max_rounds" />
                      <NumberInputStepper>
                        <NumberIncrementStepper />
                        <NumberDecrementStepper />
                      </NumberInputStepper>
                    </NumberInput>
                  </FormControl>
                  
                  {savedAgents.length > 0 && (
                    <Menu>
                      <MenuButton as={Button} rightIcon={<FaChevronDown />} size="sm" variant="outline">
                        {t('agenticAI.chat.savedAgents')}
                      </MenuButton>
                      <MenuList>
                        {savedAgents.map(agent => (
                          <MenuItem 
                            key={agent.id}
                            onClick={() => {
                              const newAgent = {...agent, isEnabled: true, id: agent.id + '_' + Date.now()};
                              setCustomAgents(prev => [...prev, newAgent]);
                              setChatForm(prev => ({...prev, agents: [...prev.agents, newAgent]}));
                            }}
                          >
                            {agent.name.replace(/_/g, ' ')} - {agent.type}
                          </MenuItem>
                        ))}
                      </MenuList>
                    </Menu>
                  )}
                </Flex>
                
                {/* Orchestration Type and MCP Tools Controls */}
                <HStack spacing={4} mt={3} align="flex-start"> {/* Align items to flex-start for proper layout with helpers */}
                  <FormControl minW="200px">
                    <FormLabel fontSize="sm" mb={1}>{t('agenticAI.chat.orchestrationType', 'Orchestration')}</FormLabel>
                    <Select
                      size="sm"
                      value={chatForm.orchestration_type || ''}
                      onChange={(e) => setChatForm(prev => ({
                        ...prev,
                        orchestration_type: e.target.value === '' ? null : e.target.value as 'parallel' | 'sequential'
                      }))}
                    >
                      <option value="">{t('agenticAI.chat.autoDetect', 'Auto-Detect')}</option>
                      <option value="parallel">{t('agenticAI.chat.parallel', 'Parallel')}</option>
                      <option value="sequential">{t('agenticAI.chat.sequential', 'Sequential')}</option>
                    </Select>
                    <FormHelperText fontSize="xs" mt={1}>
                      {t('agenticAI.chat.orchestrationTypeHelp', 'Choose how agents collaborate')}
                    </FormHelperText>
                  </FormControl>

                  {/* Revised FormControl for Switch */}
                  <FormControl>
                    <Flex alignItems="center">
                      <Switch
                        id="use-mcp-tools"
                        isChecked={!!chatForm.use_mcp_tools}
                        onChange={(e) => setChatForm(prev => ({
                          ...prev,
                          use_mcp_tools: e.target.checked
                        }))}
                        colorScheme="blue"
                        mr={2}
                      />
                      <FormLabel htmlFor="use-mcp-tools" mb="0" fontSize="sm" fontWeight="normal" whiteSpace="nowrap">
                        {t('agenticAI.chat.useMcpTools', 'Use MCP Tools')}
                      </FormLabel>
                    </Flex>
                    <FormHelperText fontSize="xs" ml={8} mt={1}> {/* Adjusted margin for alignment */}
                       {t('agenticAI.chat.useMcpToolsHelp', 'Allow agents to use connected tools')}
                    </FormHelperText>
                  </FormControl>
                </HStack>
                
                <Flex mt={3} wrap="wrap" gap={2}>
                  {customAgents.map(agent => (
                    <Tag 
                      key={agent.id} 
                      size="md" 
                      borderRadius="full" 
                      variant={agent.isEnabled ? "solid" : "outline"}
                      colorScheme={
                        agent.type === 'researcher' ? 'blue' : 
                        agent.type === 'coder' ? 'green' : 
                        agent.type === 'critic' ? 'red' : 'gray'
                      }
                      opacity={agent.isEnabled ? 1 : 0.6}
                      cursor="pointer"
                      onClick={() => handleToggleAgent(agent.id)}
                    >
                      <Avatar
                        size="xs"
                        mr={2}
                        name={agent.name.replace(/_/g, ' ')}
                      />
                      {agent.name.replace(/_/g, ' ')}
                      <IconButton
                        aria-label="Edit agent"
                        icon={<FaPen />}
                        size="xs"
                        ml={1}
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          // When editing, display the name with spaces for editing, but keep the ID
                          const displayAgent = {...agent, name: agent.name.replace(/_/g, ' ')};
                          handleEditAgent(displayAgent);
                        }}
                      />
                    </Tag>
                  ))}
                  <IconButton
                    icon={<FaPlus />}
                    aria-label="Add agent"
                    size="sm"
                    variant="outline"
                    onClick={handleAddAgent}
                    borderRadius="full"
                  />
                </Flex>
              </CardHeader>
              <CardBody 
                flex="1" 
                overflowY="auto" 
                px={4} 
                py={2}
                bg={chatBgColor}
                display="flex"
                flexDirection="column"
              >
                <VStack spacing={4} align="stretch" flex="1">
                  {chatMessages.map((msg) => (
                    <Flex 
                      key={msg.id}
                      justify={msg.role === 'user' ? 'flex-end' : 'flex-start'}
                      mb={2}
                    >
                      {msg.role !== 'user' && (
                        <Avatar 
                          size="sm" 
                          mr={2} 
                          name={msg.agentName || 'Assistant'}
                          bg={
                            msg.role === 'system' 
                              ? 'gray.500' 
                              : msg.agentName === 'Assistant' || !msg.agentName
                                ? 'blue.500'
                                : msg.agentName.toLowerCase().includes('consultant') || msg.agentName.toLowerCase().includes('business')
                                  ? 'purple.500'
                                  : msg.agentName.toLowerCase().includes('research')
                                    ? 'cyan.500'
                                    : msg.agentName.toLowerCase().includes('coder') || msg.agentName.toLowerCase().includes('developer')
                                      ? 'green.500'
                                      : msg.agentName.toLowerCase().includes('critic')
                                        ? 'red.500'
                                        : `hsl(${msg.agentName.split('').reduce((a, b) => a + b.charCodeAt(0), 0) % 360}, 70%, 50%)`
                          }
                        />
                      )}
                      <Box 
                        maxW="80%" 
                        bg={msg.role === 'user' ? messageBgUser : messageBgAssistant}
                        borderRadius="lg"
                        p={3}
                        borderWidth="1px"
                        borderColor={borderColor}
                      >
                        {msg.agentName && msg.role !== 'user' && (
                          <Text fontSize="xs" fontWeight="bold" mb={1} color="gray.500">
                            {msg.agentName.replace(/_/g, ' ')}
                          </Text>
                        )}
                        <Text whiteSpace="pre-wrap">{msg.content}</Text>
                        <Text fontSize="xs" color="gray.500" mt={1} textAlign="right">
                          {new Date(msg.timestamp).toLocaleTimeString()}
                        </Text>
                      </Box>
                      {msg.role === 'user' && (
                        <Avatar 
                          size="sm" 
                          ml={2} 
                          name="You"
                          bg="green.500"
                        />
                      )}
                    </Flex>
                  ))}
                  <div ref={messagesEndRef} />
                </VStack>
                {chatLoading && (
                  <Flex justify="center" my={4}>
                    <Spinner size="sm" mr={2} />
                    <Text>{t('agenticAI.chat.agentsThinking')}</Text>
                  </Flex>
                )}
              </CardBody>
              <Box p={4} borderTopWidth="1px" borderColor={borderColor}>
                <form onSubmit={handleChatSubmit}>
                  <InputGroup>
                    <Textarea
                      name="message"
                      value={chatForm.message}
                      onChange={handleChatChange}
                      placeholder={t('agenticAI.chat.placeholder')}
                      pr="4.5rem"
                      resize="vertical"
                      minH="60px"
                      maxH="200px"
                      disabled={chatLoading}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          if (chatForm.message.trim()) {
                            handleChatSubmit(e);
                          }
                        }
                      }}
                    />
                    <InputRightElement width="4.5rem" h="auto" top="10px">
                      <Button 
                        h="1.75rem" 
                        size="sm" 
                        type="submit"
                        colorScheme="blue"
                        isLoading={chatLoading}
                        disabled={!chatForm.message.trim()}
                      >
                        <Icon as={FaPaperPlane} />
                      </Button>
                    </InputRightElement>
                  </InputGroup>
                  <Flex justify="space-between" align="center" mt={1}>
                    <Text fontSize="xs" color="gray.500">
                      {t('agenticAI.chat.pressEnterToSend', 'Press Enter to send, Shift+Enter for new line')}
                    </Text>
                    <Text fontSize="xs" color={chatForm.message.length > 4000 ? "red.500" : "gray.500"}>
                      {chatForm.message.length}/4000
                    </Text>
                  </Flex>
                </form>
              </Box>
            </Card>
            
            {/* Agent Management Drawer */}
            <Drawer isOpen={isOpen} placement="right" onClose={onClose} size="md">
              <DrawerOverlay />
              <DrawerContent>
                <DrawerCloseButton />
                <DrawerHeader>
                  {isEditing ? t('agenticAI.chat.editAgent') : t('agenticAI.chat.addAgent')}
                </DrawerHeader>

                <DrawerBody>
                  <VStack spacing={4} align="stretch">
                    <FormControl isRequired>
                      <FormLabel>{t('agenticAI.chat.agentName')}</FormLabel>
                      <Input 
                        name="name" 
                        value={currentAgent?.name || ''} 
                        onChange={handleAgentChange}
                        placeholder="e.g., Researcher, Code Expert" 
                      />
                    </FormControl>
                    
                    <FormControl isRequired>
                      <FormLabel>{t('agenticAI.chat.agentType')}</FormLabel>
                      <Select 
                        name="type" 
                        value={currentAgent?.type || 'assistant'}
                        onChange={handleAgentChange}
                      >
                        <option value="assistant">{t('agenticAI.chat.generalAssistant')}</option>
                        <option value="researcher">{t('agenticAI.chat.researcher')}</option>
                        <option value="coder">{t('agenticAI.chat.coder')}</option>
                        <option value="critic">{t('agenticAI.chat.critic')}</option>
                        <option value="custom">{t('agenticAI.chat.custom')}</option>
                      </Select>
                      <FormHelperText>
                        {t('agenticAI.chat.typeHelp')}
                      </FormHelperText>
                    </FormControl>
                    
                    <FormControl isRequired>
                      <FormLabel>{t('agenticAI.chat.systemMessage')}</FormLabel>
                      <Textarea 
                        name="systemMessage" 
                        value={currentAgent?.systemMessage || ''} 
                        onChange={handleAgentChange}
                        placeholder="Define the agent's role, expertise, and behavior..."
                        rows={6}
                      />
                      <FormHelperText>
                        {t('agenticAI.chat.systemMessageHelp')}
                      </FormHelperText>
                    </FormControl>
                    
                    {/* Add option to save to database */}
                    <FormControl>
                      <Flex align="center">
                        <Switch id="saveToDatabase" colorScheme="blue" mr={2} defaultChecked={currentAgent?.isSaved} />
                        <FormLabel htmlFor="saveToDatabase" mb="0">
                          {t('agenticAI.chat.saveToDatabase')}
                        </FormLabel>
                      </Flex>
                      <FormHelperText>
                        {t('agenticAI.chat.saveToDatabaseHelp')}
                      </FormHelperText>
                    </FormControl>
                    
                    <Box>
                      <Heading size="sm" mb={2}>{t('agenticAI.chat.agentTemplates')}</Heading>
                      <HStack spacing={2} wrap="wrap">
                        <Button 
                          size="sm" 
                          onClick={() => setCurrentAgent(prev => prev ? {
                            ...prev,
                            name: t('agenticAI.chat.researcher'),
                            type: "researcher",
                            systemMessage: "You are an expert research agent capable of deep investigation on topics. Your responsibilities include: thoroughly researching topics, providing comprehensive analysis, citing sources, identifying knowledge gaps, and organizing information clearly. Always maintain scholarly rigor and acknowledge limitations in knowledge."
                          } : null)}
                        >
                          {t('agenticAI.chat.researcher')}
                        </Button>
                        <Button 
                          size="sm"
                          onClick={() => setCurrentAgent(prev => prev ? {
                            ...prev,
                            name: t('agenticAI.chat.coder'),
                            type: "coder",
                            systemMessage: "You are an expert software developer with deep knowledge of programming best practices. Your responsibilities include: writing clean, efficient code, following industry best practices, providing documentation, ensuring proper error handling, writing testable code, and considering security and performance. Optimize for readability and maintainability first."
                          } : null)}
                        >
                          {t('agenticAI.chat.coder')}
                        </Button>
                        <Button 
                          size="sm"
                          onClick={() => setCurrentAgent(prev => prev ? {
                            ...prev,
                            name: t('agenticAI.chat.critic'),
                            type: "critic",
                            systemMessage: "You are an expert critical thinker and evaluator. Your responsibilities include: identifying logical fallacies, pointing out assumptions and biases, evaluating evidence quality, challenging unsupported claims, suggesting alternative perspectives, and providing constructive feedback. Maintain a respectful tone while being thorough."
                          } : null)}
                        >
                          {t('agenticAI.chat.critic')}
                        </Button>
                      </HStack>
                    </Box>
                  </VStack>
                </DrawerBody>

                <DrawerFooter>
                  <Button variant="outline" mr={3} onClick={onClose}>
                    {t('cancel', 'Cancel')}
                  </Button>
                  <Button colorScheme="blue" onClick={handleSaveAgent}>
                    {t('save', 'Save')}
                  </Button>
                  {isEditing && currentAgent && (
                    <Button 
                      colorScheme="red" 
                      ml={3} 
                      onClick={() => {
                        if (currentAgent) {
                          handleDeleteAgent(currentAgent.id, currentAgent.isSaved);
                          onClose();
                        }
                      }}
                    >
                      {t('agenticAI.chat.deleteAgent')}
                    </Button>
                  )}
                </DrawerFooter>
              </DrawerContent>
            </Drawer>
            
            {/* Conversations Drawer */}
            <Drawer isOpen={isConversationDrawerOpen} placement="left" onClose={onConversationDrawerClose} size="md">
              <DrawerOverlay />
              <DrawerContent>
                <DrawerCloseButton />
                <DrawerHeader>
                  {t('agenticAI.chat.conversationHistory')}
                </DrawerHeader>

                <DrawerBody>
                  {conversationsLoading ? (
                    <Flex justify="center" align="center" h="100%">
                      <Spinner size="lg" />
                    </Flex>
                  ) : conversations.length === 0 ? (
                    <Text color="gray.500" textAlign="center" py={8}>
                      {t('agenticAI.chat.noConversations')}
                    </Text>
                  ) : (
                    <VStack spacing={3} align="stretch">
                      {conversations.map((conversation) => (
                        <Card 
                          key={conversation.id} 
                          borderWidth="1px" 
                          borderRadius="md"
                          borderColor={currentConversation?.id === conversation.id ? 'blue.400' : borderColor}
                          _hover={{ borderColor: 'blue.300', shadow: 'sm' }}
                          cursor="pointer"
                          onClick={() => {
                            loadConversation(conversation.id);
                            onConversationDrawerClose();
                          }}
                        >
                          <CardBody py={3}>
                            <Flex justify="space-between" align="center">
                              <VStack align="start" spacing={0}>
                                <Text fontWeight="medium">{conversation.title}</Text>
                                <Text fontSize="xs" color="gray.500">
                                  {new Date(conversation.createdAt).toLocaleString()}
                                </Text>
                              </VStack>
                              <IconButton
                                aria-label="Delete conversation"
                                icon={<FaTrash />}
                                size="sm"
                                variant="ghost"
                                colorScheme="red"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  // Implement delete conversation functionality
                                  if (window.confirm(t('agenticAI.chat.confirmDeleteConversation'))) {
                                    deleteConversation(conversation.id)
                                      .then(() => {
                                        setConversations(prev => prev.filter(c => c.id !== conversation.id));
                                        
                                        // If this was the current conversation, reset the chat
                                        if (currentConversation?.id === conversation.id) {
                                          handleResetChat();
                                          setCurrentConversation(null);
                                          setChatForm(prev => ({ ...prev, conversation_id: undefined }));
                                        }
                                        
                                        toast({
                                          title: 'Conversation deleted',
                                          status: 'success',
                                          duration: 3000,
                                        });
                                      })
                                      .catch(error => {
                                        console.error("Error deleting conversation:", error);
                                        toast({
                                          title: 'Error',
                                          description: 'Failed to delete the conversation',
                                          status: 'error',
                                          duration: 5000,
                                        });
                                      });
                                  }
                                }}
                              />
                            </Flex>
                          </CardBody>
                        </Card>
                      ))}
                    </VStack>
                  )}
                </DrawerBody>

                <DrawerFooter>
                  <Button variant="outline" onClick={onConversationDrawerClose}>
                    {t('close', 'Close')}
                  </Button>
                </DrawerFooter>
              </DrawerContent>
            </Drawer>
          </TabPanel>

          {/* Research Tab */}
          <TabPanel>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={8}>
              <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
                <CardHeader>
                  <Heading size="md">{t('agenticAI.research.title')}</Heading>
                  <Text mt={2} fontSize="sm" color="gray.500">
                    {t('agenticAI.research.subtitle')}
                  </Text>
                </CardHeader>
                <CardBody>
                  <form onSubmit={handleResearchSubmit}>
                    <VStack spacing={4} align="stretch">
                      <FormControl isRequired>
                        <FormLabel>{t('agenticAI.research.questionLabel')}</FormLabel>
                        <Textarea 
                          name="query"
                          value={researchForm.query}
                          onChange={handleResearchChange}
                          placeholder={t('agenticAI.research.questionPlaceholder')}
                          rows={4}
                        />
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>{t('agenticAI.research.modelLabel')}</FormLabel>
                        {modelLoading ? (
                          <Spinner size="sm" />
                        ) : (
                          <Select 
                            name="model_id"
                            value={researchForm.model_id}
                            onChange={handleResearchChange}
                          >
                            {availableModels.map((model) => (
                              <option 
                                key={model.id} 
                                value={model.id}
                                disabled={model.requiresKey && !savedKeysStatus[model.provider]}
                              >
                                {model.name} {model.requiresKey && !savedKeysStatus[model.provider] ? 
                                  ` (${t('jarvis.requiresKey')})` : ''}
                              </option>
                            ))}
                          </Select>
                        )}
                        <FormHelperText>
                          {t('agenticAI.research.modelHelp')}
                        </FormHelperText>
                      </FormControl>
                      
                      <HStack spacing={4}>
                        <FormControl>
                          <FormLabel>{t('agenticAI.research.maxRoundsLabel')}</FormLabel>
                          <Input 
                            name="max_rounds"
                            type="number"
                            min={5}
                            max={30}
                            value={researchForm.max_rounds}
                            onChange={handleResearchChange}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>{t('agenticAI.research.temperatureLabel')}</FormLabel>
                          <Input 
                            name="temperature"
                            type="number"
                            min={0.1}
                            max={1.0}
                            step={0.1}
                            value={researchForm.temperature}
                            onChange={handleResearchChange}
                          />
                        </FormControl>
                      </HStack>
                      
                      <Button 
                        type="submit" 
                        colorScheme="blue" 
                        leftIcon={<Icon as={FaUsers} />}
                        isLoading={isLoading}
                      >
                        {t('agenticAI.research.submitButton')}
                      </Button>
                    </VStack>
                  </form>
                </CardBody>
              </Card>
              
              <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
                <CardHeader>
                  <Heading size="md">{t('agenticAI.research.resultsTitle')}</Heading>
                </CardHeader>
                <CardBody maxH="500px" overflowY="auto">
                  {isLoading ? (
                    <Flex justify="center" py={8}>
                      <Spinner />
                      <Text ml={4}>{t('agenticAI.research.running')}</Text>
                    </Flex>
                  ) : summary ? (
                    <VStack spacing={4} align="stretch">
                      <Box>
                        <Heading size="sm" mb={2}>{t('agenticAI.research.summaryTitle')}</Heading>
                        <Text whiteSpace="pre-wrap">{summary}</Text>
                      </Box>
                      <Box>
                        <Heading size="sm" mb={2}>
                          {t('agenticAI.research.conversationHistoryTitle')}
                          <Badge ml={2} colorScheme="blue">
                            {t('agenticAI.research.messagesCount', { count: messages.length })}
                          </Badge>
                        </Heading>
                        <VStack spacing={3} align="stretch" maxH="300px" overflowY="auto">
                          {messages.map((msg, idx) => (
                            <Box 
                              key={idx} 
                              p={3} 
                              borderWidth="1px" 
                              borderRadius="md"
                              borderColor={borderColor}
                            >
                              <Text fontWeight="bold" fontSize="sm" mb={1}>
                                {msg.name || msg.role || 'Unknown'}:
                              </Text>
                              <Text fontSize="sm">{msg.content}</Text>
                            </Box>
                          ))}
                        </VStack>
                      </Box>
                    </VStack>
                  ) : (
                    <Text color="gray.500" textAlign="center" py={8}>
                      {t('agenticAI.research.noResults')}
                    </Text>
                  )}
                </CardBody>
              </Card>
            </SimpleGrid>
          </TabPanel>
          
          {/* Code Generation Tab */}
          <TabPanel>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={8}>
              <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
                <CardHeader>
                  <Heading size="md">{t('agenticAI.codeGeneration.title')}</Heading>
                  <Text mt={2} fontSize="sm" color="gray.500">
                    {t('agenticAI.codeGeneration.subtitle')}
                  </Text>
                </CardHeader>
                <CardBody>
                  <form onSubmit={handleCodeGenSubmit}>
                    <VStack spacing={4} align="stretch">
                      <FormControl isRequired>
                        <FormLabel>{t('agenticAI.codeGeneration.taskLabel')}</FormLabel>
                        <Textarea 
                          name="task_description"
                          value={codeGenForm.task_description}
                          onChange={handleCodeGenChange}
                          placeholder={t('agenticAI.codeGeneration.taskPlaceholder')}
                          rows={4}
                        />
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>{t('agenticAI.research.modelLabel')}</FormLabel>
                        {modelLoading ? (
                          <Spinner size="sm" />
                        ) : (
                          <Select 
                            name="model_id"
                            value={codeGenForm.model_id}
                            onChange={handleCodeGenChange}
                          >
                            {availableModels.map((model) => (
                              <option 
                                key={model.id} 
                                value={model.id}
                                disabled={model.requiresKey && !savedKeysStatus[model.provider]}
                              >
                                {model.name} {model.requiresKey && !savedKeysStatus[model.provider] ? 
                                  ` (${t('jarvis.requiresKey')})` : ''}
                              </option>
                            ))}
                          </Select>
                        )}
                      </FormControl>
                      
                      <HStack spacing={4}>
                        <FormControl>
                          <FormLabel>{t('agenticAI.research.maxRoundsLabel')}</FormLabel>
                          <Input 
                            name="max_rounds"
                            type="number"
                            min={5}
                            max={30}
                            value={codeGenForm.max_rounds}
                            onChange={handleCodeGenChange}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>{t('agenticAI.research.temperatureLabel')}</FormLabel>
                          <Input 
                            name="temperature"
                            type="number"
                            min={0.1}
                            max={1.0}
                            step={0.1}
                            value={codeGenForm.temperature}
                            onChange={handleCodeGenChange}
                          />
                        </FormControl>
                      </HStack>
                      
                      <FormControl>
                        <FormLabel>{t('agenticAI.codeGeneration.workDirLabel')}</FormLabel>
                        <Input 
                          name="work_dir"
                          value={codeGenForm.work_dir}
                          onChange={handleCodeGenChange}
                        />
                        <FormHelperText>
                          {t('agenticAI.codeGeneration.workDirHelp')}
                        </FormHelperText>
                      </FormControl>
                      
                      <Button 
                        type="submit" 
                        colorScheme="green" 
                        leftIcon={<Icon as={FaCode} />}
                        isLoading={isLoading}
                      >
                        {t('agenticAI.codeGeneration.submitButton')}
                      </Button>
                    </VStack>
                  </form>
                </CardBody>
              </Card>
              
              <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
                <CardHeader>
                  <Heading size="md">{t('agenticAI.codeGeneration.resultsTitle')}</Heading>
                </CardHeader>
                <CardBody maxH="500px" overflowY="auto">
                  {isLoading ? (
                    <Flex justify="center" py={8}>
                      <Spinner />
                      <Text ml={4}>{t('agenticAI.codeGeneration.running')}</Text>
                    </Flex>
                  ) : codeOutput ? (
                    <VStack spacing={4} align="stretch">
                      <Box>
                        <Heading size="sm" mb={2}>{t('agenticAI.codeGeneration.locationTitle')}</Heading>
                        <Tag colorScheme="green" size="lg">{codeOutput}</Tag>
                      </Box>
                      <Box>
                        <Heading size="sm" mb={2}>
                          {t('agenticAI.codeGeneration.conversationHistoryTitle')}
                          <Badge ml={2} colorScheme="green">
                            {t('agenticAI.research.messagesCount', { count: messages.length })}
                          </Badge>
                        </Heading>
                        <VStack spacing={3} align="stretch" maxH="300px" overflowY="auto">
                          {messages.map((msg, idx) => (
                            <Box 
                              key={idx} 
                              p={3} 
                              borderWidth="1px" 
                              borderRadius="md"
                              borderColor={borderColor}
                            >
                              <Text fontWeight="bold" fontSize="sm" mb={1}>
                                {msg.name || msg.role || 'Unknown'}:
                              </Text>
                              <Text fontSize="sm" whiteSpace="pre-wrap">{msg.content}</Text>
                            </Box>
                          ))}
                        </VStack>
                      </Box>
                    </VStack>
                  ) : (
                    <Text color="gray.500" textAlign="center" py={8}>
                      {t('agenticAI.codeGeneration.noResults')}
                    </Text>
                  )}
                </CardBody>
              </Card>
            </SimpleGrid>
          </TabPanel>
          
          {/* QA Tab */}
          <TabPanel>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={8}>
              <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
                <CardHeader>
                  <Heading size="md">{t('agenticAI.qa.title')}</Heading>
                  <Text mt={2} fontSize="sm" color="gray.500">
                    {t('agenticAI.qa.subtitle')}
                  </Text>
                </CardHeader>
                <CardBody>
                  <form onSubmit={handleQASubmit}>
                    <VStack spacing={4} align="stretch">
                      <FormControl isRequired>
                        <FormLabel>{t('agenticAI.qa.questionLabel')}</FormLabel>
                        <Input 
                          name="question"
                          value={qaForm.question}
                          onChange={handleQAChange}
                          placeholder={t('agenticAI.qa.questionPlaceholder')}
                        />
                      </FormControl>
                      
                      <FormControl isRequired>
                        <FormLabel>{t('agenticAI.qa.contextLabel')}</FormLabel>
                        <Textarea 
                          name="context"
                          value={qaForm.context}
                          onChange={handleQAChange}
                          placeholder={t('agenticAI.qa.contextPlaceholder')}
                          rows={6}
                        />
                        <FormHelperText>
                          {t('agenticAI.qa.contextHelp')}
                        </FormHelperText>
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>{t('agenticAI.research.modelLabel')}</FormLabel>
                        {modelLoading ? (
                          <Spinner size="sm" />
                        ) : (
                          <Select 
                            name="model_id"
                            value={qaForm.model_id}
                            onChange={handleQAChange}
                          >
                            {availableModels.map((model) => (
                              <option 
                                key={model.id} 
                                value={model.id}
                                disabled={model.requiresKey && !savedKeysStatus[model.provider]}
                              >
                                {model.name} {model.requiresKey && !savedKeysStatus[model.provider] ? 
                                  ` (${t('jarvis.requiresKey')})` : ''}
                              </option>
                            ))}
                          </Select>
                        )}
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>{t('agenticAI.research.temperatureLabel')}</FormLabel>
                        <Input 
                          name="temperature"
                          type="number"
                          min={0.1}
                          max={1.0}
                          step={0.1}
                          value={qaForm.temperature}
                          onChange={handleQAChange}
                        />
                      </FormControl>
                      
                      <Button 
                        type="submit" 
                        colorScheme="purple" 
                        leftIcon={<Icon as={FaSearch} />}
                        isLoading={isLoading}
                      >
                        {t('agenticAI.qa.submitButton')}
                      </Button>
                    </VStack>
                  </form>
                </CardBody>
              </Card>
              
              <Card bg={cardBg} borderWidth="1px" borderColor={borderColor}>
                <CardHeader>
                  <Heading size="md">{t('agenticAI.qa.resultsTitle')}</Heading>
                </CardHeader>
                <CardBody>
                  {isLoading ? (
                    <Flex justify="center" py={8}>
                      <Spinner />
                      <Text ml={4}>{t('agenticAI.qa.running')}</Text>
                    </Flex>
                  ) : answer ? (
                    <Box p={4} borderWidth="1px" borderRadius="md" borderColor={borderColor}>
                      <Text whiteSpace="pre-wrap">{answer}</Text>
                    </Box>
                  ) : (
                    <Text color="gray.500" textAlign="center" py={8}>
                      {t('agenticAI.qa.noResults')}
                    </Text>
                  )}
                </CardBody>
              </Card>
            </SimpleGrid>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Container>
  );
};

export default AutoGenPage;
