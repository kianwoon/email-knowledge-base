import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  Input,
  InputGroup,
  InputLeftElement,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  InputRightElement,
  useColorModeValue,
  Code,
  Icon,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import PageBanner from '../components/PageBanner';
import { FaPlus, FaEdit, FaTrash, FaSearch, FaPlay, FaInfoCircle, FaListAlt, FaListUl } from 'react-icons/fa';
import {
  getUserTokens,
  Token,
  deleteTokenApi,
  regenerateTokenSecret
} from '../api/token';
import CreateTokenModal from '../components/modals/CreateTokenModal';
import EditTokenModal from '../components/modals/EditTokenModal';
import TestTokenModal from '../components/modals/TestTokenModal';
import { EditIcon, DeleteIcon, CheckIcon, CopyIcon, RepeatIcon } from '@chakra-ui/icons';
import {
  ColumnDef,
  Row,
  CellContext,
  flexRender,
  getCoreRowModel,
  useReactTable,
  RowData,
} from '@tanstack/react-table';

// Define an inline DataTable component
function DataTable<TData extends RowData>({ data, columns }: { data: TData[]; columns: ColumnDef<TData, any>[] }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const headerBg = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  return (
    <Box borderWidth="1px" borderRadius="md" borderColor={borderColor} overflowX="auto">
      <TableContainer>
        <Table variant="simple">
          <Thead bg={headerBg}>
            {table.getHeaderGroups().map((headerGroup) => (
              <Tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <Th key={header.id} colSpan={header.colSpan}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </Th>
                ))}
              </Tr>
            ))}
          </Thead>
          <Tbody>
            {table.getRowModel().rows.map((row) => (
              <Tr key={row.id} _hover={{ bg: hoverBg }}>
                {row.getVisibleCells().map((cell) => (
                  <Td key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </Td>
                ))}
              </Tr>
            ))}
            {table.getRowModel().rows.length === 0 && (
              <Tr>
                <Td colSpan={columns.length} textAlign="center">
                  No data available.
                </Td>
              </Tr>
            )}
          </Tbody>
        </Table>
      </TableContainer>
    </Box>
  );
}

const TokenManagementPage: React.FC = () => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  const toast = useToast();

  const [tokens, setTokens] = useState<Token[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const { isOpen: isCreateModalOpen, onOpen: onCreateModalOpen, onClose: onCreateModalClose } = useDisclosure();
  const { isOpen: isEditModalOpen, onOpen: onEditModalOpen, onClose: onEditModalClose } = useDisclosure();
  const [editingTokenId, setEditingTokenId] = useState<number | null>(null);
  const { isOpen: isDeleteDialogOpen, onOpen: onDeleteDialogOpen, onClose: onDeleteDialogClose } = useDisclosure();
  const [tokenToDelete, setTokenToDelete] = useState<number | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const { isOpen: isTestModalOpen, onOpen: onTestModalOpen, onClose: onTestModalClose } = useDisclosure();
  const [testingTokenId, setTestingTokenId] = useState<number | null>(null);
  const [testingTokenName, setTestingTokenName] = useState<string>('');

  const { 
      isOpen: isRegenerateConfirmOpen, 
      onOpen: onRegenerateConfirmOpen, 
      onClose: onRegenerateConfirmClose 
  } = useDisclosure();
  const [tokenToRegenerate, setTokenToRegenerate] = useState<Token | null>(null);
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);
  
  const { 
      isOpen: isNewTokenModalOpen, 
      onOpen: onNewTokenModalOpen, 
      onClose: onNewTokenModalClose 
  } = useDisclosure();
  const [regeneratedTokenValue, setRegeneratedTokenValue] = useState<string>('');

  const fetchUserTokens = useCallback(async () => {
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
    setEditingTokenId(tokenId);
    onEditModalOpen();
  };

  const handleDeleteToken = (tokenId: number) => {
    setTokenToDelete(tokenId);
    onDeleteDialogOpen();
  };

  const handleTestToken = (tokenId: number, tokenName: string) => {
    setTestingTokenId(tokenId);
    setTestingTokenName(tokenName || '');
    onTestModalOpen();
  };

  const confirmDeleteToken = async () => {
    if (tokenToDelete === null) return;
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

  const filteredTokens = tokens.filter(token =>
    token.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (token.description || '').toLowerCase().includes(searchTerm.toLowerCase())
  );
  const activeTokens = filteredTokens.filter(token => token.is_active);
  const inactiveTokens = filteredTokens.filter(token => !token.is_active);

  const handleRegenerateClick = (token: Token) => {
    setTokenToRegenerate(token);
    onRegenerateConfirmOpen();
  };

  const confirmRegenerate = async () => {
    if (!tokenToRegenerate) return;
    setIsRegenerating(true);
    try {
      const response = await regenerateTokenSecret(tokenToRegenerate.id);
      setRegeneratedTokenValue(response.new_token_value);
      onNewTokenModalOpen();
      const tokenName = tokenToRegenerate.name || '';
      toast({
        title: t('tokenManagementPage.regenerateSuccess.title', 'Secret Regenerated'), 
        description: t('tokenManagementPage.regenerateSuccess.description', 'New secret generated for token "{{name}}". Copy the new value now.', { name: tokenName }), 
        status: 'success', 
        duration: 5000, 
        isClosable: true
      });
    } catch (error: any) {
      toast({
        title: t('common.error', 'Regeneration Failed'), 
        description: error.message || t('tokenManagementPage.regenerateError', 'Could not regenerate token secret.'), 
        status: 'error', 
        duration: 5000, 
        isClosable: true
      });
    } finally {
      setIsRegenerating(false);
      setTokenToRegenerate(null);
      onRegenerateConfirmClose();
    }
  };

  const columns = useMemo<ColumnDef<Token>[]>(() => [
    {
      header: t('tokenManagementPage.table.name', 'Name'),
      accessorKey: 'name',
    },
    {
      header: t('tokenManagementPage.table.description', 'Description'),
      accessorKey: 'description',
      cell: (info: CellContext<Token, unknown>) => (info.getValue() as string || '-'),
    },
    {
      header: t('tokenManagementPage.table.sensitivity', 'Sensitivity'),
      accessorKey: 'sensitivity',
      cell: (info: CellContext<Token, unknown>) => {
        const value = info.getValue() as string | null;
        return value ? (<Tag colorScheme="purple">{value}</Tag>) : '-';
      }
    },
    {
        header: t('tokenManagementPage.table.status', 'Status'),
        accessorKey: 'is_active',
        cell: (info: CellContext<Token, unknown>) => {
          const isActive = info.getValue() as boolean;
          return (
            <Badge colorScheme={isActive ? 'green' : 'red'}>
                {isActive ? t('common.active', 'Active') : t('common.inactive', 'Inactive')}
            </Badge>
          )
        }
    },
    {
        header: t('tokenManagementPage.table.expiry', 'Expiry'),
        accessorKey: 'expiry',
        cell: (info: CellContext<Token, unknown>) => formatDate(info.getValue() as string | null | undefined),
    },
    {
      header: t('tokenManagement.table.actions', 'Actions'),
      id: 'actions',
      cell: ({ row }: { row: Row<Token> }) => (
        <HStack spacing={2}>
          <IconButton
            aria-label={t('tokenManagementPage.actions.test', 'Test Token')}
            icon={<FaPlay />}
            size="sm"
            onClick={() => handleTestToken(row.original.id, row.original.name)}
            isDisabled={isLoading}
            colorScheme="blue"
            variant="ghost"
            title={t('tokenManagementPage.actions.test', 'Test Token')}
          />
          <IconButton
            aria-label={t('tokenManagementPage.actions.edit', 'Edit Token')}
            icon={<FaEdit />}
            size="sm"
            onClick={() => handleEditToken(row.original.id)}
            isDisabled={isLoading}
            variant="ghost"
            title={t('tokenManagementPage.actions.edit', 'Edit Token')}
          />
          {row.original.is_editable && (
            <IconButton
              aria-label={t('tokenManagementPage.actions.regenerate', 'Regenerate Secret')}
              icon={<RepeatIcon />}
              size="sm"
              variant="ghost"
              colorScheme="orange"
              onClick={() => handleRegenerateClick(row.original)}
              isLoading={isRegenerating && tokenToRegenerate?.id === row.original.id}
              title={t('tokenManagementPage.actions.regenerate', 'Regenerate Secret')}
            />
          )}
          <IconButton
            aria-label={t('tokenManagementPage.actions.delete', 'Delete Token')}
            icon={<FaTrash />}
            size="sm"
            colorScheme="red"
            onClick={() => handleDeleteToken(row.original.id)}
            isDisabled={isLoading}
            variant="ghost"
            title={t('tokenManagementPage.actions.delete', 'Delete Token')}
          />
        </HStack>
      ),
    },
  ], [t, handleDeleteToken, handleEditToken, handleTestToken, handleRegenerateClick, isRegenerating, tokenToRegenerate]);

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
          <HStack justify="space-between" spacing={4} mb={2}>
            <InputGroup maxW={{ base: "100%", md: "400px" }}>
                <InputLeftElement pointerEvents="none">
                  <FaSearch color="gray.300" />
                </InputLeftElement>
                <Input 
                  placeholder={t('tokenManagementPage.searchPlaceholder', 'Search by name or description...')} 
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  bg={colorMode === 'dark' ? 'gray.700' : 'white'}
                />
            </InputGroup>
            <Button
                leftIcon={<FaPlus />}
                colorScheme="cyan"
                onClick={onCreateModalOpen}
                isDisabled={isLoading}
              >
                {t('tokenManagementPage.createTokenButton', 'Create Token')}
            </Button>
          </HStack>

          {error && (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              {error}
            </Alert>
          )}

          {isLoading && tokens.length === 0 && !error && (
            <Center py={10}>
              <Spinner size="xl" />
            </Center>
          )}

          {(!isLoading || tokens.length > 0) && !error && (
            <Box>
              <Tabs variant="soft-rounded" colorScheme="blue">
                <TabList mb="1em">
                  <Tab>
                    <Icon as={FaListAlt} mr={2} />
                    {t('tokenManagementPage.tabs.active', 'Active')} 
                    ({activeTokens.length}{searchTerm ? ` / ${tokens.filter(t => t.is_active).length}` : ''})
                  </Tab>
                  <Tab>
                    <Icon as={FaListUl} mr={2} />
                    {t('tokenManagementPage.tabs.inactive', 'Inactive')} 
                    ({inactiveTokens.length}{searchTerm ? ` / ${tokens.filter(t => !t.is_active).length}` : ''})
                  </Tab>
                  <Tab>
                    <Icon as={FaInfoCircle} mr={2} />
                    {t('tokenManagementPage.tabs.guide', 'Guide')}
                  </Tab>
                </TabList>
                <TabPanels>
                  <TabPanel p={0}>
                    {activeTokens.length === 0 ? (
                      <Text>{searchTerm 
                        ? t('tokenManagementPage.noActiveTokensSearch', 'No active tokens found matching your search.') 
                        : t('tokenManagementPage.noActiveTokens', 'No active tokens found.')}
                      </Text>
                    ) : (
                      <DataTable columns={columns} data={activeTokens} />
                    )}
                  </TabPanel>

                  <TabPanel p={0}>
                    {inactiveTokens.length === 0 ? (
                      <Text>{searchTerm
                        ? t('tokenManagementPage.noInactiveTokensSearch', 'No inactive tokens found matching your search.')
                        : t('tokenManagementPage.noInactiveTokens', 'No inactive tokens found.')}
                      </Text>
                    ) : (
                      <DataTable columns={columns} data={inactiveTokens} />
                    )}
                  </TabPanel>
                  
                  <TabPanel>
                    <Heading size="lg" mb={4}>{t('tokenManagementPage.guide.title', 'How to Use API Tokens')}</Heading>
                    <VStack spacing={5} align="stretch">
                        <Text fontSize="md">{t('tokenManagementPage.guide.introduction', 'Tokens allow external applications to securely query your knowledge base via a dedicated API endpoint.')}</Text>
                        
                        <Box>
                            <Heading size="md" mb={2}>{t('tokenManagementPage.guide.endpointTitle', 'API Endpoint')}</Heading>
                            <Text mb={1}>{t('tokenManagementPage.guide.endpointPath', 'The endpoint for querying shared knowledge is:')}</Text>
                            <Code p={2} borderRadius="md" width="100%">{t('tokenManagementPage.guide.endpointValue', 'POST /api/v1/shared-knowledge/search')}</Code>
                        </Box>

                        <Box>
                            <Heading size="md" mb={2}>{t('tokenManagementPage.guide.usageTitle', 'Authentication')}</Heading>
                            <Text mb={1}>{t('tokenManagementPage.guide.usageInstructions', 'To authenticate your request, include the generated token (prefix + secret, separated by a dot) as a Bearer token in the Authorization header:')}</Text>
                            <Code p={2} borderRadius="md" width="100%">{t('tokenManagementPage.guide.usageValue', 'Authorization: Bearer YOUR_PREFIX.YOUR_SECRET')}</Code>
                        </Box>

                        <Box>
                            <Heading size="md" mb={2}>{t('tokenManagementPage.guide.requestBodyTitle', 'Request Body')}</Heading>
                            <Text mb={1}>{t('tokenManagementPage.guide.requestBodyInstructions', 'Send a JSON object in the request body with the following fields:')}</Text>
                            <Code p={2} borderRadius="md" display="block" whiteSpace="pre-wrap">
                                {t('tokenManagementPage.guide.requestBodyValue', 
`{
  "query": "your search query here",
  "limit": 10
}`)}
                            </Code>
                            <Text fontSize="sm" mt={1}>{t('tokenManagementPage.guide.requestBodyNote', 'The `query` field is required. The `limit` field is optional (default: 10).')}</Text>
                        </Box>
                        
                        <Box>
                            <Heading size="md" mb={2}>{t('tokenManagementPage.guide.curlExampleTitle', 'Example cURL Request')}</Heading>
                             <Text mb={1}>{t('tokenManagementPage.guide.curlExampleNote', 'Use -X POST and -d for the JSON body:')}</Text>
                            <Code p={2} borderRadius="md" display="block" whiteSpace="pre-wrap">
                              {t('tokenManagementPage.guide.curlExampleValue', 
`curl -X POST YOUR_API_BASE_URL/api/v1/shared-knowledge/search \ 
  -H "Authorization: Bearer YOUR_PREFIX.YOUR_SECRET" \ 
  -H "Content-Type: application/json" \ 
  -d '{ "query": "What were the key decisions made last quarter?", "limit": 10 }'`)}
                            </Code>
                             <Text fontSize="sm" mt={1}>{t('tokenManagementPage.guide.curlReplaceNote', 'Replace `YOUR_API_BASE_URL` with the actual base URL of the application and `YOUR_PREFIX.YOUR_SECRET` with your token.')}</Text>
                        </Box>

                        <Box>
                            <Heading size="md" mb={2}>{t('tokenManagementPage.guide.responseFormatTitle', 'Response Format')}</Heading>
                            <Text mb={1}>{t('tokenManagementPage.guide.responseFormatInstructions', 'A successful response will be a JSON array of search results, similar to this structure (fields may vary based on token permissions):')}</Text>
                            <Code p={2} borderRadius="md" display="block" whiteSpace="pre-wrap">
                              {t('tokenManagementPage.guide.responseFormatValue', `[
  {
    "id": "some_unique_document_id",
    "score": 0.85,
    "metadata": {
      "subject": "Project Phoenix Meeting Notes",
      "sender_name": "Alice",
      "created_at": "2024-01-15T10:30:00Z",
      // ... other metadata fields allowed by token ...
    },
    "content": "... relevant text chunk from the document ..."
  },
  // ... more results ...
]`)}
                            </Code>
                        </Box>
                        
                        <Box>
                            <Heading size="md" mb={2}>{t('tokenManagementPage.guide.limitationsTitle', 'Current Limitations')}</Heading>
                            <Alert status="info" borderRadius="md">
                                <AlertIcon />
                                {t('tokenManagementPage.guide.milvusOnly', 'Currently, this endpoint only searches the Milvus vector database. Iceberg table data is not included.')}
                            </Alert>
                        </Box>
                    </VStack>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </Box>
          )}
          
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

      <TestTokenModal
        isOpen={isTestModalOpen}
        onClose={() => {
            onTestModalClose();
            setTestingTokenId(null);
            setTestingTokenName('');
        }}
        tokenId={testingTokenId}
        tokenName={testingTokenName}
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

      <AlertDialog
        isOpen={isRegenerateConfirmOpen}
        leastDestructiveRef={cancelRef}
        onClose={onRegenerateConfirmClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('tokenManagementPage.regenerateDialog.title', 'Regenerate Secret')} {tokenToRegenerate?.name ? `"${tokenToRegenerate.name}"` : ''}
            </AlertDialogHeader>

            <AlertDialogBody>
              {t('tokenManagementPage.regenerateDialog.message', 'Are you sure? The current secret will stop working immediately. You will be shown the new secret only once.')}
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onRegenerateConfirmClose} isDisabled={isRegenerating}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button colorScheme="orange" onClick={confirmRegenerate} ml={3} isLoading={isRegenerating}>
                {t('tokenManagementPage.regenerateDialog.confirm', 'Confirm Regenerate')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <Modal isOpen={isNewTokenModalOpen} onClose={onNewTokenModalClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('tokenManagementPage.regenerateModal.title', 'New Token Secret Generated')}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text mb={2}>{t('tokenManagementPage.regenerateModal.message', 'Please copy the new token value below. This is the only time it will be shown:')}</Text>
            <InputGroup size="md">
              <Input
                pr="4.5rem"
                value={regeneratedTokenValue}
                isReadOnly
                fontFamily="monospace"
              />
              <InputRightElement width="4.5rem">
                <IconButton 
                    h="1.75rem" 
                    size="sm" 
                    aria-label={t('common.copy', 'Copy token')}
                    icon={<CopyIcon />} 
                    onClick={() => {
                        navigator.clipboard.writeText(regeneratedTokenValue);
                        toast({ title: t('common.copied', 'Copied!'), status: "success", duration: 1500 });
                    }}
                 />
              </InputRightElement>
            </InputGroup>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" onClick={onNewTokenModalClose}>
              {t('common.close', 'Close')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default TokenManagementPage; 