import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Link,
  Icon,
  useColorModeValue,
  Center,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Input,
  InputGroup,
  InputLeftElement,
  IconButton,
  Select,
  chakra
} from '@chakra-ui/react';
import {
  FaExternalLinkAlt,
  FaSort,
  FaSortUp,
  FaSortDown,
  FaSearch,
  FaFolder,
  FaFile
} from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { getMyRecentFiles } from '../api/apiClient'; // Import the new API function
import { RecentDriveItem } from '../models/sharepoint'; // Import the new model

// Helper Functions (can be moved to a utils file)
const formatDateTime = (dateTimeString?: string): string => {
  if (!dateTimeString) return '-';
  try {
    return new Date(dateTimeString).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  } catch {
    return dateTimeString;
  }
};

const getFileIcon = (item: RecentDriveItem) => {
  if (item.folder) {
    return FaFolder;
  }
  // Add more specific icons based on mimeType later if needed
  // const mimeType = item.file?.mimeType;
  // if (mimeType?.includes('word')) return FaFileWord;
  // if (mimeType?.includes('excel')) return FaFileExcel;
  // if (mimeType?.includes('powerpoint')) return FaFilePowerpoint;
  // if (mimeType?.includes('pdf')) return FaFilePdf;
  return FaFile; // Default file icon
};

type SortableColumns = 'name' | 'lastModifiedDateTime' | 'lastModifiedBy.user.displayName';
type SortDirection = 'asc' | 'desc';

const MyRecentFilesList: React.FC = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState<RecentDriveItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ownerFilter, setOwnerFilter] = useState('');
  const [sortBy, setSortBy] = useState<SortableColumns>('lastModifiedDateTime');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const tableBg = useColorModeValue('white', 'gray.700');
  const iconColor = useColorModeValue('gray.600', 'gray.400');
  const hoverBg = useColorModeValue('gray.50', 'whiteAlpha.100');
  const headerColor = useColorModeValue('gray.600', 'gray.400');

  // Fetch Data
  useEffect(() => {
    const fetchItems = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getMyRecentFiles(50); // Fetch top 50 recent items
        setItems(data || []);
      } catch (err: any) {
        console.error('[MyRecentFilesList] Fetch error:', err);
        setError(err.response?.data?.detail || err.message || t('errors.unknown'));
        setItems([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchItems();
  }, [t]);

  // Filtering and Sorting Logic
  const filteredAndSortedItems = useMemo(() => {
    let processedItems = [...items];

    // Apply Owner Filter (case-insensitive)
    if (ownerFilter.trim()) {
      processedItems = processedItems.filter(item =>
        item.lastModifiedBy?.user?.displayName?.toLowerCase().includes(ownerFilter.toLowerCase())
      );
    }

    // Apply Sorting
    processedItems.sort((a, b) => {
      let aValue: any;
      let bValue: any;

      // Handle nested properties for sorting
      if (sortBy === 'lastModifiedBy.user.displayName') {
        aValue = a.lastModifiedBy?.user?.displayName || '';
        bValue = b.lastModifiedBy?.user?.displayName || '';
      } else {
        aValue = a[sortBy] || '';
        bValue = b[sortBy] || '';
      }

      // Handle date sorting
      if (sortBy === 'lastModifiedDateTime') {
        aValue = a.lastModifiedDateTime ? new Date(a.lastModifiedDateTime).getTime() : 0;
        bValue = b.lastModifiedDateTime ? new Date(b.lastModifiedDateTime).getTime() : 0;
      }

      // Comparison logic
      let comparison = 0;
      if (aValue < bValue) {
        comparison = -1;
      } else if (aValue > bValue) {
        comparison = 1;
      }

      return sortDirection === 'asc' ? comparison : comparison * -1;
    });

    return processedItems;
  }, [items, ownerFilter, sortBy, sortDirection]);

  // Sort Handler
  const handleSort = useCallback((column: SortableColumns) => {
    setSortBy(prevSortBy => {
      if (prevSortBy === column) {
        // If same column, toggle direction
        setSortDirection(prevDir => prevDir === 'asc' ? 'desc' : 'asc');
      } else {
        // If new column, default to descending for date, ascending for others
        setSortDirection(column === 'lastModifiedDateTime' ? 'desc' : 'asc');
      }
      return column;
    });
  }, []);

  // Helper to render sort icon
  const SortIcon = ({ column }: { column: SortableColumns }) => {
    if (sortBy !== column) {
      return <Icon as={FaSort} aria-label="sortable" color="gray.400" />; // Default icon
    }
    return sortBy === column && sortDirection === 'asc' ?
      <Icon as={FaSortUp} aria-label="sorted ascending" /> :
      <Icon as={FaSortDown} aria-label="sorted descending" />;
  };

  // Render Logic
  if (isLoading) {
    return (
      <Center py={10}>
        <Spinner size="xl" />
      </Center>
    );
  }

  if (error) {
    return (
      <Alert status="error" mt={4}>
        <AlertIcon />
        <AlertTitle mr={2}>{t('sharepoint.errors.fetchRecentTitle')}</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <VStack spacing={4} align="stretch">
      {/* Filter Input */}
      <InputGroup size="sm">
        <InputLeftElement pointerEvents="none">
          <Icon as={FaSearch} color="gray.400" />
        </InputLeftElement>
        <Input
          type="text"
          placeholder={t('sharepoint.filterByOwner')}
          value={ownerFilter}
          onChange={(e) => setOwnerFilter(e.target.value)}
          bg={useColorModeValue('white', 'gray.600')}
        />
      </InputGroup>

      {/* Results Table */}
      <Box overflowX="auto" bg={tableBg} borderRadius="md" borderWidth="1px">
        {filteredAndSortedItems.length > 0 ? (
          <Table variant="simple" size="sm">
            <Thead>
              <Tr>
                <Th cursor="pointer" onClick={() => handleSort('name')} color={headerColor}>
                  <HStack spacing={1}>{t('sharepoint.name')} <SortIcon column="name" /></HStack>
                </Th>
                <Th cursor="pointer" onClick={() => handleSort('lastModifiedDateTime')} color={headerColor}>
                  <HStack spacing={1}>{t('sharepoint.modified')} <SortIcon column="lastModifiedDateTime" /></HStack>
                </Th>
                <Th cursor="pointer" onClick={() => handleSort('lastModifiedBy.user.displayName')} color={headerColor}>
                  <HStack spacing={1}>{t('sharepoint.modifiedBy')} <SortIcon column="lastModifiedBy.user.displayName" /></HStack>
                </Th>
                {/* Add Activity column later if data becomes available */}
                {/* <Th>Activity</Th> */}
              </Tr>
            </Thead>
            <Tbody>
              {filteredAndSortedItems.map((item) => (
                <Tr key={item.id} _hover={{ bg: hoverBg }}>
                  <Td py={2}>
                    <HStack spacing={2}>
                       <Icon as={getFileIcon(item)} color={iconColor} boxSize="1.1em" />
                       <Link href={item.webUrl || '#'} isExternal _hover={{ textDecoration: 'underline' }}>
                         <Text as="span" fontSize="sm" noOfLines={1} title={item.name || t('sharepoint.untitledItem') || 'Untitled'}>
                           {item.name || `(${t('sharepoint.untitledItem') || 'Untitled'})`}
                         </Text>
                       </Link>
                     </HStack>
                  </Td>
                  <Td fontSize="xs" whiteSpace="nowrap" py={2}>{formatDateTime(item.lastModifiedDateTime)}</Td>
                  <Td fontSize="xs" whiteSpace="nowrap" py={2}>{item.lastModifiedBy?.user?.displayName || '-'}</Td>
                  {/* <Td>{ item.activity || '-'}</Td> */}
                </Tr>
              ))}
            </Tbody>
          </Table>
        ) : (
          <Center py={10}>
            <Text color="gray.500">
              {items.length > 0 && ownerFilter ? 
                t('sharepoint.noMatchingItemsFilter') : 
                t('sharepoint.noRecentItems')
              }
            </Text>
          </Center>
        )}
      </Box>
    </VStack>
  );
};

export default MyRecentFilesList; 