import React, { useState, useEffect } from 'react';
import {
  Box,
  Textarea,
  FormControl,
  FormLabel,
  FormErrorMessage,
  useColorModeValue,
  Button,
  HStack,
  Alert,
  AlertIcon,
} from '@chakra-ui/react';

interface JSONSchemaEditorProps {
  value: Record<string, any>;
  onChange: (value: Record<string, any>) => void;
  label?: string;
  isRequired?: boolean;
  isDisabled?: boolean;
  formatButtonText?: string;
  loadExampleButtonText?: string;
  helpText?: string;
}

const JSONSchemaEditor: React.FC<JSONSchemaEditorProps> = ({
  value,
  onChange,
  label = 'Parameters Schema',
  isRequired = false,
  isDisabled = false,
  formatButtonText = 'Format JSON',
  loadExampleButtonText = 'Load Example',
  helpText = 'This should be a valid JSON Schema for the tool parameters.'
}) => {
  const [jsonText, setJsonText] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  // Convert object to formatted JSON string
  useEffect(() => {
    try {
      setJsonText(JSON.stringify(value, null, 2));
      setError(null);
    } catch (err) {
      setError('Invalid JSON object provided');
    }
  }, [value]);

  // Update parent component when JSON changes and is valid
  const handleJsonChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value;
    setJsonText(newText);
    
    try {
      const parsed = JSON.parse(newText);
      setError(null);
      onChange(parsed);
    } catch (err) {
      setError('Invalid JSON: Please check your syntax');
      // Don't update parent with invalid JSON
    }
  };

  // Format the JSON nicely
  const formatJson = () => {
    try {
      const parsed = JSON.parse(jsonText);
      setJsonText(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch (err) {
      setError('Cannot format invalid JSON');
    }
  };

  // Set example schema
  const setExampleSchema = () => {
    const example = {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Search query string"
        },
        "max_results": {
          "type": "number",
          "description": "Maximum number of results to return"
        }
      },
      "required": ["query"]
    };
    
    setJsonText(JSON.stringify(example, null, 2));
    onChange(example);
    setError(null);
  };

  const bgColor = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  return (
    <FormControl isInvalid={!!error} isRequired={isRequired}>
      <FormLabel>{label}</FormLabel>
      <Textarea
        value={jsonText}
        onChange={handleJsonChange}
        placeholder='{"type": "object", "properties": {...}}'
        fontFamily="monospace"
        fontSize="sm"
        rows={10}
        resize="vertical"
        bg={bgColor}
        borderColor={borderColor}
        isDisabled={isDisabled}
      />
      {error && <FormErrorMessage>{error}</FormErrorMessage>}
      <HStack mt={2} spacing={2} justifyContent="flex-end">
        <Button 
          size="sm" 
          onClick={formatJson} 
          isDisabled={isDisabled || !!error}
        >
          {formatButtonText}
        </Button>
        <Button 
          size="sm" 
          onClick={setExampleSchema} 
          variant="outline" 
          isDisabled={isDisabled}
        >
          {loadExampleButtonText}
        </Button>
      </HStack>
      {!error && (
        <Alert status="info" mt={2} size="sm" borderRadius="md">
          <AlertIcon />
          {helpText}
        </Alert>
      )}
    </FormControl>
  );
};

export default JSONSchemaEditor; 