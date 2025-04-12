import React from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  List, 
  ListItem,
  ListIcon,
  IconButton,
  Heading,
  Spinner,
  Center,
  useColorModeValue,
} from '@chakra-ui/react';
import { FaFolder, FaFile, FaTrashAlt, FaSync } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { SharePointSyncItem } from '../models/sharepoint';

interface SyncListComponentProps {
  items: SharePointSyncItem[];
  onRemoveItem: (sharepointItemId: string) => void;
  onProcessList: () => void;
  isProcessing: boolean;
  isLoading: boolean;
  error: string | null;
}

const SyncListComponent: React.FC<SyncListComponentProps> = ({ 
  items, 
  onRemoveItem, 
  onProcessList, 
  isProcessing, 
  isLoading,
  error
}) => {
  const { t } = useTranslation();
  const folderColor = useColorModeValue('blue.500', 'blue.300');
  const fileColor = useColorModeValue('gray.600', 'gray.400');
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');

  const renderContent = () => {
    if (isLoading) {
      return <Center p={5}><Spinner /></Center>;
    }
    if (error) {
        // Display error (consider using Alert component from Chakra)
        return <Center p={5}><Text color="red.500">{t('sharepoint.errors.loadSyncListError')}: {error}</Text></Center>;
    }
    if (items.length === 0) {
      return <Center p={5}><Text color="gray.500">{t('sharepoint.syncListEmpty')}</Text></Center>;
    }

    return (
      <List spacing={3} p={4}>
        {items.map((item) => (
          <ListItem 
            key={item.sharepoint_item_id} 
            display="flex" 
            alignItems="center" 
            justifyContent="space-between"
            p={2}
            borderRadius="md"
            _hover={{ bg: hoverBg }}
            bg={bgColor}
          >
            <HStack flex={1} minWidth={0}> {/* Allow shrinking */} 
              <ListIcon 
                as={item.item_type === 'folder' ? FaFolder : FaFile} 
                color={item.item_type === 'folder' ? folderColor : fileColor} 
                w={5} h={5}
              />
              <Text 
                isTruncated 
                title={item.item_name}
                flex={1} // Allow text to take available space
              >
                {item.item_name}
              </Text>
            </HStack>
            <IconButton
              aria-label={t('common.remove')}
              icon={<FaTrashAlt />}
              size="sm"
              variant="ghost"
              colorScheme="red"
              onClick={() => onRemoveItem(item.sharepoint_item_id)}
              isDisabled={isProcessing}
              ml={2} // Add margin left
            />
          </ListItem>
        ))}
      </List>
    );
  };

  return (
    <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
      <VStack spacing={0} align="stretch">
        <HStack justify="space-between" p={4} borderBottomWidth="1px">
            <Heading size="sm">{t('sharepoint.syncListTitle')}</Heading>
            <Text fontSize="sm">{t('sharepoint.syncListCount', { count: items.length })}</Text>
        </HStack>
        <Box maxHeight="400px" overflowY="auto"> {/* Scrollable list area */}
            {renderContent()}
        </Box>
        <HStack justify="flex-end" p={4} borderTopWidth="1px">
            <Button 
                colorScheme="blue"
                leftIcon={<FaSync />} 
                onClick={onProcessList}
                isLoading={isProcessing} // Show spinner on button when processing
                isDisabled={isProcessing || items.length === 0 || isLoading || !!error}
            >
                {t('sharepoint.processSyncListButton')}
            </Button>
        </HStack>
      </VStack>
    </Box>
  );
};

export default SyncListComponent; 