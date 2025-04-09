import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  Button,
  VStack,
  Spinner,
  Alert,
  AlertIcon,
  useColorMode,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  IconButton,
  HStack,
  Tag,
  Center,
  useDisclosure,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useToast,
  Badge,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import PageBanner from '../components/PageBanner';
import { FaPlus, FaEdit, FaTrash } from 'react-icons/fa';
import {
  getUserTokens,
  Token,
  deleteTokenApi
} from '../api/token';
import CreateTokenModal from '../components/modals/CreateTokenModal';
import EditTokenModal from '../components/modals/EditTokenModal';

const TokenManagementPage: React.FC = () => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  const toast = useToast();

  const [tokens, setTokens] = React.useState<Token[]>([]);
  const [isLoading, setIsLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  const { isOpen: isCreateModalOpen, onOpen: onCreateModalOpen, onClose: onCreateModalClose } = useDisclosure();
  const { isOpen: isEditModalOpen, onOpen: onEditModalOpen, onClose: onEditModalClose } = useDisclosure();
  const [editingTokenId, setEditingTokenId] = useState<number | null>(null);
  const { isOpen: isDeleteDialogOpen, onOpen: onDeleteDialogOpen, onClose: onDeleteDialogClose } = useDisclosure();
  const [tokenToDelete, setTokenToDelete] = useState<number | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchUserTokens = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const fetchedTokens = await getUserTokens();
      setTokens(fetchedTokens);
    } catch (err: any) {
      console.error('Failed to fetch tokens:', err);
      setError(t('tokenManagement.errors.loadFailed', 'Failed to load tokens. Please try refreshing the page.'));
    } finally {
      setIsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchUserTokens();
  }, [fetchUserTokens]);

  const handleEditToken = (tokenId: number) => {
    console.log('Requesting edit for token:', tokenId);
    setEditingTokenId(tokenId);
    onEditModalOpen();
  };

  const handleDeleteToken = (tokenId: number) => {
    console.log('Requesting delete for token:', tokenId);
    setTokenToDelete(tokenId);
    onDeleteDialogOpen();
  };

  const confirmDeleteToken = async () => {
    if (tokenToDelete === null) return;
    console.log('Confirming delete for token:', tokenToDelete);
    setIsDeleting(true);
    try {
      await deleteTokenApi(String(tokenToDelete));
      toast({
        title: t('tokenManagementPage.toast.deleteSuccessTitle', 'Token Deleted'),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      fetchUserTokens();
      setTokenToDelete(null);
      onDeleteDialogClose();
    } catch (error: any) {
      console.error('Failed to delete token:', error);
      toast({
        title: t('tokenManagementPage.toast.deleteErrorTitle', 'Deletion Failed'),
        description: error?.response?.data?.detail || error.message || t('tokenManagementPage.toast.deleteErrorDescription', 'Could not delete token.'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString();
    } catch (e) {
      return 'Invalid Date';
    }
  };

  const handleCreateSuccess = () => {
    fetchUserTokens();
  };

  return (
    <Box bg={colorMode === 'dark' ? "gray.900" : "gray.50"} minH="100vh">
      <PageBanner
        title={t('tokenManagement.title', 'Manage API Tokens')}
        subtitle={t('tokenManagementPage.subtitle', 'Create and manage access tokens for sharing knowledge')}
        gradient={colorMode === 'dark' 
          ? "linear(to-r, purple.500, cyan.500)" 
          : "linear(to-r, purple.400, cyan.400)"
        }
      />

      <Container maxW="container.xl" py={8}>
        <VStack spacing={6} align="stretch">
          <Box textAlign="right">
            <Button 
              leftIcon={<FaPlus />} 
              colorScheme="cyan"
              onClick={onCreateModalOpen}
            >
              {t('tokenManagementPage.createTokenButton', 'Create Token')}
            </Button>
          </Box>

          {error && (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              {error}
            </Alert>
          )}

          <Box>
            <Heading size="lg" mb={4}>{t('tokenManagementPage.existingTokensTitle', 'Existing Tokens')}</Heading>
            {isLoading && tokens.length === 0 && !error && (
               <Center py={10}>
                 <Spinner size="xl" />
               </Center>
            )}
            {(!isLoading || tokens.length > 0) && !error && (
                <> 
                  {tokens.length === 0 ? (
                    <Text>{t('tokenManagementPage.noTokens', 'No tokens found. Click Create Token to get started.')}</Text>
                  ) : (
                    <TableContainer>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>{t('tokenManagementPage.table.name', 'Name')}</Th>
                            <Th>{t('tokenManagementPage.table.description', 'Description')}</Th>
                            <Th>{t('tokenManagementPage.table.sensitivity', 'Sensitivity')}</Th>
                            <Th>{t('tokenManagementPage.table.active', 'Active')}</Th>
                            <Th>{t('tokenManagementPage.table.expiry', 'Expiry')}</Th>
                            <Th>{t('tokenManagementPage.table.actions', 'Actions')}</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {tokens.map((token) => (
                            <Tr key={token.id}>
                              <Td>{token.name}</Td>
                              <Td>{token.description || '-'}</Td>
                              <Td><Tag colorScheme="purple">{token.sensitivity}</Tag></Td>
                              <Td>
                                <Badge colorScheme={token.is_active ? 'green' : 'red'}>
                                  {token.is_active ? t('common.active', 'Active') : t('common.inactive', 'Inactive')}
                                </Badge>
                              </Td>
                              <Td>{formatDate(token.expiry)}</Td>
                              <Td>
                                <HStack spacing={2}>
                                  <IconButton
                                    aria-label={t('tokenManagementPage.actions.edit', 'Edit Token')}
                                    icon={<FaEdit />}
                                    size="sm"
                                    onClick={() => handleEditToken(token.id)}
                                    isDisabled={isLoading}
                                  />
                                  <IconButton
                                    aria-label={t('tokenManagementPage.actions.delete', 'Delete Token')}
                                    icon={<FaTrash />}
                                    size="sm"
                                    colorScheme="red"
                                    onClick={() => handleDeleteToken(token.id)}
                                    isDisabled={isLoading}
                                  />
                                </HStack>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </TableContainer>
                  )}
                </>
            )}
          </Box>
        </VStack>
      </Container>

      <CreateTokenModal 
        isOpen={isCreateModalOpen} 
        onClose={onCreateModalClose} 
        onTokenCreated={handleCreateSuccess}
      />

      <EditTokenModal 
        isOpen={isEditModalOpen}
        onClose={() => { 
            onEditModalClose(); 
            setEditingTokenId(null);
        }}
        onTokenUpdated={() => {
            onEditModalClose();
            setEditingTokenId(null);
            fetchUserTokens();
        }}
        tokenId={editingTokenId}
      />

      <AlertDialog
        isOpen={isDeleteDialogOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteDialogClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('tokenManagementPage.deleteDialog.title', 'Delete Token')}
            </AlertDialogHeader>

            <AlertDialogBody>
              {t('tokenManagementPage.deleteDialog.message', 'Are you sure you want to delete this token? This action cannot be undone.')}
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteDialogClose}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button 
                colorScheme="red" 
                onClick={confirmDeleteToken} 
                ml={3}
                isLoading={isDeleting}
              >
                {t('common.delete', 'Delete')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default TokenManagementPage; 