import React from 'react';
import {
  Box,
  Badge,
  Text,
  Flex,
  IconButton,
  CloseButton
} from '@chakra-ui/react';
import { CloseIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';

interface RuleDisplayProps {
  rule: string;
  ruleType: 'allow' | 'deny';
  onRemove: () => void;
}

const RuleDisplay: React.FC<RuleDisplayProps> = ({ rule, ruleType, onRemove }) => {
  const { t } = useTranslation();
  const isAllow = ruleType === 'allow';

  return (
    <Flex 
      justifyContent="space-between" 
      alignItems="center" 
      bg={isAllow ? 'green.50' : 'red.50'}
      p={2} 
      borderRadius="md" 
      borderWidth={1} 
      borderColor={isAllow ? 'green.200' : 'red.200'}
    >
      <Badge colorScheme={isAllow ? 'green' : 'red'} mr={2} flexShrink={0}>
        {isAllow ? t('tokenModal.rules.allow', 'ALLOW') : t('tokenModal.rules.deny', 'DENY')}
      </Badge>
      <Text fontSize="sm" fontFamily="monospace" mr={2} flexGrow={1} noOfLines={1} title={rule}> 
        {formatRuleString(rule)}
      </Text>
      <CloseButton size="sm" onClick={onRemove} aria-label={t('common.remove', 'Remove')}/>
    </Flex>
  );
};

// Helper function to format the rule string
const formatRuleString = (rule: string): string => {
  const parts = rule.split(':');
  if (parts.length === 2) {
    const field = parts[0].trim();
    const value: string = parts[1].trim(); // Explicitly type value
    const formattedField = field.charAt(0).toUpperCase() + field.slice(1);
    return `${formattedField}: ${value}`;
  }
  return rule; // Return original string if format is unexpected
};

export default RuleDisplay; 