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
  Badge,
  Flex,
  Icon,
  Divider,
  useColorMode
} from '@chakra-ui/react';
import { 
  FaDatabase, 
  FaEnvelope, 
  FaFile, 
  FaNetworkWired, 
  FaSearch, 
  FaProjectDiagram, 
  FaChartLine, 
  FaLock, 
  FaFileExport, 
  FaCode,
  FaInfoCircle
} from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

// Knowledge Type Card Component
const KnowledgeTypeCard = ({ 
  title, 
  description, 
  fields,
  icon
}: { 
  title: string, 
  description: string, 
  fields: {name: string, color: string}[],
  icon: React.ElementType
}) => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Card 
      bg={colorMode === 'dark' ? "gray.800" : "white"} 
      borderRadius="md"
      boxShadow="sm"
      height="100%"
    >
      <CardBody>
        <VStack spacing={4} align="flex-start">
          <HStack>
            <Icon as={icon} color={colorMode === 'dark' ? "blue.300" : "blue.500"} />
            <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>{title}</Heading>
          </HStack>
          <Text fontSize="sm" color={colorMode === 'dark' ? "gray.400" : "gray.600"}>{description}</Text>
          
          <Box>
            <Text fontSize="sm" fontWeight="bold" mb={2}>{t('documentation.sections.knowledgeBase.fieldsTitle')}</Text>
            <Flex wrap="wrap" gap={2}>
              {fields.map((field, index) => (
                <Badge 
                  key={index}
                  colorScheme={field.color}
                  px={2}
                  py={1}
                  borderRadius="md"
                  fontSize="xs"
                >
                  {field.name}
                </Badge>
              ))}
            </Flex>
          </Box>
        </VStack>
      </CardBody>
    </Card>
  );
};

// Search Feature Card Component
const SearchFeatureCard = ({ 
  title, 
  description, 
  example,
  icon
}: { 
  title: string, 
  description: string, 
  example: string,
  icon: React.ElementType
}) => {
  const { colorMode } = useColorMode();
  
  return (
    <Card 
      bg={colorMode === 'dark' ? "gray.800" : "white"} 
      borderRadius="md"
      boxShadow="sm"
      height="100%"
    >
      <CardBody>
        <VStack spacing={4} align="flex-start">
          <HStack>
            <Icon as={icon} color={colorMode === 'dark' ? "blue.300" : "blue.500"} boxSize={5} />
            <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>{title}</Heading>
          </HStack>
          <Text fontSize="sm" color={colorMode === 'dark' ? "gray.400" : "gray.600"}>{description}</Text>
          
          <Box bg={colorMode === 'dark' ? "gray.700" : "gray.100"} p={2} borderRadius="md" width="100%">
            <Text fontSize="xs" fontStyle="italic">{example}</Text>
          </Box>
        </VStack>
      </CardBody>
    </Card>
  );
};

// Export Format Card Component
const ExportFormatCard = ({ 
  format,
  icon,
  color
}: { 
  format: string,
  icon: React.ElementType,
  color: string
}) => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Card 
      bg={colorMode === 'dark' ? "gray.800" : "white"} 
      borderRadius="md"
      boxShadow="sm"
    >
      <CardBody>
        <HStack spacing={3}>
          <Icon as={icon} color={color} boxSize={5} />
          <Text fontWeight="bold">{t(format)}</Text>
        </HStack>
      </CardBody>
    </Card>
  );
};

// API Endpoint Component
const ApiEndpoint = ({ 
  path, 
  description 
}: { 
  path: string, 
  description: string 
}) => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <HStack spacing={3} align="center">
      <Icon as={FaCheckCircle} color="green.500" boxSize={4} />
      <Text fontWeight="bold" color={colorMode === 'dark' ? "green.300" : "green.600"}>{t(path)}</Text>
      <Text color={colorMode === 'dark' ? "gray.400" : "gray.600"}>- {t(description)}</Text>
    </HStack>
  );
};

const KnowledgeBase: React.FC = () => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Box bg={colorMode === 'dark' ? "gray.900" : "gray.100"} minH="100vh" color={colorMode === 'dark' ? "white" : "gray.900"}>
      <PageBanner 
        title={t('documentation.sections.knowledgeBase.title')} 
        subtitle={t('documentation.sections.knowledgeBase.subtitle')}
        gradient={colorMode === 'dark' 
          ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
          : "linear(to-r, brand.600, brand.500, brand.400)"
        }
      />
      
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Knowledge Management Section */}
          <Box>
            <HStack mb={4}>
              <Icon as={FaDatabase} w={6} h={6} color={colorMode === 'dark' ? "blue.300" : "blue.500"} />
              <Heading size="lg" color={colorMode === 'dark' ? "white" : "gray.900"}>{t('documentation.sections.knowledgeBase.managementTitle')}</Heading>
            </HStack>
            
            <Text fontSize="md" mb={6}>
              {t('documentation.sections.knowledgeBase.managementDescription')}
            </Text>
            
            <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} mb={6} />
            
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.knowledgeBase.knowledgeStructureTitle')}</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6} mb={8}>
              <KnowledgeTypeCard 
                title={t('documentation.sections.knowledgeBase.emailKnowledgeTitle')}
                description={t('documentation.sections.knowledgeBase.emailKnowledgeDescription')}
                icon={FaEnvelope}
                fields={[
                  { name: t('documentation.sections.knowledgeBase.senderField'), color: "blue" },
                  { name: t('documentation.sections.knowledgeBase.recipientsField'), color: "blue" },
                  { name: t('documentation.sections.knowledgeBase.dateField'), color: "green" },
                  { name: t('documentation.sections.knowledgeBase.subjectField'), color: "purple" },
                  { name: t('documentation.sections.knowledgeBase.contentField'), color: "red" },
                  { name: t('documentation.sections.knowledgeBase.attachmentsField'), color: "orange" },
                  { name: t('documentation.sections.knowledgeBase.tagsField'), color: "yellow" },
                  { name: t('documentation.sections.knowledgeBase.priorityField'), color: "pink" }
                ]}
              />
              
              <KnowledgeTypeCard 
                title={t('documentation.sections.knowledgeBase.documentKnowledgeTitle')}
                description={t('documentation.sections.knowledgeBase.documentKnowledgeDescription')}
                icon={FaFile}
                fields={[
                  { name: t('documentation.sections.knowledgeBase.filenameField'), color: "blue" },
                  { name: t('documentation.sections.knowledgeBase.typeField'), color: "purple" },
                  { name: t('documentation.sections.knowledgeBase.sizeField'), color: "green" },
                  { name: t('documentation.sections.knowledgeBase.createdDateField'), color: "yellow" },
                  { name: t('documentation.sections.knowledgeBase.modifiedDateField'), color: "orange" },
                  { name: t('documentation.sections.knowledgeBase.contentField'), color: "red" },
                  { name: t('documentation.sections.knowledgeBase.tagsField'), color: "pink" }
                ]}
              />
              
              <KnowledgeTypeCard 
                title={t('documentation.sections.knowledgeBase.relationshipKnowledgeTitle')}
                description={t('documentation.sections.knowledgeBase.relationshipKnowledgeDescription')}
                icon={FaNetworkWired}
                fields={[
                  { name: t('documentation.sections.knowledgeBase.entityTypeField'), color: "blue" },
                  { name: t('documentation.sections.knowledgeBase.entityNameField'), color: "purple" },
                  { name: t('documentation.sections.knowledgeBase.relatedEntitiesField'), color: "green" },
                  { name: t('documentation.sections.knowledgeBase.relationshipTypeField'), color: "yellow" },
                  { name: t('documentation.sections.knowledgeBase.strengthField'), color: "red" },
                  { name: t('documentation.sections.knowledgeBase.contextField'), color: "orange" }
                ]}
              />
            </SimpleGrid>
          </Box>
          
          {/* Search Capabilities Section */}
          <Box>
            <HStack mb={4}>
              <Icon as={FaSearch} w={6} h={6} color={colorMode === 'dark' ? "blue.300" : "blue.500"} />
              <Heading size="lg" color={colorMode === 'dark' ? "white" : "gray.900"}>{t('documentation.sections.knowledgeBase.searchCapabilitiesTitle')}</Heading>
            </HStack>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6} mb={6}>
              <SearchFeatureCard
                title={t('documentation.sections.knowledgeBase.semanticSearchTitle')}
                description={t('documentation.sections.knowledgeBase.semanticSearchDescription')}
                example={t('documentation.sections.knowledgeBase.semanticSearchExample')}
                icon={FaSearch}
              />
              
              <SearchFeatureCard
                title={t('documentation.sections.knowledgeBase.relationshipSearchTitle')}
                description={t('documentation.sections.knowledgeBase.relationshipSearchDescription')}
                example={t('documentation.sections.knowledgeBase.relationshipSearchExample')}
                icon={FaProjectDiagram}
              />
              
              <SearchFeatureCard
                title={t('documentation.sections.knowledgeBase.trendAnalysisTitle')}
                description={t('documentation.sections.knowledgeBase.trendAnalysisDescription')}
                example={t('documentation.sections.knowledgeBase.trendAnalysisExample')}
                icon={FaChartLine}
              />
              
              <SearchFeatureCard
                title={t('documentation.sections.knowledgeBase.permissionBasedAccessTitle')}
                description={t('documentation.sections.knowledgeBase.permissionBasedAccessDescription')}
                example={t('documentation.sections.knowledgeBase.permissionBasedAccessExample')}
                icon={FaLock}
              />
            </SimpleGrid>
          </Box>
          
          {/* Export Options Section */}
          <Box>
            <HStack mb={4}>
              <Icon as={FaFileExport} w={6} h={6} color={colorMode === 'dark' ? "blue.300" : "blue.500"} />
              <Heading size="lg" color={colorMode === 'dark' ? "white" : "gray.900"}>{t('documentation.sections.knowledgeBase.exportOptionsTitle')}</Heading>
            </HStack>
            
            <Text fontSize="md" mb={4}>
              {t('documentation.sections.knowledgeBase.exportOptionsDescription')}
            </Text>
            
            <SimpleGrid columns={{ base: 2, md: 5 }} spacing={4} mb={4}>
              <ExportFormatCard format={t('documentation.sections.knowledgeBase.jsonExport')} icon={FaCode} color="#f0db4f" />
              <ExportFormatCard format={t('documentation.sections.knowledgeBase.csvExport')} icon={FaFile} color="#217346" />
              <ExportFormatCard format={t('documentation.sections.knowledgeBase.pdfExport')} icon={FaFile} color="#ff0000" />
              <ExportFormatCard format={t('documentation.sections.knowledgeBase.htmlExport')} icon={FaCode} color="#e34c26" />
              <ExportFormatCard format={t('documentation.sections.knowledgeBase.markdownExport')} icon={FaFile} color="#083fa1" />
            </SimpleGrid>
            
            <Box bg={colorMode === 'dark' ? "blue.900" : "blue.50"} p={3} borderRadius="md" mb={6}>
              <HStack>
                <Icon as={FaInfoCircle} color={colorMode === 'dark' ? "blue.300" : "blue.500"} />
                <Text fontSize="sm">{t('documentation.sections.knowledgeBase.customExportFormatsInfo')}</Text>
              </HStack>
            </Box>
          </Box>
          
          {/* API Access Section */}
          <Box>
            <HStack mb={4}>
              <Icon as={FaCode} w={6} h={6} color={colorMode === 'dark' ? "blue.300" : "blue.500"} />
              <Heading size="lg" color={colorMode === 'dark' ? "white" : "gray.900"}>{t('documentation.sections.knowledgeBase.apiAccessTitle')}</Heading>
            </HStack>
            
            <Text fontSize="md" mb={4}>
              {t('documentation.sections.knowledgeBase.apiAccessDescription')}
            </Text>
            
            <Card bg={colorMode === 'dark' ? "gray.800" : "white"} borderRadius="md" mb={4}>
              <CardBody>
                <VStack align="stretch" spacing={3}>
                  <Heading size="sm" mb={2}>{t('documentation.sections.knowledgeBase.restApiEndpointsTitle')}</Heading>
                  
                  <ApiEndpoint 
                    path="/api/v1/knowledge" 
                    description={t('documentation.sections.knowledgeBase.crudOperationsDescription')} 
                  />
                  
                  <ApiEndpoint 
                    path="/api/v1/search" 
                    description={t('documentation.sections.knowledgeBase.searchAcrossKnowledgeBaseDescription')} 
                  />
                  
                  <ApiEndpoint 
                    path="/api/v1/export" 
                    description={t('documentation.sections.knowledgeBase.exportKnowledgeDescription')} 
                  />
                  
                  <ApiEndpoint 
                    path="/api/v1/analytics" 
                    description={t('documentation.sections.knowledgeBase.knowledgeUsageAndTrendsDescription')} 
                  />
                </VStack>
              </CardBody>
            </Card>
            
            <Text fontSize="sm" color={colorMode === 'dark' ? "gray.400" : "gray.600"}>
              {t('documentation.sections.knowledgeBase.apiDocumentationInfo')}
            </Text>
          </Box>
        </VStack>
      </Container>
      
      <Footer />
    </Box>
  );
};

// FaCheckCircle component for API endpoints
const FaCheckCircle = (props: any) => {
  return (
    <svg
      stroke="currentColor"
      fill="currentColor"
      strokeWidth="0"
      viewBox="0 0 512 512"
      height="1em"
      width="1em"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path d="M504 256c0 136.967-111.033 248-248 248S8 392.967 8 256 119.033 8 256 8s248 111.033 248 248zM227.314 387.314l184-184c6.248-6.248 6.248-16.379 0-22.627l-22.627-22.627c-6.248-6.249-16.379-6.249-22.628 0L216 308.118l-70.059-70.059c-6.248-6.248-16.379-6.248-22.628 0l-22.627 22.627c-6.248 6.248-6.248 16.379 0 22.627l104 104c6.249 6.249 16.379 6.249 22.628.001z"></path>
    </svg>
  );
};

export default KnowledgeBase;
