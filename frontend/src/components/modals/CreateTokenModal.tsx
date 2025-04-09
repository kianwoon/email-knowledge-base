import React, { useState, useRef } from 'react';
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
  VStack,
  useToast,
  Text as ChakraText,
  Divider,
  InputGroup,
  InputRightElement,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  useClipboard,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { TokenCreate, createToken, Token } from '../../api/token';
import { FaCopy } from 'react-icons/fa';
import TagInput from '../inputs/TagInput';

interface CreateTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenCreated: () => void;
}

// Bring back sensitivity levels
const SENSITIVITY_LEVELS = ["public", "internal", "confidential", "strict-confidential"];

const CreateTokenModal: React.FC<CreateTokenModalProps> = ({ isOpen, onClose, onTokenCreated }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]); // Add state back
  const [expiryDays, setExpiryDays] = useState<number | null>(null);

  // State for topics
  const [allowTopics, setAllowTopics] = useState<string[]>([]);
  const [denyTopics, setDenyTopics] = useState<string[]>([]);

  // --- State for Success View ---
  const [createdTokenValue, setCreatedTokenValue] = useState<string | null>(null);
  const [showSuccessView, setShowSuccessView] = useState<boolean>(false);
  const { onCopy, hasCopied } = useClipboard(createdTokenValue || '');

  const resetForm = () => {
    setName('');
    setDescription('');
    setSensitivity(SENSITIVITY_LEVELS[0]); // Reset sensitivity
    setExpiryDays(null);
    setAllowTopics([]);
    setDenyTopics([]);
    setIsLoading(false);
  };

  const handleCloseAndReset = () => {
    resetForm();
    setCreatedTokenValue(null);
    setShowSuccessView(false);
    onClose();
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsLoading(true);
    setCreatedTokenValue(null);
    setShowSuccessView(false);

    const tokenData: TokenCreate = {
      name,
      description: description || null,
      sensitivity, // Add sensitivity to payload
      expiry_days: expiryDays,
      allow_topics: allowTopics,
      deny_topics: denyTopics,
    };

    try {
      const createdToken: Token = await createToken(tokenData);
      
      toast({
        title: t('createTokenModal.toast.successTitle', 'Token Created'),
        description: t('createTokenModal.toast.successDescription', `Token "${name}" was successfully created.`),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      
      setCreatedTokenValue(createdToken.token_value || '[Error: Token Value Missing]');
      setShowSuccessView(true);
      onTokenCreated();

    } catch (error: any) {
      console.error("Token creation failed:", error);
      toast({
        title: t('createTokenModal.toast.errorTitle', 'Creation Failed'),
        description: error?.response?.data?.detail || error.message || t('createTokenModal.toast.errorDescription', 'Could not create token.'),
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
      setShowSuccessView(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyToken = () => {
    if (createdTokenValue) {
      onCopy();
      toast({        
        title: t('createTokenModal.copySuccess', 'Token Copied'),
        status: 'success',
        duration: 2000,
        isClosable: true,
      });
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleCloseAndReset} size="xl" closeOnOverlayClick={!showSuccessView}>
      <ModalOverlay />
      <ModalContent as={!showSuccessView ? "form" : "div"} onSubmit={!showSuccessView ? handleSubmit : undefined}>
        <ModalHeader>
          {showSuccessView 
            ? t('createTokenModal.successTitle', 'Token Created Successfully')
            : t('createTokenModal.title', 'Create New Access Token')}
        </ModalHeader>
        <ModalCloseButton />

        <ModalBody pb={6}>
          {showSuccessView && createdTokenValue ? (
            <VStack spacing={4} align="stretch">
              <Alert
                status='success'
                variant='subtle'
                flexDirection='column'
                alignItems='center'
                justifyContent='center'
                textAlign='center'
                height='auto'
                borderRadius="md"
              >
                <AlertIcon boxSize='40px' mr={0} />
                <AlertTitle mt={4} mb={1} fontSize='lg'>
                  {t('createTokenModal.successTitle', 'Token Created Successfully')}
                </AlertTitle>
                <AlertDescription maxWidth='sm' mb={4}>
                  {t('createTokenModal.successMessage', 'Your new API token has been created. Please copy and store it securely. You will not be able to see this token again.')}
                </AlertDescription>
              </Alert>

              <FormControl>
                <FormLabel>{t('createTokenModal.newTokenLabel', 'New API Token')}</FormLabel>
                <InputGroup size='md'>
                  <Input
                    pr='4.5rem'
                    type='text'
                    value={createdTokenValue}
                    isReadOnly
                    fontFamily="monospace"
                  />
                  <InputRightElement width='4.5rem'>
                    <Button h='1.75rem' size='sm' onClick={handleCopyToken} leftIcon={<FaCopy />}>
                      {hasCopied ? t('common.copied', 'Copied') : t('common.copy', 'Copy')}
                    </Button>
                  </InputRightElement>
                </InputGroup>
              </FormControl>
            </VStack>
          ) : (
            <VStack spacing={4} align="stretch">
              <FormControl isRequired>
                <FormLabel>{t('createTokenModal.form.name.label', 'Token Name')}</FormLabel>
                <Input 
                  placeholder={t('createTokenModal.form.name.placeholder', 'e.g., Project X API Key')} 
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </FormControl>

              <FormControl>
                <FormLabel>{t('createTokenModal.form.description.label', 'Description')}</FormLabel>
                <Textarea 
                  placeholder={t('createTokenModal.form.description.placeholder', 'Optional: Describe the purpose of this token')} 
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>{t('createTokenModal.form.sensitivity.label', 'Sensitivity Level')}</FormLabel>
                <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value as typeof sensitivity)}>
                  {SENSITIVITY_LEVELS.map((level) => (
                    <option key={level} value={level}>{level}</option>
                  ))}
                </Select>
                <FormHelperText>{t('createTokenModal.form.sensitivity.helper', 'Determines the maximum data sensitivity accessible.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl>
                <FormLabel>{t('createTokenModal.form.allowTopics.label', 'Allow Topics')}</FormLabel>
                <TagInput 
                  placeholder={t('createTokenModal.form.allowTopics.placeholder', 'Add allowed topics (Enter)')} 
                  value={allowTopics}
                  onChange={(newTopics) => setAllowTopics(newTopics)}
                />
                <FormHelperText>{t('createTokenModal.form.allowTopics.helper', 'Optional: List of topics this token can access.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl>
                <FormLabel>{t('createTokenModal.form.denyTopics.label', 'Deny Topics')}</FormLabel>
                <TagInput 
                  placeholder={t('createTokenModal.form.denyTopics.placeholder', 'Add denied topics (Enter)')} 
                  value={denyTopics}
                  onChange={(newTopics) => setDenyTopics(newTopics)}
                />
                <FormHelperText>{t('createTokenModal.form.denyTopics.helper', 'Optional: List of topics this token CANNOT access.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl>
                <FormLabel>{t('createTokenModal.form.expiryDays.label', 'Expiry (Days, Optional)')}</FormLabel>
                <Input 
                  type="number"
                  placeholder={t('createTokenModal.form.expiryDays.placeholder', 'e.g., 30')}
                  value={expiryDays === null ? '' : expiryDays}
                  onChange={(e) => setExpiryDays(e.target.value === '' ? null : parseInt(e.target.value, 10))}
                  min="1"
                />
                <FormHelperText>{t('createTokenModal.form.expiryDays.helper', 'Token will become inactive after this many days.')}</FormHelperText>
              </FormControl>

            </VStack>
          )}
        </ModalBody>

        <ModalFooter>
          {showSuccessView ? (
            <Button onClick={handleCloseAndReset}> 
              {t('common.close', 'Close')}
            </Button>
          ) : (
            <>
              <Button onClick={handleCloseAndReset} mr={3} isDisabled={isLoading}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button 
                colorScheme="cyan" 
                type="submit"
                isLoading={isLoading}
                loadingText={t('common.creating', 'Creating...')}
              >
                {t('createTokenModal.submitButton', 'Create Token')}
              </Button>
            </>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default CreateTokenModal; 