import React, { useState, useMemo } from 'react';
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
  Avatar,
  Flex,
  useColorModeValue,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FaRobot, FaUser } from 'react-icons/fa';

// Types for LLM models
interface LLMModel {
  id: string;
  name: string;
  provider: string;
  requiresKey: boolean;
}

// Expanded list of models
const AVAILABLE_MODELS: LLMModel[] = [
  { id: 'gpt-4', name: 'GPT-4', provider: 'OpenAI', requiresKey: true },
  { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', provider: 'OpenAI', requiresKey: true },
  { id: 'claude-3-opus', name: 'Claude 3 Opus', provider: 'Anthropic', requiresKey: true },
  { id: 'claude-3-sonnet', name: 'Claude 3 Sonnet', provider: 'Anthropic', requiresKey: true },
  { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'Google', requiresKey: true },
  { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', provider: 'Google', requiresKey: true },
  { id: 'llama3-70b', name: 'Llama 3 70B', provider: 'Meta', requiresKey: true },
  { id: 'llama3-8b', name: 'Llama 3 8B', provider: 'Meta', requiresKey: true },
  { id: 'mistral-large', name: 'Mistral Large', provider: 'Mistral', requiresKey: true },
  { id: 'mixtral-8x7b', name: 'Mixtral 8x7B', provider: 'Mistral', requiresKey: true },
  { id: 'deepseek-chat', name: 'Deepseek Chat', provider: 'Deepseek', requiresKey: true },
];

const JarvisPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const userBg = useColorModeValue('blue.50', 'blue.900');
  const assistantBg = useColorModeValue('gray.100', 'gray.700');

  // State for model selection and API keys
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<Array<{ role: 'user' | 'assistant', content: string }>>([]);

  // Get unique providers from the models list
  const uniqueProviders = useMemo(() => {
    const providers = new Set<string>();
    AVAILABLE_MODELS.forEach(model => {
      if (model.requiresKey) { // Only add providers that require a key
        providers.add(model.provider);
      }
    });
    return Array.from(providers);
  }, []); // Re-calculate only if AVAILABLE_MODELS changes (it doesn't here, but good practice)

  // Handle API key updates
  const handleApiKeyUpdate = (provider: string, key: string) => {
    setApiKeys(prev => ({
      ...prev,
      [provider]: key
    }));
  };

  // Handle chat submission
  const handleSendMessage = async () => {
    if (!message.trim()) return;

    // Add user message to chat
    const newMessage = { role: 'user' as const, content: message };
    setChatHistory(prev => [...prev, newMessage]);
    setMessage('');

    // TODO: Implement actual API call to selected LLM
    // This is a placeholder response
    setTimeout(() => {
      setChatHistory(prev => [
        ...prev,
        { role: 'assistant', content: t('jarvis.placeholderResponse') }
      ]);
    }, 1000);
  };

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        <Heading>{t('jarvis.title')}</Heading>

        <Tabs isLazy>
          <TabList>
            <Tab>{t('jarvis.chat')}</Tab>
            <Tab>{t('jarvis.settings')}</Tab>
          </TabList>

          <TabPanels>
            <TabPanel>
              {/* Chat Interface - Enhanced */}
              <VStack spacing={4} align="stretch">
                <Box
                  borderWidth={1}
                  borderColor={useColorModeValue('gray.200', 'gray.600')}
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
                        color={useColorModeValue('gray.800', 'whiteAlpha.900')}
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
                  />
                  <Button
                    colorScheme="blue"
                    onClick={handleSendMessage}
                    isDisabled={!selectedModel || !message.trim()}
                    alignSelf="flex-end"
                  >
                    {t('common.send')}
                  </Button>
                </HStack>
              </VStack>
            </TabPanel>

            <TabPanel>
              {/* Settings Interface - Enhanced */}
              <VStack spacing={6} align="stretch">
                <FormControl>
                  <FormLabel>{t('jarvis.settingsContent.selectModel')}</FormLabel>
                  <Select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    placeholder={t('jarvis.settingsContent.selectModelPlaceholder')}
                  >
                    {AVAILABLE_MODELS.map(model => (
                      <option key={model.id} value={model.id}>
                        {model.name} ({model.provider})
                      </option>
                    ))}
                  </Select>
                </FormControl>

                {/* API Key Inputs - Grouped by Provider */}
                {uniqueProviders.map(provider => (
                  <FormControl key={provider}>
                    <FormLabel>
                      {t('jarvis.settingsContent.apiKey', { provider })}
                    </FormLabel>
                    <Input
                      type="password"
                      value={apiKeys[provider] || ''}
                      onChange={(e) => handleApiKeyUpdate(provider, e.target.value)}
                      placeholder={t('jarvis.settingsContent.apiKeyPlaceholder')}
                    />
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