import React, { useState, useEffect, useRef, useMemo } from 'react';
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
  Divider
} from '@chakra-ui/react';
import { FaUsers, FaCode, FaSearch, FaRobot, FaUsersCog, FaQuestion, FaComments, FaPaperPlane, FaPlus, FaPen, FaTrash, FaCog } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { api } from '../api';
import { getAllApiKeys, getDefaultModel } from '../api/user';

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
}

// New interface for custom agent definition
interface CustomAgent {
  id: string;
  name: string;
  type: 'assistant' | 'researcher' | 'coder' | 'critic' | 'custom';
  systemMessage: string;
  isEnabled: boolean;
}

interface ChatForm {
  message: string;
  model_id: string;
  agents: CustomAgent[]; // Add agents array to the chat form
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
  const [customAgents, setCustomAgents] = useState<CustomAgent[]>([
    {
      id: '1',
      name: 'Assistant',
      type: 'assistant',
      systemMessage: 'You are a helpful AI assistant that provides accurate, concise information. Respond to the user\'s queries in a friendly and informative manner.',
      isEnabled: true
    }
  ]);
  const [currentAgent, setCurrentAgent] = useState<CustomAgent | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  
  // Update the chat form to include agents
  const [chatForm, setChatForm] = useState<ChatForm>({
    message: '',
    model_id: '',
    agents: customAgents
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
        const response = await api.get('/api/v1/autogen/status');
        // Check if status is operational or available
        setIsAvailable(response.data.status === 'operational' || response.data.status === 'available');
        
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
    setCurrentAgent({...agent});
    onOpen();
  };

  const handleDeleteAgent = (agentId: string) => {
    const updatedAgents = customAgents.filter(agent => agent.id !== agentId);
    setCustomAgents(updatedAgents);
    setChatForm(prev => ({...prev, agents: updatedAgents}));
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

  const handleSaveAgent = () => {
    if (!currentAgent || !currentAgent.name || !currentAgent.systemMessage) {
      toast({
        title: 'Validation Error',
        description: t('agenticAI.chat.validationError'),
        status: 'error',
        duration: 3000,
      });
      return;
    }

    let updatedAgents;
    if (isEditing) {
      updatedAgents = customAgents.map(agent => 
        agent.id === currentAgent.id ? currentAgent : agent
      );
    } else {
      updatedAgents = [...customAgents, currentAgent];
    }
    
    setCustomAgents(updatedAgents);
    setChatForm(prev => ({...prev, agents: updatedAgents}));
    onClose();
  };

  // Chat handlers
  const handleChatChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setChatForm(prev => ({ ...prev, [name]: value }));
  };

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatForm.message.trim()) return;
    
    // Add user message to chat
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: chatForm.message,
      timestamp: new Date()
    };
    
    setChatMessages(prev => [...prev, userMessage]);
    setChatForm(prev => ({ ...prev, message: '' }));
    setChatLoading(true);
    
    try {
      // Get enabled agents
      const enabledAgents = chatForm.agents.filter(agent => agent.isEnabled);
      
      if (enabledAgents.length === 0) {
        throw new Error(t('agenticAI.chat.noAgentsEnabled'));
      }
      
      // Call the agentic AI endpoint with agents configuration - Each call is a single message exchange
      const response = await api.post('/api/v1/autogen/chat', {
        message: userMessage.content,
        model_id: chatForm.model_id,
        // Only send relevant history to avoid confusing the model with system messages
        history: chatMessages
          .filter(m => m.role !== 'system' && m.content.trim() !== '') // Skip empty messages
          .slice(-6) // Only include the most recent messages
          .map(m => ({
            role: m.role,
            content: m.content,
            name: m.agentName
          })),
        agents: enabledAgents.map(agent => ({
          name: agent.name,
          type: agent.type,
          system_message: agent.systemMessage
        })),
        max_rounds: 1 // Only one round of conversation per API call
      });
      
      // Process the response
      if (response.data.messages && Array.isArray(response.data.messages)) {
        // If we get multiple messages (from different agents)
        if (response.data.messages.length > 0) {
          response.data.messages.forEach((msg: any, index: number) => {
            if (msg.content?.trim()) { // Only add non-empty messages
              const agentMsg: ChatMessage = {
                id: `${Date.now()}-${index}`,
                role: 'assistant',
                content: msg.content,
                timestamp: new Date(),
                agentName: msg.name || 'Assistant'
              };
              setChatMessages(prev => [...prev, agentMsg]);
            }
          });
        } else {
          // Add a default message if no messages were returned
          const defaultMsg: ChatMessage = {
            id: Date.now().toString(),
            role: 'assistant',
            content: "I've processed your request but don't have a specific response.",
            timestamp: new Date(),
            agentName: 'Assistant'
          };
          setChatMessages(prev => [...prev, defaultMsg]);
        }
      } else {
        // Simple response
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.data.response || response.data.message || "I've processed your request.",
          timestamp: new Date(),
          agentName: 'Assistant'
        };
        setChatMessages(prev => [...prev, assistantMessage]);
      }
    } catch (error) {
      // Add error message to chat
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: t('agenticAI.chat.errorMessage'),
        timestamp: new Date(),
        agentName: 'System'
      };
      setChatMessages(prev => [...prev, errorMessage]);
      
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'An error occurred',
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
      const response = await api.post('/api/v1/autogen/research', researchForm);
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
      const response = await api.post('/api/v1/autogen/code-generation', codeGenForm);
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
      
      const response = await api.post('/api/v1/autogen/qa', {
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
                  <Heading size="md">{t('agenticAI.chat.title')}</Heading>
                  <HStack>
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
                <Flex mt={2} wrap="wrap" gap={2}>
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
                        name={agent.name}
                      />
                      {agent.name}
                      <IconButton
                        aria-label="Edit agent"
                        icon={<FaPen />}
                        size="xs"
                        ml={1}
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditAgent(agent);
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
                          bg={msg.role === 'system' ? 'gray.500' : 'blue.500'}
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
                            {msg.agentName}
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
                    <Input
                      name="message"
                      value={chatForm.message}
                      onChange={handleChatChange}
                      placeholder={t('agenticAI.chat.placeholder')}
                      pr="4.5rem"
                      disabled={chatLoading}
                    />
                    <InputRightElement width="4.5rem">
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
                          handleDeleteAgent(currentAgent.id);
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