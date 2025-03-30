import React from 'react';
import { Box, Heading, Text, Container, VStack, useColorMode } from '@chakra-ui/react';

interface PageBannerProps {
  title: string;
  subtitle?: string;
  gradient?: string;
}

const PageBanner: React.FC<PageBannerProps> = ({ 
  title, 
  subtitle,
  gradient
}) => {
  const { colorMode } = useColorMode();
  
  // Default gradients if none provided
  const defaultGradient = colorMode === 'dark' 
    ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
    : "linear(to-r, brand.600, brand.500, brand.400)";
  
  return (
    <Box 
      w="100%" 
      py={{ base: 8, md: 12 }}
      px={{ base: 4, md: 8 }}
      bgGradient={colorMode === 'dark' 
        ? "linear(to-br, rgba(5, 10, 48, 0.9), rgba(58, 12, 163, 0.7))"
        : "linear(to-br, rgba(247, 249, 252, 0.9), rgba(224, 231, 255, 0.7))"
      }
      borderBottom="1px solid"
      borderColor="border.primary"
    >
      <Container maxW="1200px">
        <VStack spacing={{ base: 2, md: 3 }} align="center" textAlign="center">
          <Heading 
            size={{ base: "xl", md: "2xl" }} 
            bgGradient={gradient || defaultGradient}
            bgClip="text"
            sx={{
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
            px={{ base: 2, md: 0 }}
            wordBreak="break-word"
          >
            {title}
          </Heading>
          {subtitle && (
            <Text 
              fontSize={{ base: "md", md: "lg" }} 
              color="text.secondary" 
              maxW="800px"
              px={{ base: 2, md: 0 }}
            >
              {subtitle}
            </Text>
          )}
        </VStack>
      </Container>
    </Box>
  );
};

export default PageBanner;
