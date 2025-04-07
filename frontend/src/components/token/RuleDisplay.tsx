import React from 'react';
import {
  Box,
  Text,
  Tag,
  TagLabel,
  TagCloseButton,
  Wrap,
  WrapItem,
  HStack,
  IconButton,
  Tooltip
} from '@chakra-ui/react';
import { CloseIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';
import { AccessRule } from '../../api/token';

interface RuleDisplayProps {
  rule: AccessRule;
  ruleType: 'allow' | 'deny';
  onRemove: () => void; // Callback to remove this specific rule
}

const RuleDisplay: React.FC<RuleDisplayProps> = ({ rule, ruleType, onRemove }) => {
  const { t } = useTranslation();
  const tagColorScheme = ruleType === 'allow' ? 'green' : 'red';

  return (
    <Box borderWidth="1px" borderRadius="md" p={3} w="100%">
      <HStack justify="space-between" align="center">
        <Box flex="1">
          <Text fontWeight="bold" display="inline">
            {t(`tokenModal.rules.${ruleType}Prefix`, ruleType === 'allow' ? 'ALLOW' : 'DENY')} {`: `}
          </Text>
           <Text display="inline">{`${rule.field} is `}</Text>
            {rule.values.length === 1 ? (
                 <Tag size="sm" variant='solid' colorScheme={tagColorScheme}>{rule.values[0]}</Tag>
            ) : (
                 <Text display="inline">one of:</Text>
            )}
          {rule.values.length > 1 && (
             <Wrap spacing={1} mt={1} display="inline-block" verticalAlign="middle">
                {rule.values.map((value) => (
                    <WrapItem key={value}>
                        <Tag size="sm" variant='solid' colorScheme={tagColorScheme}>
                           <TagLabel>{value}</TagLabel>
                        </Tag>
                    </WrapItem>
                ))}
            </Wrap>
          )}
        </Box>
         <Tooltip label={t('tokenModal.rules.removeRuleTooltip', 'Remove this rule')} placement="top">
            <IconButton
                aria-label={t('tokenModal.rules.removeRuleAriaLabel', 'Remove rule')}
                icon={<CloseIcon />}
                size="xs"
                variant="ghost"
                colorScheme="red"
                onClick={onRemove}
            />
        </Tooltip>
      </HStack>
    </Box>
  );
};

export default RuleDisplay; 