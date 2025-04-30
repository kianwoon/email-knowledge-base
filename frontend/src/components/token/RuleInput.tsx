import React, { useState } from 'react';
import {
  Box,
  FormControl,
  FormLabel,
  Select,
  Input,
  Button,
  HStack,
  Tag,
  TagLabel,
  TagCloseButton,
  Wrap,
  WrapItem,
  useToast,
  VStack
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';

// Define allowed fields for rules
const ALLOWED_RULE_FIELDS = ['tags', 'source_id']; // Extend this list as needed

interface RuleInputProps {
  onAddRule: (rule: string, ruleType: 'allow' | 'deny') => void;
}

const RuleInput: React.FC<RuleInputProps> = ({ onAddRule }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [ruleType, setRuleType] = useState<'allow' | 'deny'>('allow');
  const [field, setField] = useState('');
  const [value, setValue] = useState('');

  const handleAddClick = () => {
    if (!field || !value) {
      toast({
        title: t('tokenModal.rules.errorTitle', 'Incomplete Rule'),
        description: t('tokenModal.rules.errorDescription', 'Please select a field and add a value.'),
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    // Construct the rule string (e.g., "fieldName:fieldValue")
    const ruleString = `${field}:${value}`;
    onAddRule(ruleString, ruleType);

    // Reset fields
    setField('');
    setValue('');
  };

  return (
    <VStack spacing={4} align="stretch">
      <FormControl>
        <FormLabel>{t('tokenModal.rules.fieldLabel', 'Rule Field')}</FormLabel>
        <Select value={field} onChange={(e) => setField(e.target.value)}>
          {ALLOWED_RULE_FIELDS.map((fieldName) => (
            <option key={fieldName} value={fieldName}>
              {fieldName}
            </option>
          ))}
        </Select>
      </FormControl>

      <FormControl>
        <FormLabel>{t('tokenModal.rules.valuesLabel', 'Values (press Enter to add)')}</FormLabel>
        <HStack>
          <Input
            placeholder={t('tokenModal.rules.valuePlaceholder', 'Enter a value')}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <Button onClick={handleAddClick} colorScheme={ruleType === 'allow' ? 'green' : 'red'} size="sm">
            {t('tokenModal.rules.addButton', 'Add Rule')}
          </Button>
        </HStack>
      </FormControl>

      <HStack justify="flex-end" spacing={3}>
        <Button onClick={() => setRuleType('allow')} colorScheme="green" size="sm">
          {t('tokenModal.rules.addAllow', 'Add Allow Rule')}
        </Button>
        <Button onClick={() => setRuleType('deny')} colorScheme="red" size="sm">
          {t('tokenModal.rules.addDeny', 'Add Deny Rule')}
        </Button>
      </HStack>
    </VStack>
  );
};

export default RuleInput; 