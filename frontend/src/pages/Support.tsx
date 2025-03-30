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
  Link,
  Button,
  Card,
  CardBody,
  SimpleGrid,
  Flex,
} from '@chakra-ui/react';
import { FaEnvelope, FaMapMarkerAlt, FaBuilding, FaGlobe } from 'react-icons/fa';
import Footer from '../components/Footer';
import PageBanner from '../components/PageBanner';
import { useTranslation } from 'react-i18next';

const Support: React.FC = () => {
  const { t } = useTranslation();
  
  return (
    <Box bg="bg.primary" minH="100vh" color="text.primary">
      <PageBanner 
        title={t('support.title')}
        subtitle={t('support.subtitle')}
      />
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Introduction Text */}
          <Text fontSize="lg">
            {t('support.introduction')}
          </Text>
          
          <Divider borderColor="border.primary" />
          
          {/* Contact Information */}
          <Box>
            <Heading size="md" color="text.highlight" mb={6}>{t('support.contactInformation')}</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={8}>
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaBuilding} color="text.highlight" w={6} h={6} />
                      <Heading size="md" color="text.primary">{t('support.companyInfo.title')}</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text fontWeight="bold" color="text.primary">{t('support.companyInfo.name')}</Text>
                      <Text color="text.secondary">{t('support.companyInfo.department')}</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaEnvelope} color="text.highlight" w={6} h={6} />
                      <Heading size="md" color="text.primary">{t('support.emailSupport.title')}</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Link href="mailto:BFSI_SG@beyondsoft.com" color="text.highlight" fontWeight="bold">
                        {t('support.emailSupport.email')}
                      </Link>
                      <Text color="text.secondary">{t('support.emailSupport.description')}</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaMapMarkerAlt} color="text.highlight" w={6} h={6} />
                      <Heading size="md" color="text.primary">{t('support.officeLocation.title')}</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text color="text.primary">{t('support.officeLocation.address1')}</Text>
                      <Text color="text.primary">{t('support.officeLocation.address2')}</Text>
                      <Text color="text.primary">{t('support.officeLocation.address3')}</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg="bg.secondary" 
                borderRadius="lg" 
                border="1px solid"
                borderColor="border.primary"
                overflow="hidden"
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <HStack>
                      <Icon as={FaGlobe} color="text.highlight" w={6} h={6} />
                      <Heading size="md" color="text.primary">{t('support.businessHours.title')}</Heading>
                    </HStack>
                    
                    <VStack align="flex-start" spacing={2} pl={10}>
                      <Text color="text.primary">{t('support.businessHours.weekdays')}</Text>
                      <Text color="text.primary">{t('support.businessHours.weekend')}</Text>
                      <Text color="text.primary">{t('support.businessHours.email')}</Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor="border.primary" />
          
          {/* Support Options */}
          <Box>
            <Heading size="md" color="text.highlight" mb={6}>{t('support.supportOptions.title')}</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <SupportOption 
                title={t('support.supportOptions.technicalSupport.title')}
                description={t('support.supportOptions.technicalSupport.description')}
              />
              
              <SupportOption 
                title={t('support.supportOptions.productTraining.title')}
                description={t('support.supportOptions.productTraining.description')}
              />
              
              <SupportOption 
                title={t('support.supportOptions.customIntegration.title')}
                description={t('support.supportOptions.customIntegration.description')}
              />
            </SimpleGrid>
          </Box>
          
          {/* CTA */}
          <Box 
            bg="bg.secondary" 
            p={6} 
            borderRadius="lg" 
            border="1px solid"
            borderColor="border.primary"
            mt={4}
          >
            <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" align="center">
              <VStack align={{ base: 'center', md: 'flex-start' }} spacing={2} mb={{ base: 4, md: 0 }}>
                <Heading size="md" color="text.primary">{t('support.cta.title')}</Heading>
                <Text color="text.secondary">{t('support.cta.description')}</Text>
              </VStack>
              
              <Button 
                as={Link} 
                href="mailto:BFSI_SG@beyondsoft.com" 
                colorScheme="blue"
                size="lg"
                _hover={{ textDecoration: 'none' }}
              >
                {t('support.cta.button')}
              </Button>
            </Flex>
          </Box>
        </VStack>
      </Container>
      <Footer />
    </Box>
  );
};

// Support Option Component
const SupportOption = ({ title, description }: { title: string, description: string }) => {
  return (
    <Box
      p={5}
      bg="bg.tertiary"
      borderRadius="lg"
      border="1px solid"
      borderColor="border.primary"
      height="100%"
    >
      <VStack align="flex-start" spacing={3}>
        <Heading size="sm" color="text.primary">{title}</Heading>
        <Text color="text.secondary">{description}</Text>
      </VStack>
    </Box>
  );
};

export default Support;
