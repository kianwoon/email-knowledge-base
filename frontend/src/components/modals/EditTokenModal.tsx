import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  AlertTitle,
  AlertDescription,
  Divider,
  Switch,
  Checkbox,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Spinner,
  FormErrorMessage,
  Grid,
  GridItem,
  Collapse,
  Text as ChakraText,
  useClipboard,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { TokenUpdatePayload, Token, getTokenById, updateToken, TokenType } from '../../api/token';
import { getEmailFactsColumns } from '../../api/schema';
import TagInput from '../inputs/TagInput';

interface EditTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenUpdated: () => void;
  tokenId: number | null;
}

const SENSITIVITY_LEVELS = ["public", "internal", "confidential", "strict-confidential"];
const DEFAULT_ROW_LIMIT = 10000;

const EditTokenModal: React.FC<EditTokenModalProps> = ({ isOpen, onClose, onTokenUpdated, tokenId }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const initialRef = useRef<HTMLInputElement>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [originalToken, setOriginalToken] = useState<Token | null>(null);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]);
  const [expiry, setExpiry] = useState('');
  const [expiryDays, setExpiryDays] = useState<number | string>('');
  const [isActive, setIsActive] = useState(true);
  const [allowRules, setAllowRules] = useState<string[]>([]);
  const [denyRules, setDenyRules] = useState<string[]>([]);

  const [tokenType, setTokenType] = useState<TokenType>(TokenType.PUBLIC);
  const [providerBaseUrl, setProviderBaseUrl] = useState('');
  const [audience, setAudience] = useState('');
  const [allowAttachments, setAllowAttachments] = useState(false);
  const [canExportVectors, setCanExportVectors] = useState(false);
  const [rowLimit, setRowLimit] = useState<number | string>(DEFAULT_ROW_LIMIT);
  const [allowColumns, setAllowColumns] = useState<string[]>([]);

  const [availableColumns, setAvailableColumns] = useState<string[]>([]);
  const [columnsLoading, setColumnsLoading] = useState<boolean>(false);
  const [columnsError, setColumnsError] = useState<string | null>(null);

  const resetForm = useCallback(() => {
    setName('');
    setDescription('');
    setSensitivity(SENSITIVITY_LEVELS[0]);
    setExpiry('');
    setExpiryDays('');
    setIsActive(true);
    setAllowRules([]);
    setDenyRules([]);
    setTokenType(TokenType.PUBLIC);
    setProviderBaseUrl('');
    setAudience('');
    setAllowAttachments(false);
    setCanExportVectors(false);
    setRowLimit(DEFAULT_ROW_LIMIT);
    setAllowColumns([]);
    setError(null);
    setOriginalToken(null);
    setIsLoading(false);
    setIsFetching(false);
    setAvailableColumns([]);
    setColumnsError(null);
    setColumnsLoading(false);
  }, []);

  useEffect(() => {
    if (isOpen && tokenId !== null) {
      const fetchData = async () => {
        setIsFetching(true);
        setColumnsLoading(true);
        setError(null);
        setColumnsError(null);
        setOriginalToken(null);
        try {
          const [tokenData, cols] = await Promise.all([
            getTokenById(String(tokenId)),
            getEmailFactsColumns()
          ]);

          setOriginalToken(tokenData);

          setName(tokenData.name);
          setDescription(tokenData.description || '');
          setSensitivity(tokenData.sensitivity || SENSITIVITY_LEVELS[0]);
          setExpiry(tokenData.expiry ? tokenData.expiry.slice(0, 16) : '');
          setExpiryDays('');
          setIsActive(tokenData.is_active);
          setAllowRules(tokenData.allow_rules || []);
          setDenyRules(tokenData.deny_rules || []);
          setTokenType(tokenData.token_type || TokenType.PUBLIC);
          setProviderBaseUrl(tokenData.provider_base_url || '');
          setAudience(tokenData.audience?.list?.join(', ') || '');
          setAllowAttachments(tokenData.allow_attachments || false);
          setCanExportVectors(tokenData.can_export_vectors || false);
          setRowLimit(tokenData.row_limit ?? DEFAULT_ROW_LIMIT);
          setAllowColumns(tokenData.allow_columns || []);
          
          setAvailableColumns(cols);

        } catch (err: any) {
          console.error("Failed to fetch data:", err);
          setError(t('editTokenModal.errors.fetchFailed', 'Failed to load token data or column schema. Please try again.'));
        } finally {
          setIsFetching(false);
          setColumnsLoading(false);
        }
      };
      fetchData();
    } else {
      resetForm();
    }
  }, [isOpen, tokenId, t, resetForm]);

  const calculateExpiryDays = (expiryString: string): number | null => {
    if (!expiryString) return null;
    try {
      const expiryDate = new Date(expiryString);
      const now = new Date();
      const diffTime = expiryDate.getTime() - now.getTime();
      if (diffTime <= 0) return 0;
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      return diffDays > 0 ? diffDays : null;
    } catch (e) {
      return null;
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (tokenId === null || !originalToken) return;
    setIsLoading(true);
    setError(null);

    const payload: TokenUpdatePayload = {};

    if (name !== originalToken.name) payload.name = name;
    if (description !== (originalToken.description || '')) payload.description = description || undefined;
    if (sensitivity !== originalToken.sensitivity) payload.sensitivity = sensitivity;
    if (isActive !== originalToken.is_active) payload.is_active = isActive;

    const originalExpiryString = originalToken.expiry ? originalToken.expiry.slice(0, 16) : '';
    if (expiry !== originalExpiryString) {
      payload.expiry_days = calculateExpiryDays(expiry);
    }
    
    if (JSON.stringify(allowRules.sort()) !== JSON.stringify((originalToken.allow_rules || []).sort())) {
      payload.allow_rules = allowRules;
    }
    if (JSON.stringify(denyRules.sort()) !== JSON.stringify((originalToken.deny_rules || []).sort())) {
      payload.deny_rules = denyRules;
    }

    if (tokenType === TokenType.SHARE && providerBaseUrl !== (originalToken.provider_base_url || '')) {
      payload.provider_base_url = providerBaseUrl || undefined;
    }
    const currentAudienceString = audience.split(',').map(s => s.trim()).filter(s => s).join(', ');
    const originalAudienceString = originalToken.audience?.list?.join(', ') || '';
    if (currentAudienceString !== originalAudienceString) {
      payload.audience = audience ? { list: currentAudienceString.split(',') } : undefined;
    }
    if (allowAttachments !== originalToken.allow_attachments) payload.allow_attachments = allowAttachments;
    if (canExportVectors !== originalToken.can_export_vectors) payload.can_export_vectors = canExportVectors;

    const numericRowLimit = typeof rowLimit === 'string' ? parseInt(rowLimit, 10) : rowLimit;
    if (isNaN(numericRowLimit) || numericRowLimit < 1) {
      setError(t('createTokenModal.errors.invalidRowLimit', 'Row limit must be a positive number.'));
      setIsLoading(false);
      return;
    }
    if (numericRowLimit !== originalToken.row_limit) payload.row_limit = numericRowLimit;

    if (JSON.stringify(allowColumns.sort()) !== JSON.stringify((originalToken.allow_columns || []).sort())) {
      payload.allow_columns = allowColumns.length > 0 ? allowColumns : undefined;
    }

    if (Object.keys(payload).length === 0) {
      toast({
        title: t('editTokenModal.toast.noChangesTitle', 'No Changes'),
        description: t('editTokenModal.toast.noChangesDescription', 'No changes were detected.'),
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      setIsLoading(false);
      onClose();
      return;
    }

    try {
      await updateToken(String(tokenId), payload);
      toast({
        title: t('editTokenModal.toast.successTitle', 'Token Updated'),
        description: t('editTokenModal.toast.successDescription', { name: name || originalToken.name }),
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
      onTokenUpdated();
      onClose();
    } catch (error: any) {
      console.error(`Token update failed for ${tokenId}:`, error);
      const errorDetail = error?.response?.data?.detail || error.message || t('editTokenModal.toast.errorDescription', 'Could not update token.');
      setError(errorDetail);
      toast({
        title: t('editTokenModal.toast.errorTitle', 'Update Failed'),
        description: errorDetail,
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
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
    <Modal isOpen={isOpen} onClose={onClose} initialFocusRef={initialRef} size="3xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent as={'div'}>
        <ModalHeader>{t('editTokenModal.title', 'Edit Token')}</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          {isFetching || columnsLoading ? (
             <Center h="400px"> <Spinner size="xl" /> </Center>
          ) : error && !originalToken ? (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : originalToken ? (
            <VStack spacing={5} align="stretch">
              {error && (
                <Alert status="error" borderRadius="md">
                  <AlertIcon />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              
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

              <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                <GridItem>
                  <FormControl>
                    <FormLabel>{t('createTokenModal.form.tokenType.label', 'Token Type')}</FormLabel>
                    <Input value={tokenType} isReadOnly variant="filled" />
                  </FormControl>
                </GridItem>
                <GridItem>
                  <Collapse in={tokenType === TokenType.SHARE}>
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
                    <FormLabel>{t('editTokenModal.form.sensitivity.label', 'Sensitivity Level')}</FormLabel>
                    <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}>
                      {SENSITIVITY_LEVELS.map((level) => (
                        <option key={level} value={level}>{level}</option>
                      ))}
                    </Select>
                    <FormHelperText>{t('editTokenModal.form.sensitivity.helper', 'Maximum data sensitivity accessible.')}</FormHelperText>
                  </FormControl>
                </GridItem>
                <GridItem>
                  <FormControl>
                    <FormLabel>{t('editTokenModal.form.expiry.label', 'Expiry Date (Optional)')}</FormLabel>
                    <Input
                      type="datetime-local"
                      value={expiry}
                      onChange={(e) => setExpiry(e.target.value)}
                    />
                    <FormHelperText>{t('editTokenModal.form.expiry.helper', 'Token will become inactive after this date. Clear to remove expiry.')}</FormHelperText>
                  </FormControl>
                </GridItem>
              </Grid>

              <Divider />

              <FormControl>
                <FormLabel>{t('editTokenModal.form.allowRules.label', 'Allow Rules')}</FormLabel>
                <TagInput
                  placeholder={t('editTokenModal.form.allowRules.placeholder', 'Enter allowed rule and press Enter')}
                  value={allowRules}
                  onChange={setAllowRules}
                />
                <FormHelperText>{t('editTokenModal.form.allowRules.helper', 'Data must match ALL these rules.')}</FormHelperText>
              </FormControl>

              <FormControl>
                <FormLabel>{t('editTokenModal.form.denyRules.label', 'Deny Rules')}</FormLabel>
                <TagInput
                  placeholder={t('editTokenModal.form.denyRules.placeholder', 'Enter denied rule and press Enter')}
                  value={denyRules}
                  onChange={setDenyRules}
                />
                <FormHelperText>{t('editTokenModal.form.denyRules.helper', 'Data matching ANY of these rules is excluded.')}</FormHelperText>
              </FormControl>

              <Divider />
              
              <FormControl>
                <FormLabel>{t('createTokenModal.form.audience.label', 'Audience Restrictions (Optional)')}</FormLabel>
                <Input
                  placeholder={t('createTokenModal.form.audience.placeholder', 'e.g., 192.168.1.0/24, example.org')}
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                />
                <FormHelperText>{t('createTokenModal.form.audience.helper', 'Comma-separated IP ranges or domains allowed to use token.')}</FormHelperText>
              </FormControl>
              
              <Divider />

              <Grid templateColumns="repeat(3, 1fr)" gap={6}>
                <GridItem>
                  <FormControl display='flex' alignItems='center'>
                    <Switch 
                      id='allow-attachments-edit'
                      isChecked={allowAttachments} 
                      onChange={(e) => setAllowAttachments(e.target.checked)} 
                      mr={3}
                    />
                    <FormLabel htmlFor='allow-attachments-edit' mb='0'>
                      {t('createTokenModal.form.allowAttachments.label', 'Allow Attachments')}
                    </FormLabel>
                    <FormHelperText mt={1} ml={2}>{t('createTokenModal.form.allowAttachments.helper', 'Allow viewing/exporting file attachments.')}</FormHelperText>
                  </FormControl>
                </GridItem>
                <GridItem>
                  <FormControl display='flex' alignItems='center'>
                    <Switch 
                      id='can-export-vectors-edit'
                      isChecked={canExportVectors} 
                      onChange={(e) => setCanExportVectors(e.target.checked)} 
                      mr={3}
                    />
                    <FormLabel htmlFor='can-export-vectors-edit' mb='0'>
                      {t('createTokenModal.form.canExportVectors.label', 'Allow Vector Export')}
                    </FormLabel>
                    <FormHelperText mt={1} ml={2}>{t('createTokenModal.form.canExportVectors.helper', 'Allow exporting raw vector embeddings.')}</FormHelperText>
                  </FormControl>
                </GridItem>
                <GridItem>
                  <FormControl isInvalid={isNaN(parseInt(String(rowLimit), 10)) || parseInt(String(rowLimit), 10) < 1}>
                    <FormLabel>{t('createTokenModal.form.rowLimit.label', 'Row Limit')}</FormLabel>
                    <NumberInput 
                      min={1} 
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
                    <FormHelperText>{t('createTokenModal.form.rowLimit.helper', 'Max rows per search/export.')}</FormHelperText>
                    <FormErrorMessage>{t('createTokenModal.errors.invalidRowLimit', 'Row limit must be a positive number.')}</FormErrorMessage>
                  </FormControl>
                </GridItem>
              </Grid>

              <Divider />

              <FormControl>
                <FormLabel>{t('createTokenModal.form.allowColumns.label', 'Allowed Columns (Optional)')}</FormLabel>
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
                {!columnsLoading && !columnsError && availableColumns.length === 0 && (
                  <ChakraText fontSize="sm" color="gray.500">{t('editTokenModal.noColumnsAvailable', 'No columns available or failed to load schema.')}</ChakraText>
                )}
                <FormHelperText>
                  {t('createTokenModal.form.allowColumns.helper', 'Select columns allowed in search/export. If none selected, all are allowed (except filtered attachments/vectors).')}
                </FormHelperText>
              </FormControl>

              <Divider />

              <FormControl display="flex" alignItems="center">
                <FormLabel htmlFor="is-active-edit" mb="0">
                  {t('editTokenModal.form.active.label', 'Active')}
                </FormLabel>
                <Switch
                  id="is-active-edit"
                  isChecked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                />
                <FormHelperText ml={2}>{t('editTokenModal.form.active.helper', 'Inactive tokens cannot be used.')}</FormHelperText>
              </FormControl>

            </VStack>
          ) : null}
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button
            colorScheme="cyan"
            onClick={handleSubmit}
            isLoading={isLoading}
            isDisabled={isFetching || columnsLoading || (error && !originalToken) || isLoading}
          >
            {t('common.saveChanges', 'Save Changes')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default EditTokenModal;