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
  Checkbox,
  VStack,
  useToast,
  Text as ChakraText,
  Divider,
  IconButton,
  HStack,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { TokenCreate, createToken, AccessRule } from '../../api/token'; // Import API function and type
import { FaPlus, FaTrash } from 'react-icons/fa'; // Added icons
import TagInput from '../inputs/TagInput'; // Import the new TagInput component

// Define props for the modal
interface CreateTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenCreated: () => void; // Callback to refresh list on parent page
}

// TODO: Get these from backend or config
const SENSITIVITY_LEVELS = ["public", "internal", "confidential", "strict-confidential"];

const CreateTokenModal: React.FC<CreateTokenModalProps> = ({ isOpen, onClose, onTokenCreated }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]); // Default sensitivity
  const [expiry, setExpiry] = useState(''); // Use string for datetime-local input
  const [isEditable, setIsEditable] = useState(true);
  // State for rules
  const [allowRules, setAllowRules] = useState<AccessRule[]>([]);
  const [denyRules, setDenyRules] = useState<AccessRule[]>([]);

  // --- Functions to manage rules state --- 
  const addRule = (type: 'allow' | 'deny') => {
    const newRule: AccessRule = { field: '', values: [] };
    if (type === 'allow') {
      setAllowRules([...allowRules, newRule]);
    } else {
      setDenyRules([...denyRules, newRule]);
    }
  };

  // Simplified updateRule for TagInput
  const updateRule = (index: number, field: keyof AccessRule, value: string | string[], type: 'allow' | 'deny') => {
    const rules = type === 'allow' ? allowRules : denyRules;
    const setRules = type === 'allow' ? setAllowRules : setDenyRules;
    const updatedRules = [...rules];

    // Direct assignment for field, TagInput handles values array
    updatedRules[index] = { ...updatedRules[index], [field]: value };

    setRules(updatedRules);
  };

  const removeRule = (index: number, type: 'allow' | 'deny') => {
    const rules = type === 'allow' ? allowRules : denyRules;
    const setRules = type === 'allow' ? setAllowRules : setDenyRules;
    setRules(rules.filter((_, i) => i !== index));
  };
  // --- End rule management functions ---

  const resetForm = () => {
    setName('');
    setDescription('');
    setSensitivity(SENSITIVITY_LEVELS[0]);
    setExpiry('');
    setIsEditable(true);
    // Reset rules
    setAllowRules([]); 
    setDenyRules([]); 
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsLoading(true);

    const tokenData: TokenCreate = {
      name,
      description: description || null,
      sensitivity,
      expiry: expiry ? new Date(expiry).toISOString() : null, // Convert to ISO string or null
      is_editable: isEditable,
      // Include rules from state
      allow_rules: allowRules.filter(rule => rule.field && rule.values.length > 0), // Filter out incomplete rules
      deny_rules: denyRules.filter(rule => rule.field && rule.values.length > 0),   // Filter out incomplete rules
    };

    try {
      await createToken(tokenData);
      toast({
        title: t('createTokenModal.toast.successTitle', 'Token Created'),
        description: t('createTokenModal.toast.successDescription', `Token "${name}" was successfully created.`),        status: 'success',
        duration: 5000,
        isClosable: true,
      });
      resetForm();
      onTokenCreated(); // Trigger list refresh
      onClose(); // Close modal
    } catch (error: any) {
      console.error("Token creation failed:", error);
      toast({
        title: t('createTokenModal.toast.errorTitle', 'Creation Failed'),
        description: error?.response?.data?.detail || error.message || t('createTokenModal.toast.errorDescription', 'Could not create token.'),
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent as="form" onSubmit={handleSubmit}>
        <ModalHeader>{t('createTokenModal.title', 'Create New Access Token')}</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
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
                {SENSITIVITY_LEVELS.map(level => (
                  <option key={level} value={level}>{level}</option>
                ))}
              </Select>
              <FormHelperText>{t('createTokenModal.form.sensitivity.helper', 'Determines the maximum data sensitivity accessible.')}</FormHelperText>
            </FormControl>

            {/* --- Allow Rules Section --- */}
            <FormControl>
              <FormLabel>{t('createTokenModal.form.allowRules.label', 'Allow Rules (Require ALL)')}</FormLabel>
              <VStack align="stretch" spacing={2} pl={2} borderLeft="2px" borderColor="green.200">
                {allowRules.map((rule, index) => (
                  <HStack key={`allow-${index}`} spacing={2} align="flex-start"> {/* Align items to top */} 
                    <Input 
                      placeholder={t('createTokenModal.form.rules.fieldPlaceholder', 'Metadata Field')} 
                      value={rule.field}
                      onChange={(e) => updateRule(index, 'field', e.target.value, 'allow')}
                      size="sm"
                      flexShrink={0} // Prevent field input from shrinking too much
                      w="150px" // Give field input a fixed width
                    />
                    {/* Use TagInput for values */}
                    <TagInput 
                      placeholder={t('createTokenModal.form.rules.valuesPlaceholder', 'Allowed Values (Enter)')} 
                      value={rule.values}
                      onChange={(newValues) => updateRule(index, 'values', newValues, 'allow')}
                      size="sm"
                    />
                    <IconButton 
                      aria-label={t('createTokenModal.form.rules.removeRule', 'Remove Rule')} 
                      icon={<FaTrash />} 
                      size="sm"
                      variant="ghost"
                      colorScheme="red"
                      onClick={() => removeRule(index, 'allow')}
                      alignSelf="center" // Center remove button vertically
                    />
                  </HStack>
                ))}
                <Button 
                  leftIcon={<FaPlus />} 
                  size="sm" 
                  variant="outline"
                  onClick={() => addRule('allow')}
                >
                  {t('createTokenModal.form.rules.addAllowRule', 'Add Allow Rule')}
                </Button>
              </VStack>
              <FormHelperText>{t('createTokenModal.form.allowRules.helper', 'Data must match ALL allow rules defined.')}</FormHelperText>
            </FormControl>
            
            <Divider />

            {/* --- Deny Rules Section --- */}
            <FormControl>
              <FormLabel>{t('createTokenModal.form.denyRules.label', 'Deny Rules (Require ANY)')}</FormLabel>
              <VStack align="stretch" spacing={2} pl={2} borderLeft="2px" borderColor="red.200">
                {denyRules.map((rule, index) => (
                   <HStack key={`deny-${index}`} spacing={2} align="flex-start"> {/* Align items to top */}
                    <Input 
                      placeholder={t('createTokenModal.form.rules.fieldPlaceholder', 'Metadata Field')} 
                      value={rule.field}
                      onChange={(e) => updateRule(index, 'field', e.target.value, 'deny')}
                      size="sm"
                      flexShrink={0}
                      w="150px"
                    />
                    {/* Use TagInput for values */}
                    <TagInput 
                      placeholder={t('createTokenModal.form.rules.valuesPlaceholder', 'Denied Values (Enter)')} 
                      value={rule.values}
                      onChange={(newValues) => updateRule(index, 'values', newValues, 'deny')}
                      size="sm"
                    />
                    <IconButton 
                      aria-label={t('createTokenModal.form.rules.removeRule', 'Remove Rule')} 
                      icon={<FaTrash />} 
                      size="sm"
                      variant="ghost"
                      colorScheme="red"
                      onClick={() => removeRule(index, 'deny')}
                      alignSelf="center" // Center remove button vertically
                    />
                  </HStack>
                ))}
                <Button 
                  leftIcon={<FaPlus />} 
                  size="sm" 
                  variant="outline"
                  onClick={() => addRule('deny')}
                >
                  {t('createTokenModal.form.rules.addDenyRule', 'Add Deny Rule')}
                </Button>
              </VStack>
               <FormHelperText>{t('createTokenModal.form.denyRules.helper', 'Data matching ANY deny rule defined will be excluded.')}</FormHelperText>
            </FormControl>
            
            <Divider />

            <FormControl>
              <FormLabel>{t('createTokenModal.form.expiry.label', 'Expiry Date (Optional)')}</FormLabel>
              <Input 
                type="datetime-local"
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
              />
              <FormHelperText>{t('createTokenModal.form.expiry.helper', 'Token will automatically become invalid after this date.')}</FormHelperText>
            </FormControl>

            <FormControl>
              <Checkbox isChecked={isEditable} onChange={(e) => setIsEditable(e.target.checked)}>
                {t('createTokenModal.form.editable.label', 'Editable after creation')}
              </Checkbox>
              <FormHelperText>{t('createTokenModal.form.editable.helper', 'If unchecked, the token configuration cannot be changed later.')}</FormHelperText>
            </FormControl>

          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button onClick={onClose} mr={3}>{t('common.cancel', 'Cancel')}</Button>
          <Button 
            colorScheme="cyan" 
            type="submit"
            isLoading={isLoading}
          >
            {t('createTokenModal.submitButton', 'Create Token')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default CreateTokenModal; 