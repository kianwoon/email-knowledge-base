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
  Textarea, // Keep for Description
  Select,
  VStack,
  useToast,
  CircularProgress,
  Center,
  Alert,
  AlertIcon,
  Divider,
  Switch,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { TokenUpdatePayload, Token, getTokenById, updateToken } from '../../api/token';
import TagInput from '../inputs/TagInput';

interface EditTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenUpdated: () => void;
  tokenId: number | null;
}

const SENSITIVITY_LEVELS = ["public", "internal", "confidential", "strict-confidential"];

const EditTokenModal: React.FC<EditTokenModalProps> = ({ isOpen, onClose, onTokenUpdated, tokenId }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const initialRef = useRef<HTMLInputElement>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]);
  const [expiry, setExpiry] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [allowRules, setAllowRules] = useState<string[]>([]);
  const [denyRules, setDenyRules] = useState<string[]>([]);
  // REMOVED embedding state

  useEffect(() => {
    if (isOpen && tokenId !== null) {
      const fetchToken = async () => {
        setIsFetching(true);
        setError(null);
        try {
          // Ensure tokenId is passed as string if API expects it
          const tokenData: Token = await getTokenById(String(tokenId));
          setName(tokenData.name);
          setDescription(tokenData.description || '');
          setSensitivity(tokenData.sensitivity || SENSITIVITY_LEVELS[0]);
          setExpiry(tokenData.expiry ? tokenData.expiry.slice(0, 16) : '');
          setIsActive(tokenData.is_active);
          setAllowRules(tokenData.allow_rules || []);
          setDenyRules(tokenData.deny_rules || []);
          // REMOVED embedding state population

        } catch (err: any) {
          setError(t('editTokenModal.errors.fetchFailed', 'Failed to load token data. Please try again.'));
        } finally {
          setIsFetching(false);
        }
      };
      fetchToken();
    } else {
      // Reset form state
      setName('');
      setDescription('');
      setSensitivity(SENSITIVITY_LEVELS[0]);
      setExpiry('');
      setIsActive(true);
      setAllowRules([]);
      setDenyRules([]);
      // REMOVED embedding state reset
      setError(null);
      setIsFetching(false);
      setIsLoading(false);
    }
  }, [isOpen, tokenId, t]);

  // REMOVED processTextareaInput helper

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (tokenId === null) return;
    setIsLoading(true);

    // Use allowRules and denyRules state directly
    const tokenUpdateData: TokenUpdatePayload = {
      name,
      description: description || undefined,
      sensitivity,
      allow_rules: allowRules,
      deny_rules: denyRules,
      // REMOVED embedding fields from payload
      expiry: expiry ? new Date(expiry).toISOString() : null,
      is_active: isActive,
    };

    try {
       // Ensure tokenId is passed as string if API expects it
      await updateToken(String(tokenId), tokenUpdateData);
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
             <Center h="200px"> <CircularProgress isIndeterminate color="blue.300" /> </Center>
          ) : error ? (
            <Alert status="error"> <AlertIcon /> {error} </Alert>
          ) : (
            <VStack spacing={4} align="stretch">
              {/* Standard Fields */}
                <FormControl isRequired>
                  <FormLabel>{t('editTokenModal.form.name.label', 'Token Name')}</FormLabel>
                  <Input ref={initialRef} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('editTokenModal.form.name.placeholder', 'e.g., My API Key')} />
                </FormControl>
                <FormControl>
                  <FormLabel>{t('editTokenModal.form.description.label', 'Description')}</FormLabel>
                  <Textarea
                    placeholder={t('editTokenModal.form.description.placeholder', 'Optional: Describe the purpose of this token')}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </FormControl>
                <FormControl isRequired>
                  <FormLabel>{t('editTokenModal.form.sensitivity.label', 'Sensitivity Level')}</FormLabel>
                  <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}>
                    {SENSITIVITY_LEVELS.map((level) => (
                      <option key={level} value={level}>{level}</option>
                    ))}
                  </Select>
                  <FormHelperText>{t('editTokenModal.form.sensitivity.helper', 'Controls data access restrictions.')}</FormHelperText>
                </FormControl>

              <Divider />

              {/* --- Rules Inputs (Using TagInput) --- */}
              <FormControl>
                  <FormLabel>{t('editTokenModal.form.allowRules.label', 'Allow Rules')}</FormLabel>
                   <TagInput
                      placeholder={t('editTokenModal.form.allowRules.placeholder', 'Enter allowed rule and press Enter')}
                      value={allowRules}
                      onChange={setAllowRules}
                    />
                  <FormHelperText>{t('editTokenModal.form.allowRules.helper', 'Optional: List of rules allowing access.')}</FormHelperText>
                </FormControl>

              <Divider />

              <FormControl>
                   <FormLabel>{t('editTokenModal.form.denyRules.label', 'Deny Rules')}</FormLabel>
                    <TagInput
                      placeholder={t('editTokenModal.form.denyRules.placeholder', 'Enter denied rule and press Enter')}
                      value={denyRules}
                      onChange={setDenyRules}
                    />
                  <FormHelperText>{t('editTokenModal.form.denyRules.helper', 'Optional: List of rules denying access.')}</FormHelperText>
                </FormControl>

              <Divider />

              {/* REMOVED Embedding Inputs Section */}

              {/* Expiry and Active Status */}
              <FormControl>
                   <FormLabel>{t('editTokenModal.form.expiry.label', 'Expiry Date (Optional)')}</FormLabel>
                   <Input
                      type="datetime-local"
                      value={expiry}
                      onChange={(e) => setExpiry(e.target.value)}
                   />
                   <FormHelperText>{t('editTokenModal.form.expiry.helper', 'Token will become inactive after this date.')}</FormHelperText>
                </FormControl>
                <FormControl display="flex" alignItems="center">
                    <FormLabel htmlFor="is-active" mb="0">
                        {t('editTokenModal.form.active.label', 'Active')}
                    </FormLabel>
                    <Switch
                        id="is-active"
                        isChecked={isActive}
                        onChange={(e) => setIsActive(e.target.checked)}
                    />
                    <FormHelperText ml={2}>{t('editTokenModal.form.active.helper', 'Inactive tokens cannot be used.')}</FormHelperText>
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
              isDisabled={isFetching || !!error}
            >
              {t('common.actions.save', 'Save Changes')}
            </Button>
          </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default EditTokenModal;