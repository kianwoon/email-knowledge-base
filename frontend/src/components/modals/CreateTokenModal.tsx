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
import { TokenCreatePayload, TokenCreateResponse, createToken } from '../../api/token';
import { FaCopy } from 'react-icons/fa';
import TagInput from '../inputs/TagInput';

interface CreateTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenCreated: () => void;
}

const SENSITIVITY_LEVELS = ["public", "internal", "confidential", "strict-confidential"];

const CreateTokenModal: React.FC<CreateTokenModalProps> = ({ isOpen, onClose, onTokenCreated }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]);
  const [expiryDays, setExpiryDays] = useState<number | null>(null);
  const [allowRules, setAllowRules] = useState<string[]>([]);
  const [denyRules, setDenyRules] = useState<string[]>([]);

  // State for Success View
  const [createdTokenValue, setCreatedTokenValue] = useState<string | null>(null);
  const [showSuccessView, setShowSuccessView] = useState<boolean>(false);
  const { onCopy, hasCopied } = useClipboard(createdTokenValue || '');

  const resetForm = () => {
    setName('');
    setDescription('');
    setSensitivity(SENSITIVITY_LEVELS[0]);
    setExpiryDays(null);
    setAllowRules([]);
    setDenyRules([]);
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

    const tokenData: TokenCreatePayload = {
      name,
      description: description || undefined,
      sensitivity,
      expiry_days: expiryDays,
      allow_rules: allowRules.length > 0 ? allowRules : undefined,
      deny_rules: denyRules.length > 0 ? denyRules : undefined,
    };

    try {
      const createdToken: TokenCreateResponse = await createToken(tokenData);

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
                <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}>
                  {SENSITIVITY_LEVELS.map((level) => (
                    <option key={level} value={level}>{level}</option>
                  ))}
                </Select>
                <FormHelperText>{t('createTokenModal.form.sensitivity.helper', 'Determines the maximum data sensitivity accessible.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl>
                <FormLabel>{t('createTokenModal.form.allowRules.label', 'Allow Rules')}</FormLabel>
                <TagInput
                  placeholder={t('createTokenModal.form.allowRules.placeholder', 'Enter allowed rule and press Enter')}
                  value={allowRules}
                  onChange={setAllowRules}
                />
                <FormHelperText>{t('createTokenModal.form.allowRules.helper', 'Optional: List of rules allowing access.')}</FormHelperText>
              </FormControl>

              <Divider />

              <FormControl>
                <FormLabel>{t('createTokenModal.form.denyRules.label', 'Deny Rules')}</FormLabel>
                <TagInput
                  placeholder={t('createTokenModal.form.denyRules.placeholder', 'Enter denied rule and press Enter')}
                  value={denyRules}
                  onChange={setDenyRules}
                />
                <FormHelperText>{t('createTokenModal.form.denyRules.helper', 'Optional: List of rules denying access.')}</FormHelperText>
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
                <FormHelperText>{t('createTokenModal.form.expiryDays.helper', 'Token will automatically become inactive after this many days.')}</FormHelperText>
              </FormControl>
            </VStack>
          )}
        </ModalBody>

        <ModalFooter>
          {showSuccessView ? (
            <Button colorScheme="blue" onClick={handleCloseAndReset}>
              {t('common.close', 'Close')}
            </Button>
          ) : (
            <>
              <Button variant="ghost" mr={3} onClick={handleCloseAndReset} isDisabled={isLoading}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button type="submit" colorScheme="cyan" isLoading={isLoading}>
                {t('createTokenModal.createButton', 'Create Token')}
              </Button>
            </>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default CreateTokenModal;
