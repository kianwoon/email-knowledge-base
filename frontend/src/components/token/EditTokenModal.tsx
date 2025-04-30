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
  Text as ChakraText,
  InputGroup,
  FormHelperText
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { getTokenById, updateToken, Token, TokenUpdatePayload } from '../../api/token';
import RuleInput from './RuleInput';
import RuleDisplay from './RuleDisplay';
import { CopyIcon } from '@chakra-ui/icons';

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
  const [expiry, setExpiry] = useState<string>('');
  const [isActive, setIsActive] = useState(true);

  // --- Rule State ---
  const [allowRules, setAllowRules] = useState<string[]>([]);
  const [denyRules, setDenyRules] = useState<string[]>([]);

  // State for loading/error handling
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- ADD BACK Rule Handlers ---
  const handleAddRule = (rule: string, ruleType: 'allow' | 'deny') => {
    if (ruleType === 'allow') {
      if (allowRules.some(existingRule => existingRule === rule)) {
        toast({
          title: t('tokenModal.rules.duplicateFieldTitle', 'Duplicate Field'),
          description: t('tokenModal.rules.duplicateFieldDescAllow', `An allow rule for the field '${rule}' already exists. Remove the existing rule first to change values.`),
          status: 'warning', duration: 4000, isClosable: true,
        });
        return;
      }
      setAllowRules(prev => [...prev, rule]);
    } else {
      if (denyRules.some(existingRule => existingRule === rule)) {
        toast({
          title: t('tokenModal.rules.duplicateFieldTitle', 'Duplicate Field'),
          description: t('tokenModal.rules.duplicateFieldDescDeny', `A deny rule for the field '${rule}' already exists. Remove the existing rule first to change values.`),
          status: 'warning', duration: 4000, isClosable: true,
        });
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
  // --- END ADD BACK Rule Handlers ---

  // Fetch token details when modal opens or tokenId changes
  const fetchTokenDetails = useCallback(async () => {
    if (!tokenId) return;
    setIsFetching(true);
    setError(null);
    try {
      const tokenDetails = await getTokenById(tokenId);
      setName(tokenDetails.name);
      setDescription(tokenDetails.description || '');
      setSensitivity(tokenDetails.sensitivity || SENSITIVITY_LEVELS[0]);
      setExpiry(tokenDetails.expiry ? new Date(tokenDetails.expiry).toISOString().slice(0, 16) : '');
      setIsActive(tokenDetails.is_active);
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
      setExpiry('');
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
    const payload: TokenUpdatePayload = {
      name,
      description,
      sensitivity,
      allow_rules: allowRules,
      deny_rules: denyRules,
      expiry: expiry || null,
      is_active: isActive,
    };

    try {
      await updateToken(tokenId, payload);
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
                <InputGroup>
                  <Input isReadOnly value={tokenId ? `${tokenId}...` : 'N/A'} fontFamily="monospace" />
                </InputGroup>
                <FormHelperText>{t('tokenModal.tokenValueHelper', 'Token preview shown. The full value is only available on creation.')}</FormHelperText>
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
                  value={expiry}
                  onChange={(e) => setExpiry(e.target.value)}
                />
              </FormControl>
              <FormControl>
                <Checkbox 
                  isChecked={isActive} 
                  onChange={(e) => setIsActive(e.target.checked)}
                >
                  {t('tokenModal.inactiveNote', 'Token is currently inactive due to expiry.')}
                </Checkbox>
              </FormControl>

              {/* --- Access Rules Section --- */}
              <Divider my={4} />
              <Heading size="md">{t('tokenModal.rules.title', 'Access Rules')}</Heading>
              <RuleInput onAddRule={(rule) => handleAddRule(rule, 'allow')} /> 

              {/* Display Allow Rules */}
              {allowRules.length > 0 && (
                  <VStack spacing={2} align="stretch" mt={4}>
                      <Heading size="sm" colorScheme="green">{t('tokenModal.rules.allowTitle', 'Allow Rules')}</Heading>
                      {allowRules.map((rule, index) => (
                          <RuleDisplay 
                              key={`${rule}-${index}`}
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
                              key={`${rule}-${index}`}
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
            {t('common.save', 'Save Changes')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default EditTokenModal; 