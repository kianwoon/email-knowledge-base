import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Button,
  Icon,
  useColorMode
} from '@chakra-ui/react';
import { FaGlobe } from 'react-icons/fa';

const LanguageSwitcher: React.FC = () => {
  const { i18n, t } = useTranslation();
  const { colorMode } = useColorMode();
  
  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };
  
  // Check if language is any Chinese variant
  const isChinese = i18n.language === 'cn' || i18n.language.startsWith('zh');

  return (
    <Menu placement="bottom" gutter={0} closeOnSelect={true}>
      <MenuButton
        as={Button}
        variant="ghost"
        size="sm"
        color="text.primary"
        _hover={{ bg: "bg.accent" }}
        leftIcon={<Icon as={FaGlobe} />}
      >
        {isChinese ? '中文' : 'EN'}
      </MenuButton>
      <MenuList 
        bg={colorMode === 'dark' ? "bg.primary" : "white"} 
        borderColor={colorMode === 'dark' ? "whiteAlpha.300" : "gray.200"}
        zIndex={1000}
        minWidth="150px"
        boxShadow="md"
      >
        <MenuItem 
          onClick={() => changeLanguage('en')}
          bg={i18n.language === 'en' ? (colorMode === 'dark' ? "whiteAlpha.200" : "gray.100") : "transparent"}
          _hover={{ bg: colorMode === 'dark' ? "whiteAlpha.200" : "gray.100" }}
        >
          {t('language.english')}
        </MenuItem>
        <MenuItem 
          onClick={() => changeLanguage('cn')}
          bg={isChinese ? (colorMode === 'dark' ? "whiteAlpha.200" : "gray.100") : "transparent"}
          _hover={{ bg: colorMode === 'dark' ? "whiteAlpha.200" : "gray.100" }}
        >
          {t('language.chinese')}
        </MenuItem>
      </MenuList>
    </Menu>
  );
};

export default LanguageSwitcher;
