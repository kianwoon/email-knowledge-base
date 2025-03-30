import React from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  SimpleGrid,
  VStack,
  Flex,
  Icon,
  useColorMode,
  Card,
  CardBody,
  CardHeader
} from '@chakra-ui/react';
import { 
  FaRobot, 
  FaDatabase, 
  FaUserCog, 
  FaChartLine, 
  FaCheckCircle, 
  FaEnvelope, 
  FaComments, 
  FaCode, 
  FaGlobe
} from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import Footer from '../../components/Footer';

// Process Step Card Component
const ProcessStepCard = ({ 
  number, 
  title, 
  description 
}: { 
  number: number, 
  title: string, 
  description: string 
}) => {
  const { colorMode } = useColorMode();
  
  return (
    <Card 
      variant="outline" 
      bg={colorMode === 'dark' ? "gray.800" : "white"}
      borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
      boxShadow="sm"
      height="100%"
    >
      <CardHeader pb={2}>
        <Flex align="center" mb={2}>
          <Box
            bg={colorMode === 'dark' ? "neon.blue" : "blue.500"}
            color="white"
            borderRadius="full"
            w={8}
            h={8}
            display="flex"
            alignItems="center"
            justifyContent="center"
            fontWeight="bold"
            mr={3}
          >
            {number}
          </Box>
          <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.700"}>
            {title}
          </Heading>
        </Flex>
      </CardHeader>
      <CardBody pt={0}>
        <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"}>
          {description}
        </Text>
      </CardBody>
    </Card>
  );
};

// Use Case Card Component
const UseCaseCard = ({ 
  title, 
  description, 
  icon 
}: { 
  title: string, 
  description: string, 
  icon: React.ComponentType 
}) => {
  const { colorMode } = useColorMode();
  
  return (
    <Card 
      variant="outline" 
      bg={colorMode === 'dark' ? "gray.800" : "white"}
      borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
      boxShadow="sm"
      height="100%"
    >
      <CardHeader pb={2}>
        <Flex align="center">
          <Icon as={icon} boxSize={5} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mr={2} />
          <Heading size="sm" color={colorMode === 'dark' ? "white" : "gray.700"}>
            {title}
          </Heading>
        </Flex>
      </CardHeader>
      <CardBody pt={0}>
        <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"} fontSize="sm">
          {description}
        </Text>
      </CardBody>
    </Card>
  );
};

// Best Practice Card Component
const BestPracticeCard = ({ 
  title, 
  description 
}: { 
  title: string, 
  description: string 
}) => {
  const { colorMode } = useColorMode();
  
  return (
    <Box 
      p={4} 
      borderRadius="md" 
      bg={colorMode === 'dark' ? "gray.800" : "white"}
      borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
      borderWidth="1px"
      boxShadow="sm"
    >
      <Flex align="flex-start" mb={2}>
        <Icon as={FaCheckCircle} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mt={1} mr={2} />
        <Box>
          <Text fontWeight="bold" color={colorMode === 'dark' ? "white" : "gray.700"}>
            {title}
          </Text>
          <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"} fontSize="sm">
            {description}
          </Text>
        </Box>
      </Flex>
    </Box>
  );
};

// Integration Option Card Component
const IntegrationOptionCard = ({ 
  title, 
  description, 
  icon 
}: { 
  title: string, 
  description: string, 
  icon: React.ComponentType 
}) => {
  const { colorMode } = useColorMode();
  
  return (
    <Flex 
      p={4} 
      borderRadius="md" 
      bg={colorMode === 'dark' ? "gray.800" : "white"}
      borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
      borderWidth="1px"
      boxShadow="sm"
      direction="column"
      height="100%"
    >
      <Flex align="center" mb={2}>
        <Icon as={icon} boxSize={5} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mr={2} />
        <Heading size="sm" color={colorMode === 'dark' ? "white" : "gray.700"}>
          {title}
        </Heading>
      </Flex>
      <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"} fontSize="sm">
        {description}
      </Text>
    </Flex>
  );
};

// Performance Metric Card Component
const PerformanceMetricCard = ({ 
  title, 
  description 
}: { 
  title: string, 
  description: string 
}) => {
  const { colorMode } = useColorMode();
  
  return (
    <Box 
      p={4} 
      borderRadius="md" 
      bg={colorMode === 'dark' ? "gray.800" : "white"}
      borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
      borderWidth="1px"
      boxShadow="sm"
    >
      <Heading size="sm" mb={2} color={colorMode === 'dark' ? "white" : "gray.700"}>
        {title}
      </Heading>
      <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"} fontSize="sm">
        {description}
      </Text>
    </Box>
  );
};

// Main Component
const AITraining = () => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Box py={8}>
      <Container maxW="1200px">
        <VStack spacing={8} align="stretch">
          {/* Header Section */}
          <Box textAlign="center" mb={8}>
            <Heading as="h1" size="xl" mb={4} color={colorMode === 'dark' ? "white" : "gray.800"}>
              {t('documentation.sections.aiTraining.header')}
            </Heading>
            <Text fontSize="lg" color={colorMode === 'dark' ? "gray.300" : "gray.600"} maxW="800px" mx="auto">
              {t('documentation.sections.aiTraining.subtitle')}
            </Text>
          </Box>

          {/* Overview Section */}
          <Box>
            <Heading size="lg" mb={4} color={colorMode === 'dark' ? "white" : "gray.800"}>
              {t('documentation.sections.aiTraining.overview')}
            </Heading>
            <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"} mb={6}>
              {t('documentation.sections.aiTraining.overviewDescription')}
            </Text>
          </Box>

          {/* Key Capabilities Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "white" : "gray.800"}>
              {t('documentation.sections.aiTraining.capabilities.title')}
            </Heading>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <Flex 
                p={6} 
                borderRadius="md" 
                bg={colorMode === 'dark' ? "gray.800" : "white"}
                borderWidth="1px"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
                boxShadow="sm"
                direction="column"
              >
                <Flex align="center" mb={4}>
                  <Icon as={FaDatabase} boxSize={6} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mr={3} />
                  <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.700"}>
                    {t('documentation.sections.aiTraining.capabilities.capability1.title')}
                  </Heading>
                </Flex>
                <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"}>
                  {t('documentation.sections.aiTraining.capabilities.capability1.description')}
                </Text>
              </Flex>

              <Flex 
                p={6} 
                borderRadius="md" 
                bg={colorMode === 'dark' ? "gray.800" : "white"}
                borderWidth="1px"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
                boxShadow="sm"
                direction="column"
              >
                <Flex align="center" mb={4}>
                  <Icon as={FaUserCog} boxSize={6} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mr={3} />
                  <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.700"}>
                    {t('documentation.sections.aiTraining.capabilities.capability2.title')}
                  </Heading>
                </Flex>
                <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"}>
                  {t('documentation.sections.aiTraining.capabilities.capability2.description')}
                </Text>
              </Flex>

              <Flex 
                p={6} 
                borderRadius="md" 
                bg={colorMode === 'dark' ? "gray.800" : "white"}
                borderWidth="1px"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
                boxShadow="sm"
                direction="column"
              >
                <Flex align="center" mb={4}>
                  <Icon as={FaGlobe} boxSize={6} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mr={3} />
                  <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.700"}>
                    {t('documentation.sections.aiTraining.capabilities.capability3.title')}
                  </Heading>
                </Flex>
                <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"}>
                  {t('documentation.sections.aiTraining.capabilities.capability3.description')}
                </Text>
              </Flex>

              <Flex 
                p={6} 
                borderRadius="md" 
                bg={colorMode === 'dark' ? "gray.800" : "white"}
                borderWidth="1px"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
                boxShadow="sm"
                direction="column"
              >
                <Flex align="center" mb={4}>
                  <Icon as={FaChartLine} boxSize={6} color={colorMode === 'dark' ? "neon.blue" : "blue.500"} mr={3} />
                  <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.700"}>
                    {t('documentation.sections.aiTraining.capabilities.capability4.title')}
                  </Heading>
                </Flex>
                <Text color={colorMode === 'dark' ? "gray.300" : "gray.600"}>
                  {t('documentation.sections.aiTraining.capabilities.capability4.description')}
                </Text>
              </Flex>
            </SimpleGrid>
          </Box>

          {/* Training Process Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "white" : "gray.800"}>
              {t('documentation.sections.aiTraining.trainingProcess.title')}
            </Heading>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
              <ProcessStepCard 
                number={1} 
                title={t('documentation.sections.aiTraining.trainingProcess.step1.title')} 
                description={t('documentation.sections.aiTraining.trainingProcess.step1.description')} 
              />
              <ProcessStepCard 
                number={2} 
                title={t('documentation.sections.aiTraining.trainingProcess.step2.title')} 
                description={t('documentation.sections.aiTraining.trainingProcess.step2.description')} 
              />
              <ProcessStepCard 
                number={3} 
                title={t('documentation.sections.aiTraining.trainingProcess.step3.title')} 
                description={t('documentation.sections.aiTraining.trainingProcess.step3.description')} 
              />
              <ProcessStepCard 
                number={4} 
                title={t('documentation.sections.aiTraining.trainingProcess.step4.title')} 
                description={t('documentation.sections.aiTraining.trainingProcess.step4.description')} 
              />
              <ProcessStepCard 
                number={5} 
                title={t('documentation.sections.aiTraining.trainingProcess.step5.title')} 
                description={t('documentation.sections.aiTraining.trainingProcess.step5.description')} 
              />
            </SimpleGrid>
          </Box>

          {/* Use Cases Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "white" : "gray.800"}>
              {t('documentation.sections.aiTraining.useCases.title')}
            </Heading>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <UseCaseCard 
                icon={FaRobot}
                title={t('documentation.sections.aiTraining.useCases.useCase1.title')} 
                description={t('documentation.sections.aiTraining.useCases.useCase1.description')} 
              />
              <UseCaseCard 
                icon={FaRobot}
                title={t('documentation.sections.aiTraining.useCases.useCase2.title')} 
                description={t('documentation.sections.aiTraining.useCases.useCase2.description')} 
              />
              <UseCaseCard 
                icon={FaRobot}
                title={t('documentation.sections.aiTraining.useCases.useCase3.title')} 
                description={t('documentation.sections.aiTraining.useCases.useCase3.description')} 
              />
              <UseCaseCard 
                icon={FaRobot}
                title={t('documentation.sections.aiTraining.useCases.useCase4.title')} 
                description={t('documentation.sections.aiTraining.useCases.useCase4.description')} 
              />
            </SimpleGrid>
          </Box>

          {/* Best Practices Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "white" : "gray.800"}>
              {t('documentation.sections.aiTraining.bestPractices.title')}
            </Heading>
            <VStack spacing={4} align="stretch">
              <BestPracticeCard 
                title={t('documentation.sections.aiTraining.bestPractices.practice1.title')} 
                description={t('documentation.sections.aiTraining.bestPractices.practice1.description')} 
              />
              <BestPracticeCard 
                title={t('documentation.sections.aiTraining.bestPractices.practice2.title')} 
                description={t('documentation.sections.aiTraining.bestPractices.practice2.description')} 
              />
              <BestPracticeCard 
                title={t('documentation.sections.aiTraining.bestPractices.practice3.title')} 
                description={t('documentation.sections.aiTraining.bestPractices.practice3.description')} 
              />
              <BestPracticeCard 
                title={t('documentation.sections.aiTraining.bestPractices.practice4.title')} 
                description={t('documentation.sections.aiTraining.bestPractices.practice4.description')} 
              />
              <BestPracticeCard 
                title={t('documentation.sections.aiTraining.bestPractices.practice5.title')} 
                description={t('documentation.sections.aiTraining.bestPractices.practice5.description')} 
              />
            </VStack>
          </Box>

          {/* Performance Metrics Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "white" : "gray.800"}>
              {t('documentation.sections.aiTraining.performance.title')}
            </Heading>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
              <PerformanceMetricCard 
                title={t('documentation.sections.aiTraining.performance.metric1.title')} 
                description={t('documentation.sections.aiTraining.performance.metric1.description')} 
              />
              <PerformanceMetricCard 
                title={t('documentation.sections.aiTraining.performance.metric2.title')} 
                description={t('documentation.sections.aiTraining.performance.metric2.description')} 
              />
              <PerformanceMetricCard 
                title={t('documentation.sections.aiTraining.performance.metric3.title')} 
                description={t('documentation.sections.aiTraining.performance.metric3.description')} 
              />
              <PerformanceMetricCard 
                title={t('documentation.sections.aiTraining.performance.metric4.title')} 
                description={t('documentation.sections.aiTraining.performance.metric4.description')} 
              />
            </SimpleGrid>
          </Box>

          {/* Integration Options Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "white" : "gray.800"}>
              {t('documentation.sections.aiTraining.integration.title')}
            </Heading>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <IntegrationOptionCard 
                icon={FaEnvelope}
                title={t('documentation.sections.aiTraining.integration.option1.title')} 
                description={t('documentation.sections.aiTraining.integration.option1.description')} 
              />
              <IntegrationOptionCard 
                icon={FaComments}
                title={t('documentation.sections.aiTraining.integration.option2.title')} 
                description={t('documentation.sections.aiTraining.integration.option2.description')} 
              />
              <IntegrationOptionCard 
                icon={FaDatabase}
                title={t('documentation.sections.aiTraining.integration.option3.title')} 
                description={t('documentation.sections.aiTraining.integration.option3.description')} 
              />
              <IntegrationOptionCard 
                icon={FaCode}
                title={t('documentation.sections.aiTraining.integration.option4.title')} 
                description={t('documentation.sections.aiTraining.integration.option4.description')} 
              />
            </SimpleGrid>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

export default AITraining;
