import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Heading,
  VStack,
  HStack,
  Button,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Spinner,
  Text,
  useToast,
  useColorModeValue,
  ButtonGroup,
  Tag,
  Select,
  FormControl,
  FormLabel,
  Icon,
  chakra,
  Flex,
} from '@chakra-ui/react';
import { TriangleDownIcon, TriangleUpIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';
import { format, parseISO } from 'date-fns';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import { getTokenUsageReport, TokenUsageStat } from '@/api/token';

const DatePickerWrapperStyles = `
  .react-datepicker-wrapper {
    width: auto;
  }
  .react-datepicker__input-container input {
    width: 120px; /* Adjust as needed */
    padding: 0.375rem 0.75rem;
    font-size: 0.875rem;
    border: 1px solid;
    border-color: inherit; /* Use Chakra's border color */
    border-radius: 0.375rem; /* Use Chakra's border radius */
    background-color: inherit; /* Use Chakra's background */
    color: inherit; /* Use Chakra's text color */
  }
  .react-datepicker__input-container input:focus {
    outline: none;
    border-color: blue.500; /* Example focus color */
    box-shadow: 0 0 0 1px blue.500; /* Example focus shadow */
  }
  /* Basic dark mode adjustments - Needs more refinement */
  .chakra-ui-dark .react-datepicker__input-container input {
     border-color: gray.700;
  }
  .chakra-ui-dark .react-datepicker__header {
    background-color: #2D3748; /* gray.700 */
    border-bottom-color: #4A5568; /* gray.600 */
  }
 .chakra-ui-dark .react-datepicker__day-name, .chakra-ui-dark .react-datepicker__day, .chakra-ui-dark .react-datepicker__time-name {
    color: white;
  }
 .chakra-ui-dark .react-datepicker__current-month, .chakra-ui-dark .react-datepicker-time__header, .chakra-ui-dark .react-datepicker-year-header {
    color: white;
  }
 .chakra-ui-dark .react-datepicker__day--disabled {
    color: #718096; /* gray.500 */
  }
 .chakra-ui-dark .react-datepicker__day:hover {
    background-color: #4A5568; /* gray.600 */
  }
 .chakra-ui-dark .react-datepicker__day--selected, .chakra-ui-dark .react-datepicker__day--keyboard-selected {
    background-color: #3182CE; /* blue.500 */
    color: white;
  }
`;

type SortKey = keyof TokenUsageStat | 'last_used_at_date';
type SortDirection = 'asc' | 'desc';

const TokenUsagePage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const [usageData, setUsageData] = useState<TokenUsageStat[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRange, setSelectedRange] = useState<string>('all');
  const [selectedTokenId, setSelectedTokenId] = useState<string>('all');
  const [customStartDate, setCustomStartDate] = useState<Date | null>(null);
  const [customEndDate, setCustomEndDate] = useState<Date | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('usage_count');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const tableBg = useColorModeValue('white', 'gray.800');
  const tableBorderColor = useColorModeValue('gray.200', 'gray.700');
  const datePickerInputBg = useColorModeValue('white', 'gray.700');
  const datePickerInputBorder = useColorModeValue('gray.200', 'gray.600');

  const fetchUsageData = useCallback(async () => {
    setLoading(true);
    setError(null);

    let startDateStr: string | undefined = undefined;
    let endDateStr: string | undefined = undefined;
    const today = new Date();

    try {
      if (selectedRange === 'today') {
        startDateStr = format(today, 'yyyy-MM-dd');
        endDateStr = format(today, 'yyyy-MM-dd');
      } else if (selectedRange === '7d') {
        const sevenDaysAgo = new Date(today);
        sevenDaysAgo.setDate(today.getDate() - 6);
        startDateStr = format(sevenDaysAgo, 'yyyy-MM-dd');
        endDateStr = format(today, 'yyyy-MM-dd');
      } else if (selectedRange === '30d') {
        const thirtyDaysAgo = new Date(today);
        thirtyDaysAgo.setDate(today.getDate() - 29);
        startDateStr = format(thirtyDaysAgo, 'yyyy-MM-dd');
        endDateStr = format(today, 'yyyy-MM-dd');
      } else if (selectedRange === 'custom') {
        if (customStartDate) {
          startDateStr = format(customStartDate, 'yyyy-MM-dd');
        } else {
          if (customEndDate) { startDateStr = undefined; } else { throw new Error(t('tokenUsage.errorStartDateMissing')); }
        }
        if (customEndDate) {
          if (customStartDate && customEndDate < customStartDate) {
              throw new Error(t('tokenUsage.errorEndDateBeforeStart'));
          }
          endDateStr = format(customEndDate, 'yyyy-MM-dd');
        } else {
          endDateStr = undefined;
        }
      }

      const response = await getTokenUsageReport(startDateStr, endDateStr);
      setUsageData(response.usage_stats);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || t('tokenUsage.errorFetching');
      setError(errorMessage);
      toast({
        title: t('common.error'),
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setUsageData([]);
    } finally {
      setLoading(false);
    }
  }, [selectedRange, customStartDate, customEndDate, toast, t]);

  useEffect(() => {
    if (selectedRange === 'custom') {
      if (customStartDate || customEndDate) {
        fetchUsageData();
      } else {
        setUsageData([]);
      }
    } else {
      fetchUsageData();
    }
  }, [fetchUsageData, selectedRange, customStartDate, customEndDate]);

  const handleRangeChange = (range: string) => {
    setSelectedRange(range);
    if (range !== 'custom') {
        setCustomStartDate(null);
        setCustomEndDate(null);
    }
  };

  const handleTokenChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedTokenId(event.target.value);
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDirection(key === 'usage_count' ? 'desc' : 'asc');
    }
  };

  const processedUsageData = useMemo(() => {
    let dataToProcess = [...usageData];

    if (selectedTokenId !== 'all') {
      dataToProcess = dataToProcess.filter(token => token.token_id.toString() === selectedTokenId);
    }

    dataToProcess.sort((a, b) => {
      let valA: any;
      let valB: any;
      let compareResult = 0;

      if (sortKey === 'last_used_at_date') {
        const dateA = a.last_used_at ? parseISO(a.last_used_at).getTime() : (sortDirection === 'asc' ? -Infinity : Infinity);
        const dateB = b.last_used_at ? parseISO(b.last_used_at).getTime() : (sortDirection === 'asc' ? -Infinity : Infinity);
        compareResult = dateA - dateB;
      } else if (sortKey === 'usage_count') {
        compareResult = a.usage_count - b.usage_count;
      } else {
        valA = a[sortKey as keyof TokenUsageStat] ?? '';
        valB = b[sortKey as keyof TokenUsageStat] ?? '';
        if (typeof valA === 'string' && typeof valB === 'string') {
           compareResult = valA.toLowerCase().localeCompare(valB.toLowerCase());
        } else {
           compareResult = (valA < valB) ? -1 : (valA > valB) ? 1 : 0;
        }
      }

      return sortDirection === 'asc' ? compareResult : -compareResult;
    });

    return dataToProcess;
  }, [usageData, selectedTokenId, sortKey, sortDirection]);

  const SortIcon = ({ columnKey }: { columnKey: SortKey }) => {
    if (sortKey !== columnKey) return null;
    return sortDirection === 'asc' ? <TriangleUpIcon aria-label="sorted ascending" ml={1} /> : <TriangleDownIcon aria-label="sorted descending" ml={1} />;
  };

  const SortableTh = ({ 
    children, 
    columnKey, 
    isNumeric,
    ...rest
  }: { 
    children: React.ReactNode, 
    columnKey: SortKey, 
    isNumeric?: boolean,
    [key: string]: any
  }) => (
    <Th
      isNumeric={isNumeric}
      cursor="pointer"
      onClick={() => handleSort(columnKey)}
      _hover={{ bg: useColorModeValue('gray.100', 'gray.700') }}
      {...rest}
    >
      <Flex align="center" justify={isNumeric ? "flex-end" : "flex-start"}>
        {children}
        <SortIcon columnKey={columnKey} />
      </Flex>
    </Th>
  );

  return (
    <Box py={5} px={{ base: 2, md: 4 }} maxW="1200px" margin="auto">
      <style>{DatePickerWrapperStyles}</style>
      <VStack spacing={4} align="stretch">
        <Heading as="h1" size="lg">{t('tokenUsage.title')}</Heading>
        <Text>{t('tokenUsage.description')}</Text>
        <VStack align="stretch" spacing={3}>
          <HStack justify="space-between" spacing={4} flexWrap="wrap">
            <HStack spacing={2} align="center">
              <Text fontWeight="medium" whiteSpace="nowrap">{t('tokenUsage.selectRange')}:</Text>
              <ButtonGroup isAttached variant="outline" size="sm">
                <Button onClick={() => handleRangeChange('all')} isActive={Boolean(selectedRange === 'all')}>{t('tokenUsage.allTime')}</Button>
                <Button onClick={() => handleRangeChange('today')} isActive={Boolean(selectedRange === 'today')}>{t('tokenUsage.today')}</Button>
                <Button onClick={() => handleRangeChange('7d')} isActive={Boolean(selectedRange === '7d')}>{t('tokenUsage.last7Days')}</Button>
                <Button onClick={() => handleRangeChange('30d')} isActive={Boolean(selectedRange === '30d')}>{t('tokenUsage.last30Days')}</Button>
                <Button onClick={() => handleRangeChange('custom')} isActive={Boolean(selectedRange === 'custom')}>{t('tokenUsage.customRange')}</Button>
              </ButtonGroup>
            </HStack>
            <HStack spacing={2} align="center">
              <Text fontWeight="medium" whiteSpace="nowrap">{t('tokenUsage.selectToken')}:</Text>
              <Select size="sm" value={selectedTokenId} onChange={handleTokenChange} minW="200px" isDisabled={Boolean(loading || error || usageData.length === 0)}>
                <option value="all">{t('tokenUsage.allTokens')}</option>
                {!loading && !error && usageData.map(token => (
                  <option key={token.token_id} value={token.token_id.toString()}>{token.token_name} ({token.token_preview})</option>
                ))}
              </Select>
            </HStack>
          </HStack>
          {selectedRange === 'custom' && (
            <HStack spacing={4} pt={2}>
              <FormControl id="customStartDate" w="auto">
                <FormLabel fontSize="sm" mb={1}>{t('tokenUsage.startDate')}:</FormLabel>
                <DatePicker selected={customStartDate} onChange={(date: Date | null) => setCustomStartDate(date)} selectsStart startDate={customStartDate} endDate={customEndDate} dateFormat="yyyy-MM-dd" placeholderText="YYYY-MM-DD" maxDate={new Date()} />
              </FormControl>
              <FormControl id="customEndDate" w="auto">
                <FormLabel fontSize="sm" mb={1}>{t('tokenUsage.endDate')}:</FormLabel>
                <DatePicker selected={customEndDate} onChange={(date: Date | null) => setCustomEndDate(date)} selectsEnd startDate={customStartDate} endDate={customEndDate} minDate={customStartDate ? customStartDate : undefined} maxDate={new Date()} dateFormat="yyyy-MM-dd" placeholderText="YYYY-MM-DD" />
              </FormControl>
            </HStack>
          )}
        </VStack>
        {loading && (
          <Box textAlign="center" p={10}>
            <Spinner size="xl" />
            <Text mt={2}>{t('common.loading')}</Text>
          </Box>
        )}
        {error && (
          <Box textAlign="center" p={10}>
            <Text color="red.500">{error}</Text>
          </Box>
        )}
        {!loading && !error && (
          <TableContainer borderWidth="1px" borderColor={tableBorderColor} borderRadius="md" bg={tableBg}>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <SortableTh columnKey="token_name">{t('tokenUsage.table.name')}</SortableTh>
                  <SortableTh columnKey="token_description">{t('tokenUsage.table.description')}</SortableTh>
                  <SortableTh columnKey="token_preview">{t('tokenUsage.table.preview')}</SortableTh>
                  <SortableTh columnKey="usage_count" isNumeric>{t('tokenUsage.table.usageCount')}</SortableTh>
                  <SortableTh columnKey="last_used_at_date">{t('tokenUsage.table.lastUsed')}</SortableTh>
                </Tr>
              </Thead>
              <Tbody>
                {processedUsageData.length === 0 ? (
                  <Tr>
                    <Td colSpan={5} textAlign="center">
                      {selectedTokenId === 'all' 
                        ? t('tokenUsage.table.noData') 
                        : t('tokenUsage.table.noDataForToken')} 
                    </Td>
                  </Tr>
                ) : (
                  processedUsageData.map((token) => (
                    <Tr key={token.token_id}>
                      <Td fontWeight="medium">{token.token_name}</Td>
                      <Td color="gray.500">{token.token_description || '-'}</Td>
                      <Td fontFamily="monospace">
                        <Tag size="sm" variant="outline">{token.token_preview}</Tag>
                      </Td>
                      <Td isNumeric>{token.usage_count}</Td>
                      <Td>
                        {token.last_used_at 
                          ? format(parseISO(token.last_used_at), 'yyyy-MM-dd HH:mm:ss')
                          : t('common.never')}
                      </Td>
                    </Tr>
                  ))
                )}
              </Tbody>
            </Table>
          </TableContainer>
        )}
      </VStack>
    </Box>
  );
};

export default TokenUsagePage; 