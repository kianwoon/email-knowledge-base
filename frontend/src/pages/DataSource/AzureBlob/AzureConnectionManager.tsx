import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box,
    Button,
    FormControl,
    FormLabel,
    Input,
    VStack,
    HStack,
    Text,
    Spinner,
    useToast,
    Heading,
    useDisclosure,
    AlertDialog,
    AlertDialogBody,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogContent,
    AlertDialogOverlay,
    InputGroup,
    InputRightElement,
    useColorModeValue,
    FormErrorMessage,
    FormHelperText,
    Center,
    Textarea,
} from '@chakra-ui/react';
import { DeleteIcon, CheckIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';
import { getAzureConnections, createAzureConnection, deleteAzureConnection, AzureConnection } from '../../../api/azure';

interface AzureConnectionManagerProps {
    onConnectionsChange: () => void;
}

interface AzureConnectionFormProps {
    onCreate: (data: { 
        name: string; 
        accountName: string;
        credentials: string;
    }) => void;
    isLoading: boolean;
    existingConnections: AzureConnection[];
}

const AzureConnectionForm: React.FC<AzureConnectionFormProps> = ({ onCreate, isLoading, existingConnections }) => {
    const { t } = useTranslation();
    const [name, setName] = useState('');
    const [accountName, setAccountName] = useState('');
    const [connectionString, setConnectionString] = useState('');
    const [nameError, setNameError] = useState<string | null>(null);

    const validateInput = () => {
        let isValid = true;
        setNameError(null);

        if (!name.trim()) {
            setNameError(t('common.validation.required'));
            isValid = false;
        }
        if (existingConnections.some(conn => conn.name.toLowerCase() === name.trim().toLowerCase())) {
            setNameError(t('azureConnectionManager.errors.duplicateName', 'Connection name must be unique.'));
            isValid = false;
        }

        if (!connectionString.trim()) {
            isValid = false;
        }

        return isValid;
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!validateInput()) {
            toast({ title: t('common.validation.checkFields'), status: 'warning' });
            return;
        }
        onCreate({ 
            name: name.trim(), 
            accountName: accountName.trim(),
            credentials: connectionString.trim(),
        });
        setName('');
        setAccountName('');
        setConnectionString('');
    };

    const toast = useToast();
    const bgColor = useColorModeValue('gray.50', 'gray.700');

    return (
        <Box as="form" onSubmit={handleSubmit} p={4} borderWidth="1px" borderRadius="md" bg={bgColor} shadow="sm">
            <VStack spacing={4} align="stretch">
                <Heading size="sm" mb={2}>{t('azureConnectionManager.newConnection', 'New Azure Connection')}</Heading>
                <Text fontSize="sm" mb={4}>
                    {t('azureConnectionManager.newConnectionDesc', 'Add a new Azure Storage connection by providing the required details below.')}
                </Text>
                <FormControl isRequired isInvalid={!!nameError}>
                    <FormLabel htmlFor='connection-name'>{t('azureConnectionManager.connectionNameLabel', 'Connection Name')}</FormLabel>
                    <Input
                        id='connection-name'
                        placeholder={t('azureConnectionManager.connectionNamePlaceholder', 'e.g., My Production Storage')}
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                    />
                    {nameError && <FormErrorMessage>{nameError}</FormErrorMessage>}
                </FormControl>

                <FormControl isRequired>
                    <FormLabel htmlFor='account-name'>{t('azureConnectionManager.accountNameLabel', 'Account Name')}</FormLabel>
                    <Input
                        id='account-name'
                        placeholder={t('azureConnectionManager.accountNamePlaceholder', 'yourstorageaccount')}
                        value={accountName}
                        onChange={(e) => setAccountName(e.target.value)}
                    />
                </FormControl>

                <FormControl isRequired>
                    <FormLabel htmlFor='connection-string'>{t('azureConnectionManager.credentialsLabel', 'Connection String')}</FormLabel>
                    <Textarea
                        id='connection-string'
                        placeholder={t('azureConnectionManager.credentialsPlaceholder', 'Enter full connection string')}
                        value={connectionString}
                        onChange={(e) => setConnectionString(e.target.value)}
                        rows={3}
                    />
                    <FormHelperText>
                        {t('azureConnectionManager.credentialsNote', 'Your connection string will be stored securely.')}
                    </FormHelperText>
                </FormControl>

                <Button
                    type="submit"
                    isLoading={isLoading}
                    colorScheme="blue"
                    alignSelf="flex-end"
                    isDisabled={!name || !accountName || !connectionString || isLoading}
                >
                    {t('common.add', 'Add Connection')}
                </Button>
            </VStack>
        </Box>
    );
};

const AzureConnectionManager: React.FC<AzureConnectionManagerProps> = ({ onConnectionsChange }) => {
    const { t } = useTranslation();
    const toast = useToast();
    const { isOpen: isDeleteAlertOpen, onOpen: onDeleteAlertOpen, onClose: onDeleteAlertClose } = useDisclosure();
    const cancelRef = useRef<HTMLButtonElement>(null);

    const [connections, setConnections] = useState<AzureConnection[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [connectionToDelete, setConnectionToDelete] = useState<AzureConnection | null>(null);

    const loadConnections = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await getAzureConnections();
            setConnections(data);
        } catch (err: any) {
            setError(t('azureConnectionManager.errors.loadFailed'));
            toast({ title: t('errors.error'), description: t('azureConnectionManager.errors.loadFailed'), status: 'error' });
        } finally {
            setIsLoading(false);
        }
    }, [t, toast]);

    useEffect(() => {
        loadConnections();
    }, [loadConnections]);

    const handleCreateConnection = async (connectionData: { 
        name: string; 
        accountName: string;
        credentials: string;
    }) => {
        setIsProcessing(true);
        setError(null);
        try {
            const payload = { 
                name: connectionData.name, 
                account_name: connectionData.accountName,
                credentials: connectionData.credentials,
            };
            await createAzureConnection(payload);
            toast({ title: t('common.success'), description: t('azureConnectionManager.addSuccess'), status: 'success' });
            loadConnections();
            onConnectionsChange();
        } catch (err: any) {
            setError(err.message || t('azureConnectionManager.errors.addFailed'));
            toast({ title: t('errors.error'), description: err.message || t('azureConnectionManager.errors.addFailed'), status: 'error' });
        } finally {
            setIsProcessing(false);
        }
    };

    const openDeleteConfirm = (connection: AzureConnection) => {
        setConnectionToDelete(connection);
        onDeleteAlertOpen();
    };

    const handleDeleteConnection = async () => {
        if (!connectionToDelete) return;

        setIsProcessing(true);
        setError(null);
        try {
            await deleteAzureConnection(connectionToDelete.id);
            toast({ title: t('azureConnectionManager.deleteSuccess'), status: 'success' });
            setConnections(prev => prev.filter(c => c.id !== connectionToDelete!.id));
            setConnectionToDelete(null);
            onConnectionsChange();
            onDeleteAlertClose();
        } catch (err: any) {
            setError(t('azureConnectionManager.errors.deleteFailed') + `: ${err.message}`);
            toast({ title: t('errors.error'), description: t('azureConnectionManager.errors.deleteFailed'), status: 'error' });
            onDeleteAlertClose();
        } finally {
            setIsProcessing(false);
        }
    };

    const listBgColor = useColorModeValue('gray.100', 'gray.700');

    return (
        <Box>
            <Heading size="md" mb={4}>{t('azureConnectionManager.title', 'Azure Storage Settings')}</Heading>
            <Text mb={4}>{t('azureConnectionManager.descriptionV2', 'Configure connections using the full Connection String from Azure.')}</Text>

            {isLoading && <Center my={4}><Spinner /></Center>}
            {error && <Text color="red.500" mb={4}>{error}</Text>}

            <AzureConnectionForm onCreate={handleCreateConnection} isLoading={isProcessing} existingConnections={connections} />

            {/* Existing Connections */}
            {connections.length > 0 && (
                <Box p={4} borderWidth="1px" borderRadius="md">
                    <Heading size="sm" mb={2}>{t('azureConnectionManager.existingConnections', 'Existing Connections')}</Heading>
                    <Text fontSize="sm" mb={4}>
                        {t('azureConnectionManager.existingConnectionsDesc', 'Manage your existing Azure Storage connections.')}
                    </Text>

                    <VStack spacing={4} align="stretch">
                        {connections.map((conn) => (
                            <Box
                                key={conn.id}
                                p={3}
                                borderWidth="1px"
                                borderRadius="md"
                                borderColor={useColorModeValue('gray.200', 'gray.600')}
                            >
                                <HStack justify="space-between">
                                    <VStack align="start" spacing={1}>
                                        <Text fontWeight="bold">{conn.name}</Text>
                                        <Text fontSize="sm" color="gray.500">Account: {conn.account_name}</Text>
                                    </VStack>
                                    <Button
                                        leftIcon={<DeleteIcon />}
                                        colorScheme="red"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => openDeleteConfirm(conn)}
                                        isLoading={isProcessing && connectionToDelete?.id === conn.id}
                                    >
                                        {t('common.delete')}
                                    </Button>
                                </HStack>
                            </Box>
                        ))}
                    </VStack>
                </Box>
            )}

            {/* Delete Confirmation Dialog */}
            <AlertDialog
                isOpen={isDeleteAlertOpen}
                leastDestructiveRef={cancelRef}
                onClose={onDeleteAlertClose}
            >
                <AlertDialogOverlay>
                    <AlertDialogContent>
                        <AlertDialogHeader fontSize="lg" fontWeight="bold">
                            {t('azureConnectionManager.deleteConfirmTitle', 'Delete Connection')}
                        </AlertDialogHeader>
                        <AlertDialogBody>
                            {t('azureConnectionManager.deleteConfirmMsg', 'Are you sure you want to delete the connection ')}
                            <strong>{connectionToDelete?.name}</strong>?
                            {t('common.cannotBeUndone')}
                        </AlertDialogBody>
                        <AlertDialogFooter>
                            <Button ref={cancelRef} onClick={onDeleteAlertClose}>
                                {t('common.cancel')}
                            </Button>
                            <Button colorScheme="red" onClick={handleDeleteConnection} ml={3} isLoading={isProcessing}>
                                {t('common.delete')}
                            </Button>
                        </AlertDialogFooter>
                    </AlertDialogContent>
                </AlertDialogOverlay>
            </AlertDialog>
        </Box>
    );
};

export default AzureConnectionManager; 