import React, { useState, useEffect, useCallback } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Select,
  Checkbox,
  VStack,
  useToast,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  Divider,
  Heading,
  Box,
  Text as ChakraText
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { getTokenById, updateToken, Token, TokenUpdate, AccessRule } from '../../api/token';
import RuleInput from './RuleInput';
import RuleDisplay from './RuleDisplay';

const SENSITIVITY_LEVELS = ['low', 'medium', 'high', 'critical'];

interface EditTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenUpdated: () => void;
  tokenId: string | null;
}

const EditTokenModal: React.FC<EditTokenModalProps> = ({ isOpen, onClose, onTokenUpdated, tokenId }) => {
  const { t } = useTranslation();
  const toast = useToast();

  // State for form fields
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]);
  const [expiry, setExpiry] = useState<string | null>(null);
  const [isEditable, setIsEditable] = useState(true);
  const [tokenValue, setTokenValue] = useState('');
  const [isActive, setIsActive] = useState(true);

  // --- Rule State ---
  const [allowRules, setAllowRules] = useState<AccessRule[]>([]);
  const [denyRules, setDenyRules] = useState<AccessRule[]>([]);

  // State for loading/error handling
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- Rule Handlers (Identical to Create Modal) ---
  const handleAddRule = (rule: AccessRule, ruleType: 'allow' | 'deny') => {
    if (ruleType === 'allow') {
      if (allowRules.some(existingRule => existingRule.field === rule.field)) {
        toast({ title: t('tokenModal.rules.duplicateFieldTitle'), description: t('tokenModal.rules.duplicateFieldDescAllow', { field: rule.field }), status: 'warning', duration: 4000, isClosable: true });
        return;
      }
      setAllowRules(prev => [...prev, rule]);
    } else {
      if (denyRules.some(existingRule => existingRule.field === rule.field)) {
        toast({ title: t('tokenModal.rules.duplicateFieldTitle'), description: t('tokenModal.rules.duplicateFieldDescDeny', { field: rule.field }), status: 'warning', duration: 4000, isClosable: true });
        return;
      }
      setDenyRules(prev => [...prev, rule]);
    }
  };

  const handleRemoveAllowRule = (indexToRemove: number) => {
    setAllowRules(prev => prev.filter((_, index) => index !== indexToRemove));
  };

  const handleRemoveDenyRule = (indexToRemove: number) => {
    setDenyRules(prev => prev.filter((_, index) => index !== indexToRemove));
  };

  // Fetch token details when modal opens or tokenId changes
  const fetchTokenDetails = useCallback(async () => {
    if (!tokenId) return;
    setIsFetching(true);
    setError(null);
    try {
      const tokenDetails = await getTokenById(tokenId);
      setName(tokenDetails.name);
      setDescription(tokenDetails.description || '');
      setSensitivity(tokenDetails.sensitivity);
      // Format expiry for datetime-local input (needs YYYY-MM-DDTHH:mm)
      setExpiry(tokenDetails.expiry ? tokenDetails.expiry.slice(0, 16) : null);
      setIsEditable(tokenDetails.is_editable);
      setTokenValue(tokenDetails.token_value);
      setIsActive(tokenDetails.is_active);
      // Initialize rules state
      setAllowRules(tokenDetails.allow_rules || []);
      setDenyRules(tokenDetails.deny_rules || []);
    } catch (err: any) {
      console.error("Failed to fetch token details:", err);
      setError(t('tokenModal.errors.fetchFailed', 'Failed to load token details.'));
    } finally {
      setIsFetching(false);
    }
  }, [tokenId, t]);

  useEffect(() => {
    if (isOpen && tokenId) {
      fetchTokenDetails();
    } else if (!isOpen) {
      // Reset state when modal closes
      setName('');
      setDescription('');
      setSensitivity(SENSITIVITY_LEVELS[0]);
      setExpiry(null);
      setIsEditable(true);
      setTokenValue('');
      setIsActive(true);
      setAllowRules([]);
      setDenyRules([]);
      setError(null);
      setIsLoading(false);
      setIsFetching(false);
    }
  }, [isOpen, tokenId, fetchTokenDetails]);

  const handleSubmit = async () => {
    if (!tokenId) return;
    if (!name) {
       toast({ title: t('common.error'), description: t('tokenModal.validations.nameRequired'), status: 'error', duration: 3000, isClosable: true });
       return;
    }

    setIsLoading(true);
    const tokenData: TokenUpdate = {
      name,
      description: description || null,
      sensitivity,
      // Ensure expiry is null if empty string, otherwise format if needed (though backend expects ISO string)
      expiry: expiry || null,
      is_editable: isEditable,
      allow_rules: allowRules, // Include rules from state
      deny_rules: denyRules,   // Include rules from state
    };

    try {
      await updateToken(tokenId, tokenData);
      toast({
        title: t('tokenModal.updateSuccessTitle', 'Token Updated'),
        description: t('tokenModal.updateSuccessDesc', `Token "${name}" was successfully updated.`),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      onTokenUpdated(); // Refresh list in parent
      onClose(); // Close modal
    } catch (error: any) {
      console.error("Failed to update token:", error);
      toast({
        title: t('common.error', 'Error'),
        description: error.message || t('tokenModal.errors.updateFailed', 'Failed to update token. Please try again.'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsLoading(false); // Keep modal open on error
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{t('tokenModal.editTitle', 'Edit API Token')}</ModalHeader>
        <ModalCloseButton isDisabled={isLoading || isFetching} />
        <ModalBody pb={6}>
          {isFetching ? (
            <Center h="300px">
              <Spinner size="xl" />
            </Center>
          ) : error ? (
            <Alert status="error">
              <AlertIcon />
              {error}
            </Alert>
          ) : (
            <VStack spacing={4} align="stretch">
              {/* --- Basic Info --- */}
              <FormControl isRequired>
                <FormLabel>{t('tokenModal.nameLabel', 'Name')}</FormLabel>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </FormControl>
              <FormControl>
                <FormLabel>{t('tokenModal.descriptionLabel', 'Description')}</FormLabel>
                <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
              </FormControl>
              <FormControl>
                 <FormLabel>{t('tokenModal.tokenValueLabel', 'Token Value')}</FormLabel>
                 <Input isReadOnly value={tokenValue} fontFamily="monospace" />
                 <ChakraText fontSize="xs">{t('tokenModal.tokenValueNote', 'This value is only shown once upon creation.')}</ChakraText>
              </FormControl>
              <FormControl>
                <FormLabel>{t('tokenModal.sensitivityLabel', 'Sensitivity Level')}</FormLabel>
                <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}>
                  {SENSITIVITY_LEVELS.map(level => (
                    <option key={level} value={level}>{t(`tokenModal.sensitivityLevels.${level}`, level.charAt(0).toUpperCase() + level.slice(1))}</option>
                  ))}
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>{t('tokenModal.expiryLabel', 'Expiry Date (Optional)')}</FormLabel>
                <Input 
                  type="datetime-local" 
                  // Handle null expiry by passing empty string to input
                  value={expiry ?? ''} 
                  onChange={(e) => setExpiry(e.target.value || null)} // Set to null if cleared
                />
              </FormControl>
               <FormControl>
                 <Checkbox 
                   isChecked={isEditable} 
                   onChange={(e) => setIsEditable(e.target.checked)}
                 >
                   {t('tokenModal.editableLabel', 'Allow Editing Rules Later')}
                 </Checkbox>
                 {!isActive && (
                    <ChakraText fontSize="sm" color="orange.500" mt={1}>({t('tokenModal.inactiveNote', 'Token is currently inactive due to expiry.')})</ChakraText>
                 )}
               </FormControl>

              {/* --- Access Rules Section --- */}
              <Divider my={4} />
              <Heading size="md">{t('tokenModal.rules.title', 'Access Rules')}</Heading>
              <RuleInput onAddRule={handleAddRule} /> 

              {/* Display Allow Rules */}
              {allowRules.length > 0 && (
                  <VStack spacing={2} align="stretch" mt={4}>
                      <Heading size="sm" colorScheme="green">{t('tokenModal.rules.allowTitle', 'Allow Rules')}</Heading>
                      {allowRules.map((rule, index) => (
                          <RuleDisplay 
                              key={`allow-${rule.field}-${index}`}
                              rule={rule} 
                              ruleType="allow" 
                              onRemove={() => handleRemoveAllowRule(index)} 
                          />
                      ))}
                  </VStack>
              )}

              {/* Display Deny Rules */}
              {denyRules.length > 0 && (
                  <VStack spacing={2} align="stretch" mt={4}>
                      <Heading size="sm" colorScheme="red">{t('tokenModal.rules.denyTitle', 'Deny Rules')}</Heading>
                      {denyRules.map((rule, index) => (
                          <RuleDisplay 
                              key={`deny-${rule.field}-${index}`}
                              rule={rule} 
                              ruleType="deny" 
                              onRemove={() => handleRemoveDenyRule(index)} 
                          />
                      ))}
                  </VStack>
              )}
              
              {/* Add spacing if needed */}
              {(allowRules.length > 0 || denyRules.length > 0) && <Box h={4} />} 

            </VStack>
          )}
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose} isDisabled={isLoading || isFetching}>
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button 
            colorScheme="blue" 
            onClick={handleSubmit} 
            isLoading={isLoading}
            isDisabled={isFetching || error !== null}
            loadingText={t('common.saving', 'Saving...')}
          >
            {t('tokenModal.updateButton', 'Update Token')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default EditTokenModal; 