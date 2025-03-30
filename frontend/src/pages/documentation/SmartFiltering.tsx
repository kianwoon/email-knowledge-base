import React from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  HStack,
  SimpleGrid,
  Card,
  CardBody,
  Divider,
  useColorMode,
  Flex,
  Icon,
  Badge
} from '@chakra-ui/react';
import { FaSearch, FaCalendarAlt, FaUser, FaTag, FaFolder, FaInfoCircle } from 'react-icons/fa';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';
import { useTranslation } from 'react-i18next';

// Workflow Step Card Component
const WorkflowStepCard = ({ 
  number, 
  title, 
  description 
}: { 
  number: string, 
  title: string, 
  description: string 
}) => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Card 
      bg={colorMode === 'dark' ? "gray.800" : "white"} 
      borderRadius="md"
      boxShadow="sm"
      overflow="hidden"
    >
      <CardBody>
        <HStack spacing={4} align="flex-start">
          <Flex
            w="36px"
            h="36px"
            bg={colorMode === 'dark' ? "blue.900" : "blue.50"}
            color={colorMode === 'dark' ? "blue.300" : "blue.600"}
            borderRadius="full"
            justify="center"
            align="center"
          >
            <Text fontWeight="bold">{number}</Text>
          </Flex>
          <Box>
            <Text fontWeight="bold" fontSize="md" color={colorMode === 'dark' ? "white" : "gray.900"}>{t(title)}</Text>
            <Text fontSize="sm" color={colorMode === 'dark' ? "gray.400" : "gray.600"}>{t(description)}</Text>
          </Box>
        </HStack>
      </CardBody>
    </Card>
  );
};

// Use Case Card Component
const UseCaseCard = ({ 
  title, 
  description, 
  tags 
}: { 
  title: string, 
  description: string, 
  tags: string[] 
}) => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Box 
      bg={colorMode === 'dark' ? "gray.800" : "white"} 
      borderRadius="lg"
      boxShadow="md"
      overflow="hidden"
      height="100%"
      borderWidth="1px"
      borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
      p={6}
    >
      <VStack spacing={4} align="flex-start">
        <HStack>
          <Icon as={FaInfoCircle} color={colorMode === 'dark' ? "blue.300" : "blue.500"} boxSize={5} />
          <Text fontWeight="bold" fontSize="lg" color={colorMode === 'dark' ? "white" : "gray.800"}>{t(title)}</Text>
        </HStack>
        <Text fontSize="md" color={colorMode === 'dark' ? "gray.300" : "gray.600"}>{t(description)}</Text>
        <Text fontWeight="medium" fontSize="sm" color={colorMode === 'dark' ? "gray.400" : "gray.500"}>{t('documentation.sections.filtering.tagsLabel')}</Text>
        <Flex flexWrap="wrap" gap={2}>
          {tags.map((tag, index) => {
            // Assign different colors based on tag index or content
            const colorSchemes = ["blue", "green", "purple", "red", "orange", "teal", "cyan", "pink"];
            const colorScheme = colorSchemes[index % colorSchemes.length];
            
            return (
              <Badge 
                key={index} 
                colorScheme={colorScheme}
                variant={colorMode === 'dark' ? "solid" : "subtle"}
                px={2}
                py={1}
                borderRadius="md"
                fontSize="xs"
              >
                {tag}
              </Badge>
            );
          })}
        </Flex>
      </VStack>
    </Box>
  );
};

// Filter Type Card Component
const FilterTypeCard = ({ 
  icon, 
  title, 
  description,
  examples = []
}: { 
  icon: React.ComponentType, 
  title: string, 
  description: string,
  examples?: string[]
}) => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Box 
      bg={colorMode === 'dark' ? "gray.800" : "white"} 
      borderRadius="lg"
      boxShadow="md"
      overflow="hidden"
      height="100%"
      borderWidth="1px"
      borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
      p={6}
    >
      <VStack spacing={4} align="flex-start">
        <HStack>
          <Icon as={icon} color={colorMode === 'dark' ? "blue.300" : "blue.500"} boxSize={5} />
          <Text fontWeight="bold" fontSize="lg" color={colorMode === 'dark' ? "white" : "gray.800"}>{t(title)}</Text>
        </HStack>
        <Text fontSize="md" color={colorMode === 'dark' ? "gray.300" : "gray.600"}>{t(description)}</Text>
        {examples.length > 0 && (
          <>
            <Text fontWeight="medium" fontSize="sm" color={colorMode === 'dark' ? "gray.400" : "gray.500"}>{t('documentation.sections.filtering.fieldsLabel')}</Text>
            <Flex flexWrap="wrap" gap={2}>
              {examples.map((example, index) => {
                // Assign different colors based on example index or content
                const colorSchemes = ["blue", "green", "purple", "red", "orange", "teal", "cyan", "pink"];
                const colorScheme = colorSchemes[index % colorSchemes.length];
                
                return (
                  <Badge 
                    key={index} 
                    colorScheme={colorScheme}
                    variant={colorMode === 'dark' ? "solid" : "subtle"}
                    px={2}
                    py={1}
                    borderRadius="md"
                    fontSize="xs"
                  >
                    {example}
                  </Badge>
                );
              })}
            </Flex>
          </>
        )}
      </VStack>
    </Box>
  );
};

const SmartFiltering: React.FC = () => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Box bg={colorMode === 'dark' ? "gray.900" : "gray.100"} minH="100vh" color={colorMode === 'dark' ? "white" : "gray.900"}>
      <PageBanner 
        title={t('documentation.sections.filtering.title')}
        subtitle={t('documentation.sections.filtering.description')}
        gradient={colorMode === 'dark' 
          ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
          : "linear(to-r, brand.600, brand.500, brand.400)"
        }
      />
      
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Introduction Section */}
          <Box mb={6}>
            <Heading 
              size="xl" 
              mb={4}
              color={colorMode === 'dark' ? "white" : "gray.800"}
            >
              {t('documentation.sections.filtering.header')}
            </Heading>
            
            <Text fontSize="lg" color={colorMode === 'dark' ? "gray.300" : "gray.600"}>
              {t('documentation.sections.filtering.description')}
            </Text>
          </Box>
          
          <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
          
          {/* Knowledge Structure Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "blue.300" : "blue.600"}>
              {t('documentation.sections.filtering.knowledgeStructure')}
            </Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <FilterTypeCard 
                icon={FaFolder} 
                title={t('documentation.sections.filtering.folder')}
                description={t('documentation.sections.filtering.folderDescription')}
                examples={[t('documentation.sections.filtering.executive'), t('documentation.sections.filtering.management'), t('documentation.sections.filtering.reports')]}
              />
              
              <FilterTypeCard 
                icon={FaCalendarAlt} 
                title={t('documentation.sections.filtering.dateRange')}
                description={t('documentation.sections.filtering.dateRangeDescription')}
                examples={[t('documentation.sections.filtering.date'), t('documentation.sections.filtering.creationDate'), t('documentation.sections.filtering.modificationDate')]}
              />
              
              <FilterTypeCard 
                icon={FaUser} 
                title={t('documentation.sections.filtering.senderRecipient')}
                description={t('documentation.sections.filtering.senderRecipientDescription')}
                examples={[t('documentation.sections.filtering.sender'), t('documentation.sections.filtering.recipient'), t('documentation.sections.filtering.subject'), t('documentation.sections.filtering.content')]}
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
          
          {/* Filtering Process Section */}
          <Box mb={8}>
            <Heading as="h2" size="lg" mb={6} color={colorMode === 'dark' ? "blue.300" : "blue.600"}>
              {t('documentation.sections.filtering.filteringProcess')}
            </Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <Box 
                bg={colorMode === 'dark' ? "gray.800" : "white"} 
                borderRadius="lg"
                boxShadow="sm"
                overflow="hidden"
                borderWidth="1px"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
                p={4}
                position="relative"
              >
                <Flex align="center" mb={2}>
                  <Flex 
                    w="32px" 
                    h="32px" 
                    borderRadius="md" 
                    bg="blue.50" 
                    justify="center" 
                    align="center"
                    mr={3}
                  >
                    <Icon as={FaSearch} color="blue.500" boxSize={4} />
                  </Flex>
                  <Text fontWeight="bold" fontSize="md" color={colorMode === 'dark' ? "white" : "gray.800"}>
                    {t('documentation.sections.filtering.filterTip1')}
                  </Text>
                </Flex>
                <Text fontSize="sm" color={colorMode === 'dark' ? "gray.300" : "gray.600"} pl="44px">
                  {t('documentation.sections.filtering.filterTip1Description')}
                </Text>
              </Box>
              
              <Box 
                bg={colorMode === 'dark' ? "gray.800" : "white"} 
                borderRadius="lg"
                boxShadow="sm"
                overflow="hidden"
                borderWidth="1px"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
                p={4}
                position="relative"
              >
                <Flex align="center" mb={2}>
                  <Flex 
                    w="32px" 
                    h="32px" 
                    borderRadius="md" 
                    bg="green.50" 
                    justify="center" 
                    align="center"
                    mr={3}
                  >
                    <Icon as={FaTag} color="green.500" boxSize={4} />
                  </Flex>
                  <Text fontWeight="bold" fontSize="md" color={colorMode === 'dark' ? "white" : "gray.800"}>
                    {t('documentation.sections.filtering.filterTip2')}
                  </Text>
                </Flex>
                <Text fontSize="sm" color={colorMode === 'dark' ? "gray.300" : "gray.600"} pl="44px">
                  {t('documentation.sections.filtering.filterTip2Description')}
                </Text>
              </Box>
              
              <Box 
                bg={colorMode === 'dark' ? "gray.800" : "white"} 
                borderRadius="lg"
                boxShadow="sm"
                overflow="hidden"
                borderWidth="1px"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
                p={4}
                position="relative"
              >
                <Flex align="center" mb={2}>
                  <Flex 
                    w="32px" 
                    h="32px" 
                    borderRadius="md" 
                    bg="blue.50" 
                    justify="center" 
                    align="center"
                    mr={3}
                  >
                    <Icon as={FaCalendarAlt} color="blue.500" boxSize={4} />
                  </Flex>
                  <Text fontWeight="bold" fontSize="md" color={colorMode === 'dark' ? "white" : "gray.800"}>
                    {t('documentation.sections.filtering.filterTip3')}
                  </Text>
                </Flex>
                <Text fontSize="sm" color={colorMode === 'dark' ? "gray.300" : "gray.600"} pl="44px">
                  {t('documentation.sections.filtering.filterTip3Description')}
                </Text>
              </Box>
              
              <Box 
                bg={colorMode === 'dark' ? "gray.800" : "white"} 
                borderRadius="lg"
                boxShadow="sm"
                overflow="hidden"
                borderWidth="1px"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.200"}
                p={4}
                position="relative"
              >
                <Flex align="center" mb={2}>
                  <Flex 
                    w="32px" 
                    h="32px" 
                    borderRadius="md" 
                    bg="cyan.50" 
                    justify="center" 
                    align="center"
                    mr={3}
                  >
                    <Icon as={FaUser} color="cyan.500" boxSize={4} />
                  </Flex>
                  <Text fontWeight="bold" fontSize="md" color={colorMode === 'dark' ? "white" : "gray.800"}>
                    {t('documentation.sections.filtering.filterTip4')}
                  </Text>
                </Flex>
                <Text fontSize="sm" color={colorMode === 'dark' ? "gray.300" : "gray.600"} pl="44px">
                  {t('documentation.sections.filtering.filterTip4Description')}
                </Text>
              </Box>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
          
          {/* Workflow Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "blue.300" : "blue.600"}>
              {t('documentation.sections.filtering.workflow')}
            </Heading>
            
            <SimpleGrid columns={{ base: 1, md: 4 }} spacing={6}>
              <WorkflowStepCard 
                number="1"
                title={t('documentation.sections.filtering.workflowStep1')}
                description={t('documentation.sections.filtering.workflowStep1Description')}
              />
              
              <WorkflowStepCard 
                number="2"
                title={t('documentation.sections.filtering.workflowStep2')}
                description={t('documentation.sections.filtering.workflowStep2Description')}
              />
              
              <WorkflowStepCard 
                number="3"
                title={t('documentation.sections.filtering.workflowStep3')}
                description={t('documentation.sections.filtering.workflowStep3Description')}
              />
              
              <WorkflowStepCard 
                number="4"
                title={t('documentation.sections.filtering.workflowStep4')}
                description={t('documentation.sections.filtering.workflowStep4Description')}
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
          
          {/* Use Cases Section */}
          <Box>
            <Heading size="lg" mb={6} color={colorMode === 'dark' ? "blue.300" : "blue.600"}>
              {t('documentation.sections.filtering.useCases')}
            </Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <UseCaseCard 
                title={t('documentation.sections.filtering.useCase1')}
                description={t('documentation.sections.filtering.useCase1Description')}
                tags={[t('documentation.sections.filtering.executive'), t('documentation.sections.filtering.management'), t('documentation.sections.filtering.reports')]}
              />
              
              <UseCaseCard 
                title={t('documentation.sections.filtering.useCase2')}
                description={t('documentation.sections.filtering.useCase2Description')}
                tags={[t('documentation.sections.filtering.clientRelations'), t('documentation.sections.filtering.sales'), t('documentation.sections.filtering.support')]}
              />
              
              <UseCaseCard 
                title={t('documentation.sections.filtering.useCase3')}
                description={t('documentation.sections.filtering.useCase3Description')}
                tags={[t('documentation.sections.filtering.itSupport'), t('documentation.sections.filtering.engineering'), t('documentation.sections.filtering.troubleshooting')]}
              />
            </SimpleGrid>
          </Box>
        </VStack>
      </Container>
      
      <Footer />
    </Box>
  );
};

export default SmartFiltering;
