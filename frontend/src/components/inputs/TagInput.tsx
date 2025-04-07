import React, { useState, KeyboardEvent } from 'react';
import {
  Input,
  Tag,
  TagLabel,
  TagCloseButton,
  Wrap, // Use Wrap for better responsiveness
  WrapItem,
  useTheme, // To access theme colors if needed
} from '@chakra-ui/react';

interface TagInputProps {
  value: string[];
  onChange: (newValue: string[]) => void;
  placeholder?: string;
  isDisabled?: boolean;
  size?: string; // Add size prop
}

const TagInput: React.FC<TagInputProps> = ({
  value: tags = [], // Default to empty array
  onChange,
  placeholder = 'Type and press Enter...',
  isDisabled = false,
  size = 'md', // Default size
}) => {
  const [inputValue, setInputValue] = useState('');
  const theme = useTheme();

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && inputValue.trim() !== '') {
      event.preventDefault(); // Prevent form submission if inside a form
      const newTag = inputValue.trim();
      // Add tag only if it doesn't already exist
      if (!tags.includes(newTag)) {
        onChange([...tags, newTag]);
      }
      setInputValue(''); // Clear input
    }
    // Optional: Handle Backspace to remove the last tag if input is empty
    if (event.key === 'Backspace' && inputValue === '' && tags.length > 0) {
        handleRemoveTag(tags.length - 1);
    }
  };

  const handleRemoveTag = (indexToRemove: number) => {
    if (isDisabled) return;
    onChange(tags.filter((_, index) => index !== indexToRemove));
  };

  return (
    <Wrap
      spacing={2}
      align="center"
      borderWidth="1px"
      borderRadius="md"
      p={size === 'sm' ? 1 : 2} // Adjust padding based on size
      borderColor={isDisabled ? 'gray.200' : 'gray.200'} // Consistent border color
      bg={isDisabled ? 'gray.100' : 'transparent'}
      cursor={isDisabled ? 'not-allowed' : 'text'}
      onClick={(e) => {
        // Focus the hidden input when the wrapper is clicked
        const inputElement = (e.currentTarget as HTMLElement).querySelector('input');
        inputElement?.focus();
       }}
      w="100%" // Ensure it takes full width available in the HStack
    >
      {tags.map((tag, index) => (
        <WrapItem key={index}>
          <Tag
            size={size} // Use size prop
            borderRadius="full"
            variant="solid"
            colorScheme="blue" // Or another color scheme
            isDisabled={isDisabled}
          >
            <TagLabel>{tag}</TagLabel>
            {!isDisabled && <TagCloseButton onClick={() => handleRemoveTag(index)} />}
          </Tag>
        </WrapItem>
      ))}
      <WrapItem flexGrow={1} flexBasis="100px"> {/* Ensure input can grow and has a minimum basis */}
        <Input
          variant="unstyled" // Remove default input styling
          placeholder={tags.length === 0 ? placeholder : ''} // Show placeholder only when empty
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleInputKeyDown}
          isDisabled={isDisabled}
          size={size} // Use size prop
          ml={tags.length > 0 ? 1 : 0} // Add slight margin if tags exist
          // Remove minW to allow flexbox to handle width
          _placeholder={{ fontSize: size === 'sm' ? 'sm' : 'md' }} // Adjust placeholder size
          height="auto" // Allow height to adjust
          minHeight={size === 'sm' ? '1.75rem' : '2.5rem'} // Match button/input height for size
          py={1} // Add some vertical padding
        />
      </WrapItem>
    </Wrap>
  );
};

export default TagInput;