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
  InputRightElement,
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
  FaFile,
  FaFileWord,
  FaFileExcel,
  FaFilePowerpoint,
  FaFilePdf,
  FaFileImage,
  FaFileAudio,
  FaFileVideo,
  FaFileArchive
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

const formatFileSize = (bytes?: number): string => {
  if (bytes === undefined || bytes === null || bytes < 0) return '-';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

const getFileIcon = (item: RecentDriveItem) => {
  if (item.folder) {
    return FaFolder;
  }
  const mimeType = item.file?.mimeType?.toLowerCase() || '';
  if (mimeType.includes('word') || mimeType.includes('document')) return FaFileWord;
  if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return FaFileExcel;
  if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return FaFilePowerpoint;
  if (mimeType.includes('pdf')) return FaFilePdf;
  if (mimeType.includes('image')) return FaFileImage;
  if (mimeType.includes('audio')) return FaFileAudio;
  if (mimeType.includes('video')) return FaFileVideo;
  if (mimeType.includes('archive') || mimeType.includes('zip')) return FaFileArchive;
  return FaFile; // Default file icon
};

type SortableColumns = 'name' | 'lastModifiedDateTime' | 'lastModifiedBy.user.displayName' | 'size';
type SortDirection = 'asc' | 'desc';

const MyRecentFilesList: React.FC = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState<RecentDriveItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ownerFilter, setOwnerFilter] = useState('');
  const [sortBy, setSortBy] = useState<SortableColumns>('lastModifiedDateTime');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const tableBg = useColorModeValue('white', 'gray.800');
  const iconColor = useColorModeValue('gray.600', 'gray.400');
  const hoverBg = useColorModeValue('gray.50', 'whiteAlpha.100');
  const filterInputBg = useColorModeValue('white', 'gray.700');

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
        // Handle potentially missing values for size (treat null/undefined as -1 for sorting)
        aValue = sortBy === 'size' ? (a.size ?? -1) : (a[sortBy] || '');
        bValue = sortBy === 'size' ? (b.size ?? -1) : (b[sortBy] || '');
      }

      // Handle date sorting
      if (sortBy === 'lastModifiedDateTime') {
        aValue = a.lastModifiedDateTime ? new Date(a.lastModifiedDateTime).getTime() : 0;
        bValue = b.lastModifiedDateTime ? new Date(b.lastModifiedDateTime).getTime() : 0;
      }

      // Comparison logic (numbers or strings)
      let comparison = 0;
      if (typeof aValue === 'number' && typeof bValue === 'number') {
         comparison = aValue - bValue;
      } else {
         // Ensure values are strings for localeCompare
         const strA = String(aValue);
         const strB = String(bValue);
         comparison = strA.localeCompare(strB);
      }
     
      return sortDirection === 'asc' ? comparison : comparison * -1;
    });

    return processedItems;
  }, [items, ownerFilter, sortBy, sortDirection]);

  // Sort Handler
  const handleSort = useCallback((column: SortableColumns) => {
    setSortBy(prevSortBy => {
      if (prevSortBy === column) {
        setSortDirection(prevDir => prevDir === 'asc' ? 'desc' : 'asc');
      } else {
        // Default sorting direction: desc for date, asc for others
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
      {/* Filter Input - Modified to match Browse Sites search bar structure */}
      <InputGroup size="md">
        {/* REMOVED InputLeftElement */}
        {/* <InputLeftElement pointerEvents="none">
          <Icon as={FaSearch} color="gray.400" />
        </InputLeftElement> */}
        <Input
          type="text"
          placeholder={t('sharepoint.filterByOwner')} // Keep placeholder relevant to filtering
          value={ownerFilter}
          onChange={(e) => setOwnerFilter(e.target.value)}
          bg={filterInputBg}
          pr="3rem" // Changed padding to 3rem
        />
        <InputRightElement width="3rem"> {/* Changed width to 3rem */}
          <IconButton
            h="1.75rem"
            size="sm"
            aria-label={t('common.filter') || 'Filter'}
            icon={<Icon as={FaSearch} />}
            onClick={() => {}} 
            isDisabled={false} 
            colorScheme="blue" // Changed variant from ghost to solid blue
          />
        </InputRightElement>
      </InputGroup>

      {/* Results Table */}
      <Box overflowX="auto" bg={tableBg} borderRadius="md" borderWidth="1px">
        {filteredAndSortedItems.length > 0 ? (
          <Table variant="simple" size="sm">
            <Thead>
              <Tr>
                <Th cursor="pointer" onClick={() => handleSort('name')}>
                  <HStack spacing={1}>{t('sharepoint.name')} <SortIcon column="name" /></HStack>
                </Th>
                <Th cursor="pointer" onClick={() => handleSort('lastModifiedDateTime')}>
                  <HStack spacing={1}>{t('sharepoint.modified')} <SortIcon column="lastModifiedDateTime" /></HStack>
                </Th>
                <Th cursor="pointer" onClick={() => handleSort('lastModifiedBy.user.displayName')}>
                  <HStack spacing={1}>{t('sharepoint.modifiedBy')} <SortIcon column="lastModifiedBy.user.displayName" /></HStack>
                </Th>
                <Th cursor="pointer" onClick={() => handleSort('size')} isNumeric>
                  <HStack spacing={1} justify="flex-end">{t('sharepoint.size')} <SortIcon column="size" /></HStack>
                </Th>
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
                  <Td whiteSpace="nowrap" py={2}>{formatDateTime(item.lastModifiedDateTime)}</Td>
                  <Td whiteSpace="nowrap" py={2}>{item.lastModifiedBy?.user?.displayName || '-'}</Td>
                  <Td whiteSpace="nowrap" py={2} isNumeric>{formatFileSize(item.size)}</Td>
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