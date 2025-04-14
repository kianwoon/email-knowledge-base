import React, { useState, useEffect, useCallback } from 'react';
import {
    Box, Heading, VStack, HStack, Spinner, Alert, AlertIcon, useToast, Button, Text, Select, List, ListItem
} from '@chakra-ui/react';
import {
    getAzureBlobConnections,
    createAzureBlobConnection,
    listAzureBlobContainers,
    AzureBlobConnection, // Import the types
    AzureBlobConnectionCreatePayload 
} from '../api/apiClient'; // Adjusted path

// Simple placeholder components (we'll create separate files later)

interface AzureConnectionFormProps {
    onCreate: (formData: AzureBlobConnectionCreatePayload) => Promise<void>;
    isLoading: boolean;
}

const AzureConnectionForm: React.FC<AzureConnectionFormProps> = ({ onCreate, isLoading }) => {
    const [name, setName] = useState('');
    const [accountName, setAccountName] = useState('');
    const [connectionString, setConnectionString] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!name || !accountName || !connectionString) {
            // Basic validation
            alert('Please fill in all fields.'); 
            return;
        }
        onCreate({ name, account_name: accountName, credentials: connectionString });
        // Reset form maybe?
        // setName('');
        // setAccountName('');
        // setConnectionString('');
    };

    // Basic form styling needed
    return (
        <Box as="form" onSubmit={handleSubmit} p={4} borderWidth={1} borderRadius="md" mb={6}>
            <VStack spacing={4} align="stretch">
                <Heading size="md">Add New Connection</Heading>
                <input type="text" placeholder="Connection Name (e.g., Work Storage)" value={name} onChange={(e) => setName(e.target.value)} required />
                <input type="text" placeholder="Storage Account Name" value={accountName} onChange={(e) => setAccountName(e.target.value)} required />
                <textarea placeholder="Connection String" value={connectionString} onChange={(e) => setConnectionString(e.target.value)} required />
                <Button type="submit" isLoading={isLoading} colorScheme="blue">
                    Add Connection
                </Button>
            </VStack>
        </Box>
    );
};

interface AzureConnectionListProps {
    connections: AzureBlobConnection[];
    selectedConnectionId: string | null;
    onSelectConnection: (id: string) => void;
    isLoading: boolean;
}

const AzureConnectionList: React.FC<AzureConnectionListProps> = ({ connections, selectedConnectionId, onSelectConnection, isLoading }) => {
    if (isLoading) return <Spinner />;
    if (!connections.length) return <Text>No connections configured yet.</Text>;

    return (
        <VStack align="stretch" mb={6}>
             <Heading size="md">Select Connection</Heading>
             <Select 
                placeholder="Select a connection..." 
                value={selectedConnectionId || ''}
                onChange={(e) => onSelectConnection(e.target.value)}
             >
                {connections.map(conn => (
                    <option key={conn.id} value={conn.id}>
                        {conn.name} ({conn.account_name})
                    </option>
                ))}
             </Select>
        </VStack>
    );
};

interface AzureContainerBrowserProps {
    connectionId: string | null;
    isLoading: boolean;
    error: string | null;
}

const AzureContainerBrowser: React.FC<AzureContainerBrowserProps> = ({ connectionId, isLoading, error }) => {
    const [containers, setContainers] = useState<string[]>([]);
    const [isFetching, setIsFetching] = useState(false);
    const toast = useToast();

    useEffect(() => {
        if (!connectionId) {
            setContainers([]);
            return;
        }

        const fetchContainers = async () => {
            setIsFetching(true);
            try {
                const fetchedContainers = await listAzureBlobContainers(connectionId);
                setContainers(fetchedContainers);
            } catch (err: any) { // Improved error handling
                const errorMessage = err.response?.data?.detail || err.message || 'Failed to fetch containers';
                console.error("Container fetch error:", err);
                toast({ title: "Error fetching containers", description: errorMessage, status: "error", duration: 5000, isClosable: true });
                setContainers([]);
            } finally {
                setIsFetching(false);
            }
        };

        fetchContainers();
    }, [connectionId, toast]);

    if (!connectionId) return null; // Don't render if no connection selected
    if (isFetching || isLoading) return <Spinner />;
    if (error) return <Alert status="error"><AlertIcon />{error}</Alert>;

    return (
        <Box p={4} borderWidth={1} borderRadius="md">
            <Heading size="md">Containers</Heading>
            {containers.length > 0 ? (
                <List spacing={2} mt={4}>
                    {containers.map(name => <ListItem key={name}>{name}</ListItem>)}
                </List>
            ) : (
                <Text mt={4}>No containers found or unable to fetch.</Text>
            )}
        </Box>
    );
};


// Main Page Component
const AzureBlobPage: React.FC = () => {
    const [connections, setConnections] = useState<AzureBlobConnection[]>([]);
    const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
    const [isLoadingConnections, setIsLoadingConnections] = useState(true);
    const [isCreatingConnection, setIsCreatingConnection] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const toast = useToast();

    const fetchConnections = useCallback(async () => {
        setIsLoadingConnections(true);
        setError(null);
        try {
            const fetchedConnections = await getAzureBlobConnections();
            setConnections(fetchedConnections);
            if (fetchedConnections.length > 0 && !selectedConnectionId) {
                // Optionally select the first connection by default
                // setSelectedConnectionId(fetchedConnections[0].id);
            }
        } catch (err: any) { // Improved error handling
            const errorMessage = err.response?.data?.detail || err.message || 'Failed to load connections';
            console.error("Error fetching connections:", err);
            setError(errorMessage);
            toast({ title: "Error", description: errorMessage, status: "error", duration: 5000, isClosable: true });
        } finally {
            setIsLoadingConnections(false);
        }
    }, [toast, selectedConnectionId]);

    useEffect(() => {
        fetchConnections();
    }, [fetchConnections]);

    const handleCreateConnection = async (formData: AzureBlobConnectionCreatePayload) => {
        setIsCreatingConnection(true);
        setError(null);
        try {
            await createAzureBlobConnection(formData);
            toast({ title: "Connection Created", description: "Azure Blob connection added successfully.", status: "success", duration: 3000, isClosable: true });
            await fetchConnections(); // Refresh list after creation
        } catch (err: any) { // Improved error handling
            const errorMessage = err.response?.data?.detail || err.message || 'Failed to create connection';
            console.error("Error creating connection:", err);
            setError(errorMessage);
            toast({ title: "Creation Failed", description: errorMessage, status: "error", duration: 5000, isClosable: true });
        } finally {
            setIsCreatingConnection(false);
        }
    };

    const handleSelectConnection = (id: string) => {
        setSelectedConnectionId(id);
        setError(null); // Clear errors when switching connections
    };

    return (
        <Box p={5}>
            <Heading mb={6}>Azure Blob Storage Management</Heading>

            {error && (
                <Alert status="error" mb={4}>
                    <AlertIcon />
                    {error}
                </Alert>
            )}

            <AzureConnectionForm onCreate={handleCreateConnection} isLoading={isCreatingConnection} />

            <AzureConnectionList 
                connections={connections} 
                selectedConnectionId={selectedConnectionId}
                onSelectConnection={handleSelectConnection}
                isLoading={isLoadingConnections}
            />

            <AzureContainerBrowser 
                connectionId={selectedConnectionId}
                isLoading={isLoadingConnections} // Browser depends on connections list being loaded
                error={null} // Let browser handle its own errors for now
            />

            {/* Placeholder for Blob list/upload/download components */}
        </Box>
    );
};

export default AzureBlobPage; 