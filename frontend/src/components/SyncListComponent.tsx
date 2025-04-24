import React from 'react';
import {
  Box,
  Heading,
  Text,
  useColorModeValue,
  Spinner,
  Center,
  Button,
  Icon,
  VStack,
  HStack,
  List,
  ListItem,
  IconButton,
  Tag,
  Flex,
} from '@chakra-ui/react';
import { FaFolder, FaFileAlt, FaSync, FaTrashAlt } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';

// Define a common interface for sync list items from different sources
export interface SyncListItem {
  id: number;
  item_type: 'prefix' | 'folder' | 'file'; // Standardize: 'folder' or 'file' preferably
  name: string; // Display name (e.g., item_name, file name)
  path: string; // Full identifier (e.g., s3_key, blob_path, sharepoint_path)
  container?: string; // Optional: Bucket, Container name, Drive name, Site name etc.
  status: 'pending' | 'completed' | 'failed'; // Limited to known statuses
}

interface SyncListComponentProps {
  items: SyncListItem[];
  onRemoveItem: (itemId: number) => Promise<void>;
  onProcessList: () => void;
  isProcessing: boolean;
  isLoading: boolean;
  error: string | null;
  sourceType: 'S3' | 'Azure' | 'SharePoint'; // To customize titles etc.
  t: (key: string, options?: any) => string;
}

const SyncListComponent: React.FC<SyncListComponentProps> = ({
  items,
  onRemoveItem,
  onProcessList,
  isProcessing,
  isLoading,
  error,
  sourceType,
  t,
}) => {
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');

  console.log('[SyncListComponent] Rendering with items:', items);

  // Only show pending items in this component
  const pendingItems = items.filter(item => item.status === 'pending');

  const renderContent = () => {
    if (isLoading) {
      return <Center p={5}><Spinner /></Center>;
    }
    if (error) {
      return <Center p={5}><Text color="red.500" textAlign="center" width="100%">{t('syncList.errors.loadError', { context: sourceType, error: error })}</Text></Center>;
    }
    if (pendingItems.length === 0) {
      return <Center p={5}><Text color="gray.500" textAlign="center" width="100%">{t('syncList.empty_one', { context: sourceType })}</Text></Center>;
    }
    return (
      <List spacing={3} p={2}>
        {pendingItems.map((item) => {
          const isFolder = item.item_type === 'folder' || item.item_type === 'prefix';
          return (
            <ListItem
              key={item.id}
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              p={2}
              borderRadius="md"
              _hover={{ bg: hoverBg }}
            >
              <HStack spacing={2} flex={1} minWidth={0} width="100%">
                <Icon
                  as={isFolder ? FaFolder : FaFileAlt}
                  color={isFolder ? folderColor : fileColor}
                  boxSize="1.2em"
                  flexShrink={0}
                />
                <VStack align="start" spacing={0} flex={1} minWidth={0} width="100%">
                  <Text fontSize="sm" fontWeight="medium" noOfLines={1} title={item.path} width="100%" textAlign="left">
                    {item.name || item.path}
                  </Text>
                  {item.container && (
                     <Text fontSize="xs" color="gray.500" noOfLines={1} title={item.container} width="100%" textAlign="left">
                       {t(`syncList.containerLabel.${sourceType}`, { defaultValue: 'Location' })}: {item.container}
                     </Text>
                   )}
                </VStack>
              </HStack>
              <IconButton
                aria-label={t('common.remove', 'Remove')}
                icon={<FaTrashAlt />}
                size="sm"
                variant="ghost"
                colorScheme="red"
                onClick={() => onRemoveItem(item.id)}
                isDisabled={isProcessing}
                flexShrink={0}
              />
            </ListItem>
          );
        })}
      </List>
    );
  };

  return (
    <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
      <Flex justify="space-between" align="center" p={4} borderBottomWidth="1px">
        <Heading size="md">{t('syncList.title_one', { context: sourceType })}</Heading>
        <Tag size="md" variant="solid" colorScheme="blue">
          {t('syncList.pendingCount', { count: pendingItems.length })}
        </Tag>
      </Flex>
      <Box maxHeight="300px" overflowY="auto" p={4}>
        {renderContent()}
      </Box>
      <Flex justify="flex-end" p={4} borderTopWidth="1px">
        <Button
          leftIcon={<FaSync />}
          colorScheme="orange"
          onClick={onProcessList}
          isDisabled={isProcessing || pendingItems.length === 0}
          isLoading={isProcessing}
          loadingText={t('syncList.processingButton', 'Processing...')}
        >
          {t('syncList.processButton_one', { context: sourceType })}
        </Button>
      </Flex>
    </Box>
  );
};

export default SyncListComponent; 