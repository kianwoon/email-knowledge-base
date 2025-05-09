import React from 'react';
import {
  Box,
  Heading,
  Text,
  UnorderedList,
  ListItem,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Code,
  useColorModeValue,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';

const MCPToolsHelp: React.FC = () => {
  const { t } = useTranslation();
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const codeColor = useColorModeValue('blue.700', 'blue.200');

  return (
    <Box borderWidth="1px" borderRadius="lg" p={4} borderColor={borderColor} bg={bgColor}>
      <Heading size="md" mb={3}>{t('mcpTools.understanding', 'Understanding MCP Tools')}</Heading>
      <Text mb={4}>
        {t('mcpTools.description', 'MCP Tools allow you to create custom interactions between the AI and your systems. When you define a tool, you\'re creating a pattern that the AI can recognize and use to take specific actions.')}
      </Text>

      <Accordion allowToggle>
        <AccordionItem border="none">
          <h2>
            <AccordionButton>
              <Box flex="1" textAlign="left" fontWeight="bold">
                {t('mcpTools.howTheyWork', 'How MCP Tools Work')}
              </Box>
              <AccordionIcon />
            </AccordionButton>
          </h2>
          <AccordionPanel pb={4}>
            <Text mb={3}>
              {t('mcpTools.aiRequest', 'When the AI receives a request that matches a tool\'s functionality, it can:')}
            </Text>
            <UnorderedList spacing={2} mb={3}>
              <ListItem>{t('mcpTools.recognizeIntent', 'Recognize the intent to use the tool')}</ListItem>
              <ListItem>{t('mcpTools.extractParameters', 'Extract the necessary parameters from the conversation')}</ListItem>
              <ListItem>{t('mcpTools.callEndpoint', 'Call your defined endpoint or function with those parameters')}</ListItem>
              <ListItem>{t('mcpTools.incorporateResults', 'Incorporate the results into its response')}</ListItem>
            </UnorderedList>
            <Text>
              {t('mcpTools.allowsActions', 'This allows the AI to perform concrete actions like creating tickets, querying databases, or interacting with external systems.')}
            </Text>
          </AccordionPanel>
        </AccordionItem>

        <AccordionItem border="none">
          <h2>
            <AccordionButton>
              <Box flex="1" textAlign="left" fontWeight="bold">
                {t('mcpTools.jsonSchema', 'JSON Schema for Parameters')}
              </Box>
              <AccordionIcon />
            </AccordionButton>
          </h2>
          <AccordionPanel pb={4}>
            <Text mb={3}>
              {t('mcpTools.parametersField', 'The parameters field uses JSON Schema to define what arguments the tool accepts. This helps the AI understand what information it needs to collect.')}
            </Text>
            <Text mb={3}>
              {t('mcpTools.basicSchema', 'A basic schema might look like:')}
            </Text>
            <Code
              display="block"
              whiteSpace="pre"
              p={3}
              borderRadius="md"
              fontFamily="monospace"
              mb={3}
              color={codeColor}
            >
{`{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query"
    },
    "max_results": {
      "type": "number",
      "description": "Maximum number of results"
    }
  },
  "required": ["query"]
}`}
            </Code>
            <Text>
              {t('mcpTools.schemaExplanation', 'This schema tells the AI that it needs to collect a required "query" string and an optional "max_results" number.')}
            </Text>
          </AccordionPanel>
        </AccordionItem>

        <AccordionItem border="none">
          <h2>
            <AccordionButton>
              <Box flex="1" textAlign="left" fontWeight="bold">
                {t('mcpTools.exampleTools', 'Example Tools')}
              </Box>
              <AccordionIcon />
            </AccordionButton>
          </h2>
          <AccordionPanel pb={4}>
            <Text fontWeight="bold" mb={2}>{t('mcpTools.example1', 'Example 1: JIRA Issue Creator')}</Text>
            <UnorderedList spacing={1} mb={3}>
              <ListItem><strong>{t('mcpTools.name', 'Name')}:</strong> jira.create_issue</ListItem>
              <ListItem><strong>{t('mcpTools.description', 'Description')}:</strong> {t('mcpTools.jiraDescription', 'Creates a new JIRA issue')}</ListItem>
              <ListItem><strong>{t('mcpTools.endpoint', 'Endpoint')}:</strong> /api/v1/jira/create-issue</ListItem>
              <ListItem><strong>{t('mcpTools.parameters', 'Parameters')}:</strong></ListItem>
            </UnorderedList>
            <Code
              display="block"
              whiteSpace="pre"
              p={3}
              borderRadius="md"
              fontFamily="monospace"
              mb={4}
              color={codeColor}
              fontSize="xs"
            >
{`{
  "type": "object",
  "properties": {
    "summary": {
      "type": "string",
      "description": "Issue summary/title"
    },
    "description": {
      "type": "string",
      "description": "Detailed description of the issue"
    },
    "issue_type": {
      "type": "string",
      "description": "Type of issue",
      "enum": ["Bug", "Task", "Story"]
    },
    "priority": {
      "type": "string",
      "description": "Issue priority",
      "enum": ["High", "Medium", "Low"]
    }
  },
  "required": ["summary", "description", "issue_type"]
}`}
            </Code>

            <Text fontWeight="bold" mb={2}>{t('mcpTools.example2', 'Example 2: Weather API')}</Text>
            <UnorderedList spacing={1} mb={3}>
              <ListItem><strong>{t('mcpTools.name', 'Name')}:</strong> weather.get_forecast</ListItem>
              <ListItem><strong>{t('mcpTools.description', 'Description')}:</strong> {t('mcpTools.weatherDescription', 'Gets weather forecast for a location')}</ListItem>
              <ListItem><strong>{t('mcpTools.endpoint', 'Endpoint')}:</strong> /api/v1/weather/forecast</ListItem>
              <ListItem><strong>{t('mcpTools.parameters', 'Parameters')}:</strong></ListItem>
            </UnorderedList>
            <Code
              display="block"
              whiteSpace="pre"
              p={3}
              borderRadius="md"
              fontFamily="monospace"
              mb={3}
              color={codeColor}
              fontSize="xs"
            >
{`{
  "type": "object",
  "properties": {
    "location": {
      "type": "string",
      "description": "City name or address"
    },
    "days": {
      "type": "integer",
      "description": "Number of days to forecast",
      "minimum": 1,
      "maximum": 7
    },
    "units": {
      "type": "string",
      "description": "Temperature units",
      "enum": ["celsius", "fahrenheit"],
      "default": "celsius"
    }
  },
  "required": ["location"]
}`}
            </Code>
          </AccordionPanel>
        </AccordionItem>
      </Accordion>
    </Box>
  );
};

export default MCPToolsHelp; 