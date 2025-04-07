import React from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  HStack,
  Icon,
  Divider,
  List,
  ListItem,
  ListIcon,
  Alert,
  AlertIcon,
  SimpleGrid,
  Card,
  CardBody,
  Flex,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  useColorMode
} from '@chakra-ui/react';
import { FaBrain, FaShieldAlt, FaTag, FaEye, FaLock, FaChartLine, FaExclamationTriangle } from 'react-icons/fa';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';
import { useTranslation } from 'react-i18next';

const AIAnalysis: React.FC = () => {
  const { colorMode } = useColorMode();
  const { t } = useTranslation();
  
  return (
    <Box bg="bg.primary" minH="100vh" color="text.primary">
      <PageBanner 
        title={t('documentation.sections.analysis.title')} 
        subtitle={t('documentation.sections.analysis.description')}
        gradient={colorMode === 'dark' 
          ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
          : "linear(to-r, brand.600, brand.500, brand.400)"
        }
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaBrain} w={8} h={8} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
            <Heading 
              size="xl" 
              bgGradient={colorMode === 'dark' 
                ? "linear(to-r, neon.blue, neon.purple)"
                : "linear(to-r, brand.600, brand.400)"
              }
              bgClip="text"
            >
              {t('documentation.sections.analysis.header')}
            </Heading>
          </HStack>
          
          <Text fontSize="lg" color="text.primary">
            {t('documentation.sections.analysis.description')}
          </Text>
          
          <Divider borderColor="border.primary" />
          
          {/* Main Content */}
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={10}>
            {/* Left Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.analysis.capabilities.title')}</Heading>
              
              <List spacing={4}>
                <ListItem>
                  <HStack>
                    <ListIcon as={FaTag} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.analysis.capabilities.classification.title')}:</strong> {t('documentation.sections.analysis.capabilities.classification.description')}</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaShieldAlt} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.analysis.capabilities.pii.title')}:</strong> {t('documentation.sections.analysis.capabilities.pii.description')}</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaEye} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.analysis.capabilities.summarization.title')}:</strong> {t('documentation.sections.analysis.capabilities.summarization.description')}</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaLock} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.analysis.capabilities.sensitivity.title')}:</strong> {t('documentation.sections.analysis.capabilities.sensitivity.description')}</Text>
                  </HStack>
                </ListItem>
                
                <ListItem>
                  <HStack>
                    <ListIcon as={FaChartLine} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                    <Text color="text.primary"><strong>{t('documentation.sections.analysis.capabilities.extraction.title')}:</strong> {t('documentation.sections.analysis.capabilities.extraction.description')}</Text>
                  </HStack>
                </ListItem>
              </List>
              
              <Alert status="info" bg="bg.info" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                {t('documentation.sections.analysis.info')}
              </Alert>
              
              <Box>
                <Heading size="sm" mb={2} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.analysis.model.title')}</Heading>
                <Card bg="bg.secondary" borderRadius="md">
                  <CardBody>
                    <SimpleGrid columns={2} spacing={4}>
                      <Stat>
                        <StatLabel color="text.secondary">{t('documentation.sections.analysis.model.base')}</StatLabel>
                        <StatNumber fontSize="md" color="text.primary">ChatGPT-4o mini</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="text.secondary">{t('documentation.sections.analysis.model.fineTuning')}</StatLabel>
                        <StatNumber fontSize="md" color="text.primary">Business Communications</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="text.secondary">{t('documentation.sections.analysis.model.context')}</StatLabel>
                        <StatNumber fontSize="md" color="text.primary">16K tokens</StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel color="text.secondary">{t('documentation.sections.analysis.model.speed')}</StatLabel>
                        <StatNumber fontSize="md" color="text.primary">~3-5 sec/email</StatNumber>
                      </Stat>
                    </SimpleGrid>
                  </CardBody>
                </Card>
              </Box>
            </VStack>
            
            {/* Right Column */}
            <VStack align="stretch" spacing={6}>
              <Heading size="md" color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.analysis.process.title')}</Heading>
              
              <SimpleGrid columns={1} spacing={4}>
                <ProcessStepCard 
                  number="01"
                  title={t('documentation.sections.analysis.process.step1.title')}
                  description={t('documentation.sections.analysis.process.step1.description')}
                  progress={100}
                />
                
                <ProcessStepCard 
                  number="02"
                  title={t('documentation.sections.analysis.process.step2.title')}
                  description={t('documentation.sections.analysis.process.step2.description')}
                  progress={100}
                />
                
                <ProcessStepCard 
                  number="03"
                  title={t('documentation.sections.analysis.process.step3.title')}
                  description={t('documentation.sections.analysis.process.step3.description')}
                  progress={100}
                />
                
                <ProcessStepCard 
                  number="04"
                  title={t('documentation.sections.analysis.process.step4.title')}
                  description={t('documentation.sections.analysis.process.step4.description')}
                  progress={100}
                />
                
                <ProcessStepCard 
                  number="05"
                  title={t('documentation.sections.analysis.process.step5.title')}
                  description={t('documentation.sections.analysis.process.step5.description')}
                  progress={100}
                />
              </SimpleGrid>
              
              <Alert status="warning" bg="bg.warning" color="text.primary" borderRadius="md">
                <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
                {t('documentation.sections.analysis.warning')}
              </Alert>
            </VStack>
          </SimpleGrid>
          
          <Divider borderColor="border.primary" />
          
          {/* Classification Categories */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.analysis.classification.title')}</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <ClassificationCard 
                title={t('documentation.sections.analysis.classification.department.title')}
                description={t('documentation.sections.analysis.classification.department.description')}
                tags={[
                  t('documentation.sections.analysis.classification.tags.executive'), 
                  t('documentation.sections.analysis.classification.tags.sales'), 
                  t('documentation.sections.analysis.classification.tags.marketing'), 
                  t('documentation.sections.analysis.classification.tags.finance'), 
                  t('documentation.sections.analysis.classification.tags.legal'), 
                  t('documentation.sections.analysis.classification.tags.hr'), 
                  t('documentation.sections.analysis.classification.tags.it'), 
                  t('documentation.sections.analysis.classification.tags.operations'), 
                  t('documentation.sections.analysis.classification.tags.customerSupport')
                ]}
              />
              
              <ClassificationCard 
                title={t('documentation.sections.analysis.classification.type.title')}
                description={t('documentation.sections.analysis.classification.type.description')}
                tags={[
                  t('documentation.sections.analysis.classification.tags.policy'), 
                  t('documentation.sections.analysis.classification.tags.procedure'), 
                  t('documentation.sections.analysis.classification.tags.decision'), 
                  t('documentation.sections.analysis.classification.tags.report'), 
                  t('documentation.sections.analysis.classification.tags.analysis'), 
                  t('documentation.sections.analysis.classification.tags.discussion'), 
                  t('documentation.sections.analysis.classification.tags.approval'), 
                  t('documentation.sections.analysis.classification.tags.request'), 
                  t('documentation.sections.analysis.classification.tags.notification')
                ]}
              />
              
              <ClassificationCard 
                title={t('documentation.sections.analysis.classification.sensitivity.title')}
                description={t('documentation.sections.analysis.classification.sensitivity.description')}
                tags={[
                  t('documentation.sections.analysis.classification.tags.public'), 
                  t('documentation.sections.analysis.classification.tags.internal'), 
                  t('documentation.sections.analysis.classification.tags.confidential'), 
                  t('documentation.sections.analysis.classification.tags.restricted'), 
                  t('documentation.sections.analysis.classification.tags.pii'), 
                  t('documentation.sections.analysis.classification.tags.financial'), 
                  t('documentation.sections.analysis.classification.tags.legal'), 
                  t('documentation.sections.analysis.classification.tags.strategic')
                ]}
              />
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="border.primary" />
          
          {/* PII Detection */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>{t('documentation.sections.analysis.pii.title')}</Heading>
            
            <Text mb={4} color="text.primary">
              {t('documentation.sections.analysis.pii.description')}
            </Text>
            
            <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={6}>
              <PIITag label={t('documentation.sections.analysis.pii.names')} />
              <PIITag label={t('documentation.sections.analysis.pii.emails')} />
              <PIITag label={t('documentation.sections.analysis.pii.phoneNumbers')} />
              <PIITag label={t('documentation.sections.analysis.pii.addresses')} />
              <PIITag label={t('documentation.sections.analysis.pii.ssn')} />
              <PIITag label={t('documentation.sections.analysis.pii.financialData')} />
              <PIITag label={t('documentation.sections.analysis.pii.healthInformation')} />
              <PIITag label={t('documentation.sections.analysis.pii.credentials')} />
            </SimpleGrid>
            
            <Alert status="success" bg="bg.success" color="text.primary" borderRadius="md">
              <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
              {t('documentation.sections.analysis.pii.success')}
            </Alert>
          </Box>
        </VStack>
      </Container>
      
      <Footer />
    </Box>
  );
};

// Process Step Card Component
const ProcessStepCard: React.FC<{ 
  number: string, 
  title: string, 
  description: string,
  progress: number
}> = ({ number, title, description, progress }) => {
  const { colorMode } = useColorMode();
  
  return (
    <Card 
      bg="bg.secondary" 
      borderRadius="md" 
      overflow="hidden"
      position="relative"
      border="1px solid"
      borderColor="border.primary"
    >
      <CardBody>
        <Flex align="center" mb={2}>
          <Box 
            w="30px" 
            h="30px" 
            borderRadius="full" 
            bg={colorMode === 'dark' ? "neon.blue" : "brand.600"}
            color="white"
            display="flex"
            alignItems="center"
            justifyContent="center"
            fontWeight="bold"
            mr={3}
          >
            {number}
          </Box>
          <Heading size="sm" color="text.primary">{title}</Heading>
        </Flex>
        <Text color="text.secondary" fontSize="sm" mb={3}>{description}</Text>
        <Progress 
          value={progress} 
          size="sm" 
          colorScheme={colorMode === 'dark' ? "cyan" : "blue"} 
          borderRadius="full" 
        />
      </CardBody>
    </Card>
  );
};

// Classification Card Component
const ClassificationCard: React.FC<{ 
  title: string, 
  description: string,
  tags: string[] 
}> = ({ title, description, tags }) => {
  const { colorMode } = useColorMode();
  
  // Color mapping for tags - similar to the email knowledge card
  const getTagColor = (index: number) => {
    const colors = [
      { bg: "blue.100", darkBg: "rgba(66, 153, 225, 0.3)", color: "blue.800", darkColor: "blue.200" },
      { bg: "green.100", darkBg: "rgba(72, 187, 120, 0.3)", color: "green.800", darkColor: "green.200" },
      { bg: "purple.100", darkBg: "rgba(159, 122, 234, 0.3)", color: "purple.800", darkColor: "purple.200" },
      { bg: "red.100", darkBg: "rgba(245, 101, 101, 0.3)", color: "red.800", darkColor: "red.200" },
      { bg: "orange.100", darkBg: "rgba(237, 137, 54, 0.3)", color: "orange.800", darkColor: "orange.200" },
      { bg: "yellow.100", darkBg: "rgba(236, 201, 75, 0.3)", color: "yellow.800", darkColor: "yellow.200" },
      { bg: "pink.100", darkBg: "rgba(237, 100, 166, 0.3)", color: "pink.800", darkColor: "pink.200" },
      { bg: "cyan.100", darkBg: "rgba(103, 232, 249, 0.3)", color: "cyan.800", darkColor: "cyan.200" },
      { bg: "teal.100", darkBg: "rgba(79, 209, 197, 0.3)", color: "teal.800", darkColor: "teal.200" }
    ];
    
    return colors[index % colors.length];
  };
  
  return (
    <Card 
      bg="bg.secondary" 
      borderRadius="md"
      border="1px solid"
      borderColor="border.primary"
    >
      <CardBody>
        <Heading size="sm" mb={2} color="text.primary">{title}</Heading>
        <Text fontSize="sm" color="text.secondary" mb={4}>{description}</Text>
        <Flex wrap="wrap" gap={2}>
          {tags.map((tag, index) => {
            const tagColor = getTagColor(index);
            return (
              <Box 
                key={index}
                bg={colorMode === 'dark' ? tagColor.darkBg : tagColor.bg}
                color={colorMode === 'dark' ? tagColor.darkColor : tagColor.color}
                px={2}
                py={1}
                borderRadius="md"
                fontSize="xs"
                fontWeight="bold"
                textAlign="center"
              >
                {tag}
              </Box>
            );
          })}
        </Flex>
      </CardBody>
    </Card>
  );
};

// PII Tag Component
const PIITag: React.FC<{ label: string }> = ({ label }) => {
  const { colorMode } = useColorMode();
  
  return (
    <Flex 
      bg="bg.warning" 
      p={3} 
      borderRadius="md" 
      align="center"
      border="1px solid"
      borderColor="border.primary"
    >
      <Icon as={FaExclamationTriangle} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} mr={2} />
      <Text fontSize="sm" fontWeight="medium" color="text.primary">{label}</Text>
    </Flex>
  );
};

export default AIAnalysis;
