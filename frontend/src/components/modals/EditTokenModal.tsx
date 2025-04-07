import React, { useState, useEffect, useRef } from 'react';
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
  FormHelperText,
  Input,
  Textarea,
  Select,
  Checkbox,
  VStack,
  useToast,
  Spinner,
  Center,
  Text as ChakraText,
  CircularProgress,
  Alert,
  AlertIcon,
  Divider,
  IconButton,
  HStack,
  Switch,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { TokenUpdate, Token, getTokenById, updateToken, AccessRule } from '../../api/token';
import { FaPlus, FaTrash } from 'react-icons/fa';
import TagInput from '../inputs/TagInput';

interface EditTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenUpdated: () => void;
  tokenId: string | null;
}

const SENSITIVITY_LEVELS = ["public", "internal", "confidential", "strict-confidential"];

const EditTokenModal: React.FC<EditTokenModalProps> = ({ isOpen, onClose, onTokenUpdated, tokenId }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const initialRef = useRef<HTMLInputElement>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]);
  const [expiry, setExpiry] = useState('');
  const [isEditable, setIsEditable] = useState(true);
  const [allowRules, setAllowRules] = useState<AccessRule[]>([]);
  const [denyRules, setDenyRules] = useState<AccessRule[]>([]);
  const [originalIsEditable, setOriginalIsEditable] = useState(true);

  const addRule = (type: 'allow' | 'deny') => {
    const newRule: AccessRule = { field: '', values: [] };
    if (type === 'allow') {
      setAllowRules([...allowRules, newRule]);
    } else {
      setDenyRules([...denyRules, newRule]);
    }
  };

  const updateRule = (index: number, field: keyof AccessRule, value: string | string[], type: 'allow' | 'deny') => {
    const rules = type === 'allow' ? allowRules : denyRules;
    const setRules = type === 'allow' ? setAllowRules : setDenyRules;
    const updatedRules = [...rules];
    updatedRules[index] = { ...updatedRules[index], [field]: value };
    setRules(updatedRules);
  };

  const removeRule = (index: number, type: 'allow' | 'deny') => {
    const rules = type === 'allow' ? allowRules : denyRules;
    const setRules = type === 'allow' ? setAllowRules : setDenyRules;
    setRules(rules.filter((_, i) => i !== index));
  };

  useEffect(() => {
    if (isOpen && tokenId) {
      const fetchToken = async () => {
        setIsFetching(true);
        setError(null);
        try {
          console.log(`EditModal: Fetching data for token ID: ${tokenId}`);
          const tokenData = await getTokenById(tokenId);
          console.log('EditModal: Data received:', tokenData);
          setName(tokenData.name);
          setDescription(tokenData.description || '');
          setSensitivity(tokenData.sensitivity || SENSITIVITY_LEVELS[0]);
          setExpiry(tokenData.expiry ? tokenData.expiry.slice(0, 16) : '');
          setIsEditable(tokenData.is_editable);
          setOriginalIsEditable(tokenData.is_editable);
          setAllowRules(tokenData.allow_rules || []);
          setDenyRules(tokenData.deny_rules || []);
        } catch (err: any) {
          console.error('EditModal: Error fetching token data:', err);
          setError(t('editTokenModal.errors.fetchFailed', 'Failed to load token data. Please try again.'));
        } finally {
          setIsFetching(false);
        }
      };
      fetchToken();
    } else {
      setName('');
      setDescription('');
      setSensitivity(SENSITIVITY_LEVELS[0]);
      setExpiry('');
      setIsEditable(true);
      setOriginalIsEditable(true);
      setAllowRules([]);
      setDenyRules([]);
      setError(null);
      setIsFetching(false);
      setIsLoading(false);
    }
  }, [isOpen, tokenId, t]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!tokenId || !originalIsEditable) {
        toast({
            title: t('editTokenModal.toast.errorTitle', 'Update Failed'),
            description: t('editTokenModal.nonEditableWarning', 'This token is marked as non-editable. Changes will not be saved.'),
            status: 'error',
            duration: 9000,
            isClosable: true,
        });
        return;
    }
    setIsLoading(true);

    const tokenUpdateData: TokenUpdate = {
      name,
      description: description || null,
      sensitivity,
      expiry: expiry ? new Date(expiry).toISOString() : null,
      is_editable: isEditable,
      allow_rules: allowRules.filter(rule => rule.field && rule.values.length > 0),
      deny_rules: denyRules.filter(rule => rule.field && rule.values.length > 0),
    };

    try {
      await updateToken(tokenId, tokenUpdateData);
      toast({
        title: t('editTokenModal.toast.successTitle', 'Token Updated'),
        description: t('editTokenModal.toast.successDescription', `Token "${name}" was successfully updated.`),        
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
      onTokenUpdated();
      onClose();
    } catch (error: any) {
      console.error(`Token update failed for ${tokenId}:`, error);
      toast({
        title: t('editTokenModal.toast.errorTitle', 'Update Failed'),
        description: error?.response?.data?.detail || error.message || t('editTokenModal.toast.errorDescription', 'Could not update token.'),
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} initialFocusRef={initialRef} size="xl">
      <ModalOverlay />
      <ModalContent as="form" onSubmit={handleSubmit}>
        <ModalHeader>{t('editTokenModal.title', 'Edit Token')}</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          {isFetching ? (
            <CircularProgress isIndeterminate color="blue.300" />
          ) : error ? (
            <Alert status="error">
              <AlertIcon />
              {error}
            </Alert>
          ) : (
            <VStack spacing={4} align="stretch">
              {!originalIsEditable && (
                <Alert status="warning">
                    <AlertIcon />
                    {t('editTokenModal.nonEditableWarning', 'This token is marked as non-editable. Changes will not be saved.')}
                </Alert>
              )}
              <FormControl isRequired isDisabled={!originalIsEditable}>
                <FormLabel>{t('editTokenModal.form.name.label', 'Token Name')}</FormLabel>
                <Input ref={initialRef} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('editTokenModal.form.name.placeholder', 'e.g., My API Key')} />
              </FormControl>

              <FormControl isDisabled={!originalIsEditable}>
                <FormLabel>{t('editTokenModal.form.description.label', 'Description')}</FormLabel>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t('editTokenModal.form.description.placeholder', 'Optional: Describe the token\'s purpose')} />
              </FormControl>

              <FormControl isRequired isDisabled={!originalIsEditable}>
                <FormLabel>{t('editTokenModal.form.sensitivity.label', 'Sensitivity Level')}</FormLabel>
                <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value as typeof sensitivity)}>
                  {SENSITIVITY_LEVELS.map((level) => (
                    <option key={level} value={level}>{level}</option>
                  ))}
                </Select>
                <FormHelperText>{t('editTokenModal.form.sensitivity.helper', 'Controls data access restrictions.')}</FormHelperText>
              </FormControl>
              
              <Divider />

              <FormControl isDisabled={!originalIsEditable}>
                <FormLabel>{t('editTokenModal.form.allowRules.label', 'Allow Rules (Require ALL)')}</FormLabel>
                 <VStack align="stretch" spacing={2} pl={2} borderLeft="2px" borderColor="green.200">
                    {allowRules.map((rule, index) => (
                      <HStack key={`allow-${index}`} spacing={2} align="flex-start">
                        <Input 
                          placeholder={t('editTokenModal.form.rules.fieldPlaceholder', 'Metadata Field')} 
                          value={rule.field}
                          onChange={(e) => updateRule(index, 'field', e.target.value, 'allow')}
                          size="sm"
                          isDisabled={!originalIsEditable}
                          flexShrink={0}
                          w="150px"
                        />
                        <TagInput 
                          placeholder={t('editTokenModal.form.rules.valuesPlaceholder', 'Allowed Values (Enter)')} 
                          value={rule.values}
                          onChange={(newValues) => updateRule(index, 'values', newValues, 'allow')}
                          size="sm"
                          isDisabled={!originalIsEditable}
                        />
                        <IconButton 
                          aria-label={t('editTokenModal.form.rules.removeRule', 'Remove Rule')} 
                          icon={<FaTrash />} 
                          size="sm"
                          variant="ghost"
                          colorScheme="red"
                          onClick={() => removeRule(index, 'allow')}
                          isDisabled={!originalIsEditable}
                          alignSelf="center"
                        />
                      </HStack>
                    ))}
                    <Button 
                      leftIcon={<FaPlus />} 
                      size="sm" 
                      variant="outline"
                      onClick={() => addRule('allow')}
                      isDisabled={!originalIsEditable}
                    >
                      {t('editTokenModal.form.rules.addAllowRule', 'Add Allow Rule')}
                    </Button>
                  </VStack>
                <FormHelperText>{t('editTokenModal.form.allowRules.helper', 'Data must match ALL allow rules defined.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl isDisabled={!originalIsEditable}>
                 <FormLabel>{t('editTokenModal.form.denyRules.label', 'Deny Rules (Require ANY)')}</FormLabel>
                  <VStack align="stretch" spacing={2} pl={2} borderLeft="2px" borderColor="red.200">
                    {denyRules.map((rule, index) => (
                      <HStack key={`deny-${index}`} spacing={2} align="flex-start">
                        <Input 
                          placeholder={t('editTokenModal.form.rules.fieldPlaceholder', 'Metadata Field')} 
                          value={rule.field}
                          onChange={(e) => updateRule(index, 'field', e.target.value, 'deny')}
                          size="sm"
                          isDisabled={!originalIsEditable}
                          flexShrink={0}
                          w="150px"
                        />
                        <TagInput 
                          placeholder={t('editTokenModal.form.rules.valuesPlaceholder', 'Denied Values (Enter)')} 
                          value={rule.values}
                          onChange={(newValues) => updateRule(index, 'values', newValues, 'deny')}
                          size="sm"
                          isDisabled={!originalIsEditable}
                        />
                        <IconButton 
                          aria-label={t('editTokenModal.form.rules.removeRule', 'Remove Rule')} 
                          icon={<FaTrash />} 
                          size="sm"
                          variant="ghost"
                          colorScheme="red"
                          onClick={() => removeRule(index, 'deny')}
                          isDisabled={!originalIsEditable}
                          alignSelf="center"
                        />
                      </HStack>
                    ))}
                    <Button 
                      leftIcon={<FaPlus />} 
                      size="sm" 
                      variant="outline"
                      onClick={() => addRule('deny')}
                      isDisabled={!originalIsEditable}
                    >
                      {t('editTokenModal.form.rules.addDenyRule', 'Add Deny Rule')}
                    </Button>
                  </VStack>
                <FormHelperText>{t('editTokenModal.form.denyRules.helper', 'Data matching ANY deny rule defined will be excluded.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl isDisabled={!originalIsEditable}>
                 <FormLabel>{t('editTokenModal.form.expiry.label', 'Expiry Date (Optional)')}</FormLabel>
                 <Input 
                    type="datetime-local" 
                    value={expiry} 
                    onChange={(e) => setExpiry(e.target.value)} 
                 />
                 <FormHelperText>{t('editTokenModal.form.expiry.helper', 'Token will become inactive after this date.')}</FormHelperText>
              </FormControl>

               <FormControl display="flex" alignItems="center" isDisabled={!originalIsEditable}>
                  <FormLabel htmlFor="is-editable" mb="0">
                     {t('editTokenModal.form.editable.label', 'Editable?')}
                  </FormLabel>
                  <Switch 
                      id="is-editable" 
                      isChecked={isEditable} 
                      onChange={(e) => setIsEditable(e.target.checked)} 
                      isDisabled={!originalIsEditable}
                  />
                  <FormHelperText ml={2}>{t('editTokenModal.form.editable.helper', 'Can this token\'s settings be changed later?')}</FormHelperText>
               </FormControl>

            </VStack>
          )}
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            {t('common.actions.cancel', 'Cancel')}
          </Button>
          <Button 
            colorScheme="blue" 
            type="submit" 
            isLoading={isLoading} 
            isDisabled={isFetching || !!error || !originalIsEditable}
          >
            {t('common.actions.saveChanges', 'Save Changes')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default EditTokenModal; 