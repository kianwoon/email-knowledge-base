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
import { TokenUpdate, Token, getTokenById, updateToken } from '../../api/token';
import TagInput from '../inputs/TagInput';

interface EditTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenUpdated: () => void;
  tokenId: number | null;
}

// Bring back sensitivity levels
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
  const [allowTopics, setAllowTopics] = useState<string[]>([]);
  const [denyTopics, setDenyTopics] = useState<string[]>([]);
  const [expiry, setExpiry] = useState('');
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (isOpen && tokenId !== null) {
      const fetchToken = async () => {
        setIsFetching(true);
        setError(null);
        try {
          console.log(`EditModal: Fetching data for token ID: ${tokenId}`);
          const tokenData = await getTokenById(String(tokenId));
          console.log('EditModal: Data received:', tokenData);
          setName(tokenData.name);
          setDescription(tokenData.description || '');
          setSensitivity(tokenData.sensitivity || SENSITIVITY_LEVELS[0]);
          setAllowTopics(tokenData.allow_topics || []);
          setDenyTopics(tokenData.deny_topics || []);
          setExpiry(tokenData.expiry ? tokenData.expiry.slice(0, 16) : '');
          setIsActive(tokenData.is_active);
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
      setAllowTopics([]);
      setDenyTopics([]);
      setExpiry('');
      setIsActive(true);
      setError(null);
      setIsFetching(false);
      setIsLoading(false);
    }
  }, [isOpen, tokenId, t]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (tokenId === null) {
        toast({
            title: t('editTokenModal.toast.errorTitle', 'Update Failed'),
            description: t('editTokenModal.toast.missingId', 'Token ID is missing.'),
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
      allow_topics: allowTopics,
      deny_topics: denyTopics,
      expiry: expiry ? new Date(expiry).toISOString() : null,
      is_active: isActive,
    };

    try {
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
            <Alert status="error">
              <AlertIcon />
              {error}
            </Alert>
          ) : (
            <VStack spacing={4} align="stretch">
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
                <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value as typeof sensitivity)}>
                  {SENSITIVITY_LEVELS.map((level) => (
                    <option key={level} value={level}>{level}</option>
                  ))}
                </Select>
                <FormHelperText>{t('editTokenModal.form.sensitivity.helper', 'Controls data access restrictions.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl>
                 <FormLabel>{t('editTokenModal.form.allowTopics.label', 'Allow Topics')}</FormLabel>
                  <TagInput 
                      placeholder={t('editTokenModal.form.allowTopics.placeholder', 'Add allowed topics (Enter)')} 
                      value={allowTopics}
                      onChange={(newTopics) => setAllowTopics(newTopics)}
                    />
                <FormHelperText>{t('editTokenModal.form.allowTopics.helper', 'Optional: List of topics this token can access.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl>
                 <FormLabel>{t('editTokenModal.form.denyTopics.label', 'Deny Topics')}</FormLabel>
                  <TagInput 
                      placeholder={t('editTokenModal.form.denyTopics.placeholder', 'Add denied topics (Enter)')} 
                      value={denyTopics}
                      onChange={(newTopics) => setDenyTopics(newTopics)}
                    />
                <FormHelperText>{t('editTokenModal.form.denyTopics.helper', 'Optional: List of topics this token CANNOT access.')}</FormHelperText>
              </FormControl>

              <Divider />

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
            {t('common.actions.saveChanges', 'Save Changes')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default EditTokenModal; 