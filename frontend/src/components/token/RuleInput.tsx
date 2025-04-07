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
import { AccessRule } from '../../api/token'; // Import the type

// Define allowed fields for rules
const ALLOWED_RULE_FIELDS = ['tags', 'source_id']; // Extend this list as needed

interface RuleInputProps {
  onAddRule: (rule: AccessRule, ruleType: 'allow' | 'deny') => void;
}

const RuleInput: React.FC<RuleInputProps> = ({ onAddRule }) => {
  const { t } = useTranslation();
  const [field, setField] = useState<string>(ALLOWED_RULE_FIELDS[0]);
  const [currentValue, setCurrentValue] = useState<string>('');
  const [values, setValues] = useState<string[]>([]);
  const toast = useToast();

  const handleAddValue = () => {
    if (currentValue.trim() && !values.includes(currentValue.trim())) {
      setValues([...values, currentValue.trim()]);
      setCurrentValue('');
    }
  };

  const handleRemoveValue = (valueToRemove: string) => {
    setValues(values.filter(value => value !== valueToRemove));
  };

  const handleAddRuleClick = (ruleType: 'allow' | 'deny') => {
    if (!field || values.length === 0) {
      toast({
        title: t('tokenModal.rules.errorTitle', 'Incomplete Rule'),
        description: t('tokenModal.rules.errorDescription', 'Please select a field and add at least one value.'),
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }
    onAddRule({ field, values }, ruleType);
    // Reset form after adding
    setField(ALLOWED_RULE_FIELDS[0]);
    setValues([]);
    setCurrentValue('');
  };

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault(); // Prevent form submission if inside a form
      handleAddValue();
    }
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
            value={currentValue}
            onChange={(e) => setCurrentValue(e.target.value)}
            onKeyDown={handleInputKeyDown}
          />
          <Button onClick={handleAddValue} size="sm">
            {t('common.add', 'Add')}
          </Button>
        </HStack>
        {values.length > 0 && (
          <Wrap spacing={2} mt={2}>
            {values.map((value) => (
              <WrapItem key={value}>
                <Tag size="md" borderRadius="full" variant="solid" colorScheme="blue">
                  <TagLabel>{value}</TagLabel>
                  <TagCloseButton onClick={() => handleRemoveValue(value)} />
                </Tag>
              </WrapItem>
            ))}
          </Wrap>
        )}
      </FormControl>

      <HStack justify="flex-end" spacing={3}>
         <Button onClick={() => handleAddRuleClick('allow')} colorScheme="green" size="sm">
            {t('tokenModal.rules.addAllow', 'Add Allow Rule')}
         </Button>
         <Button onClick={() => handleAddRuleClick('deny')} colorScheme="red" size="sm">
             {t('tokenModal.rules.addDeny', 'Add Deny Rule')}
         </Button>
      </HStack>
    </VStack>
  );
};

export default RuleInput; 