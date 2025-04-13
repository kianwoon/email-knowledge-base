import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  Button,
  VStack,
  Spinner,
  Alert,
  AlertIcon,
  useColorModeValue,
  Input,
  FormControl,
  FormLabel,
  FormHelperText,
  useToast,
  Center
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import PageBanner from '../components/PageBanner'; // Assuming you have this component
import { getS3Config, configureS3, S3Config } from '../api/s3';

const S3ConfigurationPage: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const bgColor = useColorModeValue('gray.50', 'gray.800');
  const formBgColor = useColorModeValue('white', 'gray.700');

  const [currentConfig, setCurrentConfig] = useState<S3Config | null>(null);
  const [roleArnInput, setRoleArnInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch current config on mount
  const fetchConfig = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const config = await getS3Config();
      setCurrentConfig(config);
      setRoleArnInput(config?.role_arn || '');
    } catch (err: any) {
      console.error('Failed to fetch S3 config:', err);
      setError(t('s3ConfigurationPage.errors.loadFailed', 'Failed to load S3 configuration.'));
    } finally {
      setIsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Handle saving the configuration
  const handleSaveConfig = async () => {
    setIsSaving(true);
    setError(null);
    try {
      // Basic ARN validation
      if (!roleArnInput || !roleArnInput.startsWith('arn:aws:iam::') || !roleArnInput.includes(':role/')) {
        throw new Error(t('s3ConfigurationPage.errors.invalidArnFormat', 'Invalid AWS Role ARN format.'));
      }
      
      const updatedConfig = await configureS3(roleArnInput);
      setCurrentConfig(updatedConfig);
      setRoleArnInput(updatedConfig.role_arn || '');
      toast({
        title: t('s3ConfigurationPage.toast.saveSuccessTitle', 'Configuration Saved'),
        description: t('s3ConfigurationPage.toast.saveSuccessDescription', 'AWS S3 Role ARN has been updated.'),
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (err: any) {
      console.error('Failed to save S3 config:', err);
      const errorMessage = err?.response?.data?.detail || err.message || t('s3ConfigurationPage.errors.saveFailed', 'Failed to save S3 configuration.');
      setError(errorMessage);
      toast({
        title: t('s3ConfigurationPage.toast.saveErrorTitle', 'Save Failed'),
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Box bg={bgColor} minH="calc(100vh - 64px)"> {/* Adjust minH based on navbar height */}
      <PageBanner
        title={t('s3ConfigurationPage.title', 'AWS S3 Configuration')}
        subtitle={t('s3ConfigurationPage.subtitle', 'Configure access to your AWS S3 buckets via IAM Role assumption.')}
        gradient={useColorModeValue("linear(to-r, orange.400, yellow.400)", "linear(to-r, orange.600, yellow.600)")} // Example gradient
      />

      <Container maxW="container.lg" py={8}>
        {isLoading && (
          <Center py={10}>
            <Spinner size="xl" />
          </Center>
        )}

        {!isLoading && (
          <Box p={8} bg={formBgColor} borderRadius="lg" shadow="md">
            <VStack spacing={6} align="stretch">
              <Heading size="md">{t('s3ConfigurationPage.formHeading', 'Configure Assumed Role')}</Heading>
              <Text fontSize="sm" color={useColorModeValue('gray.600', 'gray.400')}>
                {t('s3ConfigurationPage.formDescription', 'Provide the ARN of the IAM Role that this application should assume to access your S3 buckets. This role needs appropriate S3 read permissions (e.g., ListBucket, GetObject).')}
              </Text>
              
              {error && !isSaving && (
                <Alert status="error" borderRadius="md">
                  <AlertIcon />
                  {error}
                </Alert>
              )}

              <FormControl isRequired>
                <FormLabel htmlFor="roleArn">{t('s3ConfigurationPage.roleArnLabel', 'IAM Role ARN')}</FormLabel>
                <Input
                  id="roleArn"
                  placeholder="arn:aws:iam::123456789012:role/YourS3AccessRole"
                  value={roleArnInput}
                  onChange={(e) => setRoleArnInput(e.target.value)}
                  isDisabled={isSaving}
                  bg={useColorModeValue('white', 'gray.800')} 
                />
                <FormHelperText>
                  {t('s3ConfigurationPage.roleArnHelp', 'The full ARN of the IAM role to assume.')}
                </FormHelperText>
              </FormControl>

              <Button
                colorScheme="orange" // Match S3 theme
                onClick={handleSaveConfig}
                isLoading={isSaving}
                isDisabled={isLoading}
                alignSelf="flex-start"
              >
                {t('common.save', 'Save Configuration')}
              </Button>
            </VStack>
          </Box>
        )}
      </Container>
    </Box>
  );
};

export default S3ConfigurationPage; 