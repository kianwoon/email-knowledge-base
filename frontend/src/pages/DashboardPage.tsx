import React from 'react';
import {
  Box,
  Container,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Heading,
  Text,
  VStack,
  HStack,
  Icon,
  useColorModeValue,
  Card,
  CardBody,
} from '@chakra-ui/react';
import { FaDatabase, FaRobot, FaSearch, FaCheckCircle } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';

const DashboardPage: React.FC = () => {
  const { t } = useTranslation();
  const cardBg = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Mock data - replace with actual API calls
  const stats = [
    {
      label: 'Total Documents',
      value: '1,234',
      icon: FaDatabase,
      helpText: 'Processed documents in knowledge base',
    },
    {
      label: 'AI Interactions',
      value: '5,678',
      icon: FaRobot,
      helpText: 'Total AI assistant interactions',
    },
    {
      label: 'Searches',
      value: '892',
      icon: FaSearch,
      helpText: 'Knowledge base searches this month',
    },
    {
      label: 'Success Rate',
      value: '98.5%',
      icon: FaCheckCircle,
      helpText: 'Average response accuracy',
    },
  ];

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        <Box>
          <Heading size="lg" mb={2}>
            {t('dashboard.welcome', 'Welcome to Your Dashboard')}
          </Heading>
          <Text color="gray.500">
            {t('dashboard.overview', 'Overview of your knowledge base and AI interactions')}
          </Text>
        </Box>

        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          {stats.map((stat, idx) => (
            <Card
              key={idx}
              bg={cardBg}
              borderWidth="1px"
              borderColor={borderColor}
              borderRadius="lg"
              overflow="hidden"
              transition="all 0.2s"
              _hover={{ transform: 'translateY(-2px)', shadow: 'md' }}
            >
              <CardBody>
                <Stat>
                  <HStack spacing={3} mb={2}>
                    <Icon as={stat.icon} w={6} h={6} color="blue.500" />
                    <StatLabel fontSize="lg">{t(`dashboard.stats.${stat.label}`, stat.label)}</StatLabel>
                  </HStack>
                  <StatNumber fontSize="2xl" fontWeight="bold">
                    {stat.value}
                  </StatNumber>
                  <StatHelpText>
                    {t(`dashboard.stats.help.${stat.label}`, stat.helpText)}
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>

        {/* Add more dashboard sections here */}
      </VStack>
    </Container>
  );
};

export default DashboardPage; 