import React, { useState } from 'react';
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
  Divider,
  Heading,
  Box
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { createToken, TokenCreate, AccessRule } from '../../api/token';
import RuleInput from './RuleInput';
import RuleDisplay from './RuleDisplay';

// Define sensitivity levels (align with backend if necessary)
const SENSITIVITY_LEVELS = ['low', 'medium', 'high', 'critical'];

interface CreateTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenCreated: () => void; // Callback to refresh the list
}

const CreateTokenModal: React.FC<CreateTokenModalProps> = ({ isOpen, onClose, onTokenCreated }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sensitivity, setSensitivity] = useState(SENSITIVITY_LEVELS[0]);
  const [expiry, setExpiry] = useState('');
  const [isEditable, setIsEditable] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  
  // --- Rule State ---
  const [allowRules, setAllowRules] = useState<AccessRule[]>([]);
  const [denyRules, setDenyRules] = useState<AccessRule[]>([]);

  // --- Rule Handlers ---
  const handleAddRule = (rule: AccessRule, ruleType: 'allow' | 'deny') => {
    if (ruleType === 'allow') {
      if (allowRules.some(existingRule => existingRule.field === rule.field)) {
        toast({
          title: t('tokenModal.rules.duplicateFieldTitle', 'Duplicate Field'),
          description: t('tokenModal.rules.duplicateFieldDescAllow', `An allow rule for the field '${rule.field}' already exists. Remove the existing rule first to change values.`),
          status: 'warning', duration: 4000, isClosable: true,
        });
        return;
      }
      setAllowRules(prev => [...prev, rule]);
    } else {
      if (denyRules.some(existingRule => existingRule.field === rule.field)) {
        toast({
          title: t('tokenModal.rules.duplicateFieldTitle', 'Duplicate Field'),
          description: t('tokenModal.rules.duplicateFieldDescDeny', `A deny rule for the field '${rule.field}' already exists. Remove the existing rule first to change values.`),
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

  // --- Reset State on Close ---
  const handleClose = () => {
    setName('');
    setDescription('');
    setSensitivity(SENSITIVITY_LEVELS[0]);
    setExpiry('');
    setIsEditable(true);
    setAllowRules([]); // Reset rules
    setDenyRules([]);  // Reset rules
    setIsLoading(false);
    onClose(); // Call original onClose
  };

  const handleSubmit = async () => {
    if (!name) {
      toast({
        title: t('common.error', 'Error'),
        description: t('tokenModal.validations.nameRequired', 'Token name is required.'),
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsLoading(true);
    const tokenData: TokenCreate = {
      name,
      description: description || null,
      sensitivity,
      expiry: expiry || null,
      is_editable: isEditable,
      allow_rules: allowRules, // Include rules from state
      deny_rules: denyRules,   // Include rules from state
    };

    try {
      await createToken(tokenData);
      toast({
        title: t('tokenModal.createSuccessTitle', 'Token Created'),
        description: t('tokenModal.createSuccessDesc', `Token "${name}" was successfully created.`),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      onTokenCreated(); // Refresh list in parent component
      handleClose(); // Close and reset modal
    } catch (error: any) {
      console.error("Failed to create token:", error);
      toast({
        title: t('common.error', 'Error'),
        description: error.message || t('tokenModal.errors.createFailed', 'Failed to create token. Please try again.'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsLoading(false); // Keep modal open on error
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="xl"> {/* Consider larger size */}
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{t('tokenModal.createTitle', 'Create New API Token')}</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          <VStack spacing={4} align="stretch">
            {/* --- Basic Info --- */}
            <FormControl isRequired>
              <FormLabel>{t('tokenModal.nameLabel', 'Name')}</FormLabel>
              <Input 
                placeholder={t('tokenModal.namePlaceholder', 'e.g., My Analysis Script')} 
                value={name} 
                onChange={(e) => setName(e.target.value)} 
              />
            </FormControl>
            <FormControl>
              <FormLabel>{t('tokenModal.descriptionLabel', 'Description')}</FormLabel>
              <Textarea 
                placeholder={t('tokenModal.descriptionPlaceholder', 'Optional: Describe what this token is used for')} 
                value={description} 
                onChange={(e) => setDescription(e.target.value)} 
              />
            </FormControl>
            <FormControl>
              <FormLabel>{t('tokenModal.sensitivityLabel', 'Sensitivity Level')}</FormLabel>
              <Select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}>
                {SENSITIVITY_LEVELS.map(level => (
                  <option key={level} value={level}>
                    {t(`tokenModal.sensitivityLevels.${level}`, level.charAt(0).toUpperCase() + level.slice(1))} 
                  </option>
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
                 isChecked={isEditable} 
                 onChange={(e) => setIsEditable(e.target.checked)}
               >
                 {t('tokenModal.editableLabel', 'Allow Editing Rules Later')}
               </Checkbox>
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
                            key={`${rule.field}-${index}`} // Use index for key as rules can change
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
                            key={`${rule.field}-${index}`} // Use index for key
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
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={handleClose} isDisabled={isLoading}>
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button 
            colorScheme="blue" 
            onClick={handleSubmit} 
            isLoading={isLoading}
            loadingText={t('common.saving', 'Saving...')}
          >
            {t('tokenModal.createButton', 'Create Token')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default CreateTokenModal; 