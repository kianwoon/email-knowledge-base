import React, { useState, useRef, useEffect } from 'react';
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
  Checkbox,
  Switch,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Spinner,
  FormErrorMessage,
  Grid,
  GridItem,
  Collapse
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { TokenCreatePayload, TokenCreateResponse, createToken, TokenType } from '../../api/token';
import { getEmailFactsColumns } from '../../api/schema';
import { FaCopy } from 'react-icons/fa';
import TagInput from '../inputs/TagInput';

interface CreateTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenCreated: () => void;
}

const SENSITIVITY_LEVELS = ["public", "internal", "confidential", "strict-confidential"];
const DEFAULT_ROW_LIMIT = 10000;

const CreateTokenModal: React.FC<CreateTokenModalProps> = ({ isOpen, onClose, onTokenCreated }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]);
  const [expiryDays, setExpiryDays] = useState<number | string>('');
  const [allowRules, setAllowRules] = useState<string[]>([]);
  const [denyRules, setDenyRules] = useState<string[]>([]);

  // NEW v3 Form State
  const [tokenType, setTokenType] = useState<TokenType>(TokenType.PUBLIC);
  const [providerBaseUrl, setProviderBaseUrl] = useState('');
  const [audience, setAudience] = useState('');
  const [allowAttachments, setAllowAttachments] = useState(false);
  const [canExportVectors, setCanExportVectors] = useState(false);
  const [rowLimit, setRowLimit] = useState<number | string>(DEFAULT_ROW_LIMIT);
  const [allowColumns, setAllowColumns] = useState<string[]>([]);

  // State for fetching available columns
  const [availableColumns, setAvailableColumns] = useState<string[]>([]);
  const [columnsLoading, setColumnsLoading] = useState<boolean>(false);
  const [columnsError, setColumnsError] = useState<string | null>(null);

  // State for Success View
  const [createdTokenValue, setCreatedTokenValue] = useState<string | null>(null);
  const [showSuccessView, setShowSuccessView] = useState<boolean>(false);
  const { onCopy, hasCopied } = useClipboard(createdTokenValue || '');

  // Fetch available columns when the modal opens
  useEffect(() => {
    if (isOpen) {
      const fetchColumns = async () => {
        setColumnsLoading(true);
        setColumnsError(null);
        try {
          const cols = await getEmailFactsColumns();
          setAvailableColumns(cols);
        } catch (err: any) {
          console.error("Failed to fetch columns:", err);
          setColumnsError(t('createTokenModal.errors.fetchColumnsFailed', 'Failed to load column list. Please check backend connection.'));
        } finally {
          setColumnsLoading(false);
        }
      };
      fetchColumns();
    } else {
      setAvailableColumns([]);
      setColumnsError(null);
    }
  }, [isOpen, t]);

  const resetForm = () => {
    setName('');
    setDescription('');
    setSensitivity(SENSITIVITY_LEVELS[0]);
    setExpiryDays('');
    setAllowRules([]);
    setDenyRules([]);
    setTokenType(TokenType.PUBLIC);
    setProviderBaseUrl('');
    setAudience('');
    setAllowAttachments(false);
    setCanExportVectors(false);
    setRowLimit(DEFAULT_ROW_LIMIT);
    setAllowColumns([]);
    setIsLoading(false);
    setError(null);
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
    setError(null);
    setCreatedTokenValue(null);
    setShowSuccessView(false);

    const numericRowLimit = typeof rowLimit === 'string' ? parseInt(rowLimit, 10) : rowLimit;
    if (isNaN(numericRowLimit) || numericRowLimit < 1) {
      setError(t('createTokenModal.errors.invalidRowLimit', 'Row limit must be a positive number.'));
      setIsLoading(false);
      return;
    }
    const numericExpiryDays = typeof expiryDays === 'string' ? parseInt(expiryDays, 10) : expiryDays;
    if (expiryDays !== '' && (isNaN(numericExpiryDays) || numericExpiryDays <= 0)) {
      setError(t('createTokenModal.errors.invalidExpiry', 'Expiry days must be a positive number if provided.'));
      setIsLoading(false);
      return;
    }

    const tokenData: TokenCreatePayload = {
      name,
      description: description || undefined,
      sensitivity,
      expiry_days: expiryDays === '' ? null : numericExpiryDays,
      allow_rules: allowRules.length > 0 ? allowRules : undefined,
      deny_rules: denyRules.length > 0 ? denyRules : undefined,
      token_type: tokenType,
      provider_base_url: tokenType === TokenType.SHARE && providerBaseUrl ? providerBaseUrl : undefined,
      audience: audience ? { list: audience.split(',').map(s => s.trim()).filter(s => s) } : undefined,
      allow_attachments: allowAttachments,
      can_export_vectors: canExportVectors,
      row_limit: numericRowLimit,
      allow_columns: allowColumns.length > 0 ? allowColumns : undefined,
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
      const errorDetail = error?.response?.data?.detail || error.message || t('createTokenModal.toast.errorDescription', 'Could not create token.');
      setError(errorDetail);
      toast({
        title: t('createTokenModal.toast.errorTitle', 'Creation Failed'),
        description: errorDetail,
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

  const handleAllowColumnChange = (columnName: string, isChecked: boolean) => {
    setAllowColumns(prev => 
      isChecked 
        ? [...prev, columnName] 
        : prev.filter(col => col !== columnName)
    );
  };

  return (
    <Modal isOpen={isOpen} onClose={handleCloseAndReset} size="3xl" closeOnOverlayClick={!showSuccessView} scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent as={"div"}>
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
                py={6}
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
            <VStack spacing={5} align="stretch">
              {error && (
                <Alert status="error" borderRadius="md">
                  <AlertIcon />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              
              <FormControl isRequired>
                <FormLabel>{t('createTokenModal.form.name.label', 'Token Name')}</FormLabel>
                <Input
                  placeholder={t('createTokenModal.form.name.placeholder', 'e.g., Project X API Key')}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <FormHelperText>{t('createTokenModal.form.nameHelp')}</FormHelperText>
              </FormControl>

              <FormControl>
                <FormLabel>{t('createTokenModal.form.description.label', 'Description')}</FormLabel>
                <Textarea
                  placeholder={t('createTokenModal.form.description.placeholder', 'Optional: Describe the purpose of this token')}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </FormControl>

              <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                 <GridItem>
                   <FormControl>
                     <FormLabel>{t('createTokenModal.form.tokenType.label', 'Token Type')}</FormLabel>
                     <Select value={tokenType} onChange={(e) => setTokenType(e.target.value as TokenType)}>
                       <option value={TokenType.PUBLIC}>{t('tokenManagement.types.public', 'Public')}</option>
                       <option value={TokenType.SHARE}>{t('tokenManagement.types.share', 'Share')}</option>
                     </Select>
                   </FormControl>
                 </GridItem>
                 <GridItem>
                    <Collapse in={tokenType === TokenType.SHARE} animateOpacity>
                      <FormControl isRequired={tokenType === TokenType.SHARE}>
                         <FormLabel>{t('createTokenModal.form.providerBaseUrl.label', 'Provider Base URL')}</FormLabel>
                         <Input
                           placeholder={t('createTokenModal.form.providerBaseUrl.placeholder', 'e.g., https://provider.example.com')}
                           value={providerBaseUrl}
                           onChange={(e) => setProviderBaseUrl(e.target.value)}
                           isDisabled={tokenType !== TokenType.SHARE}
                         />
                         <FormHelperText>{t('createTokenModal.form.providerBaseUrl.helper', 'Required for \'Share\' tokens.')}</FormHelperText>
                       </FormControl>
                    </Collapse>
                 </GridItem>
              </Grid>

              <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                <GridItem>
                  <FormControl isRequired>
                    <FormLabel>{t('createTokenModal.form.sensitivity.label', 'Sensitivity Level')}</FormLabel>
                    <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}>
                      {SENSITIVITY_LEVELS.map((level) => (
                        <option key={level} value={level}>{t(`createTokenModal.form.sensitivityOptions.${level.replace('-', '_')}`)}</option>
                      ))}
                    </Select>
                    <FormHelperText>{t('createTokenModal.form.sensitivityHelp')}</FormHelperText>
                  </FormControl>
                </GridItem>
                <GridItem>
                  <FormControl isInvalid={!!error && error.includes('Expiry')}>
                    <FormLabel htmlFor="expiryDays">
                      {t('createTokenModal.form.expiryDays', 'Expiry (Days, Optional)')}
                    </FormLabel>
                    <NumberInput 
                      id="expiryDays"
                      value={expiryDays} 
                      onChange={(valueString) => setExpiryDays(valueString ? parseInt(valueString, 10) : '')} 
                      min={1}
                    >
                      <NumberInputField placeholder={t('createTokenModal.form.expiryPlaceholder', 'e.g., 30')} />
                      <NumberInputStepper>
                        <NumberIncrementStepper />
                        <NumberDecrementStepper />
                      </NumberInputStepper>
                    </NumberInput>
                    <FormHelperText>
                      {t('createTokenModal.form.expiryHelp', 'Leave blank for no expiry.')}
                    </FormHelperText>
                    {error && error.includes('Expiry') && <FormErrorMessage>{error}</FormErrorMessage>}
                  </FormControl>
                </GridItem>
              </Grid>

              <Divider />

              <FormControl>
                <FormLabel>{t('createTokenModal.form.allowRules.label', 'Allow Rules')}</FormLabel>
                <TagInput
                  placeholder={t('createTokenModal.form.allowRules.placeholder', 'Enter allowed rule and press Enter')}
                  value={allowRules}
                  onChange={setAllowRules}
                />
                <FormHelperText>{t('createTokenModal.form.allowRulesHelp')}</FormHelperText>
              </FormControl>

              <FormControl>
                <FormLabel>{t('createTokenModal.form.denyRules.label', 'Deny Rules')}</FormLabel>
                <TagInput
                  placeholder={t('createTokenModal.form.denyRules.placeholder', 'Enter denied rule and press Enter')}
                  value={denyRules}
                  onChange={setDenyRules}
                />
                <FormHelperText>{t('createTokenModal.form.denyRulesHelp')}</FormHelperText>
              </FormControl>
               
               <Divider />

               <FormControl>
                 <FormLabel>{t('createTokenModal.form.audience.label', 'Audience Restrictions (Optional)')}</FormLabel>
                 <Input
                   placeholder={t('createTokenModal.form.audience.placeholder', 'e.g., 192.168.1.0/24, example.org')}
                   value={audience}
                   onChange={(e) => setAudience(e.target.value)}
                 />
                 <FormHelperText>{t('createTokenModal.form.audienceHelp')}</FormHelperText>
               </FormControl>
               
               <Divider />

               <Grid templateColumns="repeat(3, 1fr)" gap={6}>
                  <GridItem>
                     <FormControl display='flex' alignItems='center'>
                       <Switch 
                         id='allow-attachments' 
                         isChecked={allowAttachments} 
                         onChange={(e) => setAllowAttachments(e.target.checked)} 
                         mr={3}
                       />
                       <FormLabel htmlFor='allow-attachments' mb='0'>
                         {t('createTokenModal.form.allowAttachments.label', 'Allow Attachments')}
                       </FormLabel>
                       <FormHelperText mt={1} ml={2}>{t('createTokenModal.form.allowAttachmentsHelp')}</FormHelperText>
                     </FormControl>
                  </GridItem>
                   <GridItem>
                     <FormControl display='flex' alignItems='center'>
                       <Switch 
                         id='can-export-vectors' 
                         isChecked={canExportVectors} 
                         onChange={(e) => setCanExportVectors(e.target.checked)} 
                         mr={3}
                       />
                       <FormLabel htmlFor='can-export-vectors' mb='0'>
                         {t('createTokenModal.form.canExportVectors.label', 'Allow Vector Export')}
                       </FormLabel>
                       <FormHelperText mt={1} ml={2}>{t('createTokenModal.form.canExportVectorsHelp')}</FormHelperText>
                     </FormControl>
                   </GridItem>
                   <GridItem>
                      <FormControl isInvalid={isNaN(parseInt(String(rowLimit), 10)) || parseInt(String(rowLimit), 10) < 1}>
                          <FormLabel>{t('createTokenModal.form.rowLimit.label', 'Row Limit')}</FormLabel>
                          <NumberInput 
                             min={1} 
                             defaultValue={DEFAULT_ROW_LIMIT} 
                             value={rowLimit} 
                             onChange={(valueString) => setRowLimit(valueString)}
                             allowMouseWheel
                           >
                            <NumberInputField />
                            <NumberInputStepper>
                              <NumberIncrementStepper />
                              <NumberDecrementStepper />
                            </NumberInputStepper>
                          </NumberInput>
                          <FormHelperText>{t('createTokenModal.form.rowLimitHelp')}</FormHelperText>
                          <FormErrorMessage>{t('createTokenModal.errors.invalidRowLimit', 'Row limit must be a positive number.')}</FormErrorMessage>
                      </FormControl>
                   </GridItem>
               </Grid>

               <Divider />

               <FormControl>
                    <FormLabel>{t('createTokenModal.form.allowColumns.label', 'Allowed Columns (Optional)')}</FormLabel>
                    <FormHelperText mb={2}>{t('createTokenModal.form.allowColumnsHelp')}</FormHelperText>
                    {columnsLoading && <Spinner size="sm" />}
                    {columnsError && <ChakraText color="red.500">{columnsError}</ChakraText>}
                    {!columnsLoading && !columnsError && availableColumns.length > 0 && (
                        <VStack align="start" spacing={1} maxHeight="200px" overflowY="auto" borderWidth="1px" borderRadius="md" p={3}>
                            {availableColumns.sort().map(col => (
                                <Checkbox 
                                    key={col}
                                    isChecked={allowColumns.includes(col)}
                                    onChange={(e) => handleAllowColumnChange(col, e.target.checked)}
                                >
                                    {col}
                                </Checkbox>
                            ))}
                        </VStack>
                    )}
               </FormControl>

            </VStack>
          )}
        </ModalBody>

        <ModalFooter>
          {showSuccessView ? (
            <Button onClick={handleCloseAndReset} colorScheme="cyan">
               {t('common.close', 'Close')}
            </Button>
          ) : (
            <>
              <Button variant="ghost" mr={3} onClick={handleCloseAndReset}>
                 {t('common.cancel', 'Cancel')}
              </Button>
              <Button colorScheme="cyan" type="submit" isLoading={isLoading || columnsLoading} isDisabled={isLoading || columnsLoading}>
                 {t('createTokenModal.form.createButton', 'Create Token')}
              </Button>
            </>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default CreateTokenModal;
