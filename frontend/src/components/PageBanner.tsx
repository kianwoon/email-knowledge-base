import React from 'react';
import { Box, Heading, Text, Container, VStack } from '@chakra-ui/react';

interface PageBannerProps {
  title: string;
  subtitle?: string;
  gradient?: string;
}

const PageBanner: React.FC<PageBannerProps> = ({ 
  title, 
  subtitle,
  gradient = "linear(to-r, #3ef2f2, #f72585)"
}) => {
  return (
    <Box 
      w="100%" 
      py={12}
      bgGradient="linear(to-b, rgba(62, 242, 242, 0.2), transparent)"
      borderBottom="1px solid rgba(255, 255, 255, 0.1)"
    >
      <Container maxW="1200px">
        <VStack spacing={3} align="center" textAlign="center">
          <Heading 
            size="2xl" 
            bgGradient={gradient}
            bgClip="text"
          >
            {title}
          </Heading>
          {subtitle && (
            <Text fontSize="lg" color="whiteAlpha.800" maxW="800px">
              {subtitle}
            </Text>
          )}
        </VStack>
      </Container>
    </Box>
  );
};

export default PageBanner;
