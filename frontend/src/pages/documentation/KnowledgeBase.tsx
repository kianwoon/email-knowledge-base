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
  SimpleGrid,
  Card,
  CardBody,
  Badge,
  Flex,
  Code,
  Alert,
  AlertIcon,
  useColorMode
} from '@chakra-ui/react';
import { FaDatabase, FaSearch, FaFileExport, FaTag, FaCheckCircle, FaNetworkWired } from 'react-icons/fa';
import Footer from '../../components/Footer';
import PageBanner from '../../components/PageBanner';

const KnowledgeBase: React.FC = () => {
  const { colorMode } = useColorMode();
  
  return (
    <Box bg={colorMode === 'dark' ? "gray.900" : "gray.100"} minH="100vh" color={colorMode === 'dark' ? "white" : "gray.900"}>
      <PageBanner 
        title="Knowledge Base" 
        subtitle="Powerful vector database for storing, searching, and exporting your organization's knowledge."
        gradient={colorMode === 'dark' 
          ? "linear(to-r, neon.blue, neon.purple, neon.pink)"
          : "linear(to-r, brand.600, brand.500, brand.400)"
        }
      />
      
      <Container maxW="1200px" py={10}>
        <VStack spacing={8} align="stretch">
          {/* Header */}
          <HStack>
            <Icon as={FaDatabase} w={8} h={8} color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
            <Heading 
              size="xl" 
              bgGradient={colorMode === 'dark' 
                ? "linear(to-r, neon.blue, neon.purple)"
                : "linear(to-r, brand.600, brand.400)"
              }
              bgClip="text"
            >
              Knowledge Management
            </Heading>
          </HStack>
          
          <Text fontSize="lg">
            Our knowledge base provides a structured repository for your organization's valuable information,
            making it easy to store, search, and export knowledge extracted from your communications.
          </Text>
          
          <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
          
          {/* Knowledge Structure */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Knowledge Structure</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
              <Card 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="lg" 
                border="1px solid"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
                overflow="hidden"
                transition="all 0.3s"
                _hover={{ 
                  transform: 'translateY(-5px)', 
                  boxShadow: 'xl' 
                }}
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>Email Knowledge</Heading>
                    <Text color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Information extracted from email communications</Text>
                    
                    <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
                    
                    <Heading size="xs" color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Fields:</Heading>
                    <HStack spacing={2} flexWrap="wrap">
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Sender
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Recipients
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Date
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Subject
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Content
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Attachments
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Tags
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Priority
                      </Badge>
                    </HStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="lg" 
                border="1px solid"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
                overflow="hidden"
                transition="all 0.3s"
                _hover={{ 
                  transform: 'translateY(-5px)', 
                  boxShadow: 'xl' 
                }}
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>Document Knowledge</Heading>
                    <Text color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Information extracted from attached documents</Text>
                    
                    <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
                    
                    <Heading size="xs" color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Fields:</Heading>
                    <HStack spacing={2} flexWrap="wrap">
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Filename
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Type
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Size
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Created Date
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Modified Date
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Content
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Tags
                      </Badge>
                    </HStack>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="lg" 
                border="1px solid"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
                overflow="hidden"
                transition="all 0.3s"
                _hover={{ 
                  transform: 'translateY(-5px)', 
                  boxShadow: 'xl' 
                }}
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>Relationship Knowledge</Heading>
                    <Text color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Connections between people, topics, and content</Text>
                    
                    <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
                    
                    <Heading size="xs" color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Fields:</Heading>
                    <HStack spacing={2} flexWrap="wrap">
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Entity Type
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Entity Name
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Related Entities
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Relationship Type
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Strength
                      </Badge>
                      <Badge 
                        bg={colorMode === 'dark' ? "rgba(62, 242, 242, 0.2)" : "rgba(10, 124, 255, 0.1)"}
                        color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                        px={2} 
                        py={1} 
                        borderRadius="md"
                        mb={2}
                      >
                        Context
                      </Badge>
                    </HStack>
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
          
          {/* Search Capabilities */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Search Capabilities</Heading>
            
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <Card 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="lg" 
                border="1px solid"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
                overflow="hidden"
                transition="all 0.3s"
                _hover={{ 
                  transform: 'translateY(-5px)', 
                  boxShadow: 'xl' 
                }}
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <Flex
                      w="50px"
                      h="50px"
                      bg={colorMode === 'dark' ? "gray.900" : "gray.100"}
                      color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                      borderRadius="lg"
                      justify="center"
                      align="center"
                    >
                      <Icon as={FaSearch} w={6} h={6} />
                    </Flex>
                    
                    <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>Semantic Search</Heading>
                    <Text color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Find information based on meaning and context, not just exact keyword matches</Text>
                    
                    <Box 
                      w="100%" 
                      p={3} 
                      bg={colorMode === 'dark' ? "gray.900" : "gray.100"} 
                      borderRadius="md"
                    >
                      <Text fontFamily="mono" fontSize="sm" color={colorMode === 'dark' ? "white" : "gray.900"}>
                        Example: Show me all discussions about budget planning for Q3
                      </Text>
                    </Box>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="lg" 
                border="1px solid"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
                overflow="hidden"
                transition="all 0.3s"
                _hover={{ 
                  transform: 'translateY(-5px)', 
                  boxShadow: 'xl' 
                }}
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <Flex
                      w="50px"
                      h="50px"
                      bg={colorMode === 'dark' ? "gray.900" : "gray.100"}
                      color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                      borderRadius="lg"
                      justify="center"
                      align="center"
                    >
                      <Icon as={FaNetworkWired} w={6} h={6} />
                    </Flex>
                    
                    <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>Relationship Search</Heading>
                    <Text color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Discover connections between people and topics</Text>
                    
                    <Box 
                      w="100%" 
                      p={3} 
                      bg={colorMode === 'dark' ? "gray.900" : "gray.100"} 
                      borderRadius="md"
                    >
                      <Text fontFamily="mono" fontSize="sm" color={colorMode === 'dark' ? "white" : "gray.900"}>
                        Example: Who has been involved in the website redesign project?
                      </Text>
                    </Box>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="lg" 
                border="1px solid"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
                overflow="hidden"
                transition="all 0.3s"
                _hover={{ 
                  transform: 'translateY(-5px)', 
                  boxShadow: 'xl' 
                }}
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <Flex
                      w="50px"
                      h="50px"
                      bg={colorMode === 'dark' ? "gray.900" : "gray.100"}
                      color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                      borderRadius="lg"
                      justify="center"
                      align="center"
                    >
                      <Icon as={FaFileExport} w={6} h={6} />
                    </Flex>
                    
                    <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>Trend Analysis</Heading>
                    <Text color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Identify patterns and trends over time</Text>
                    
                    <Box 
                      w="100%" 
                      p={3} 
                      bg={colorMode === 'dark' ? "gray.900" : "gray.100"} 
                      borderRadius="md"
                    >
                      <Text fontFamily="mono" fontSize="sm" color={colorMode === 'dark' ? "white" : "gray.900"}>
                        Example: How has customer feedback evolved over the past 6 months?
                      </Text>
                    </Box>
                  </VStack>
                </CardBody>
              </Card>
              
              <Card 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="lg" 
                border="1px solid"
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
                overflow="hidden"
                transition="all 0.3s"
                _hover={{ 
                  transform: 'translateY(-5px)', 
                  boxShadow: 'xl' 
                }}
              >
                <CardBody>
                  <VStack align="flex-start" spacing={4}>
                    <Flex
                      w="50px"
                      h="50px"
                      bg={colorMode === 'dark' ? "gray.900" : "gray.100"}
                      color={colorMode === 'dark' ? "neon.blue" : "brand.600"}
                      borderRadius="lg"
                      justify="center"
                      align="center"
                    >
                      <Icon as={FaTag} w={6} h={6} />
                    </Flex>
                    
                    <Heading size="md" color={colorMode === 'dark' ? "white" : "gray.900"}>Permission-Based Access</Heading>
                    <Text color={colorMode === 'dark' ? "gray.400" : "gray.600"}>Results filtered based on user permissions</Text>
                    
                    <Box 
                      w="100%" 
                      p={3} 
                      bg={colorMode === 'dark' ? "gray.900" : "gray.100"} 
                      borderRadius="md"
                    >
                      <Text fontFamily="mono" fontSize="sm" color={colorMode === 'dark' ? "white" : "gray.900"}>
                        Example: Only show knowledge from departments I have access to
                      </Text>
                    </Box>
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>
          </Box>
          
          <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
          
          {/* Export Options */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>Export Options</Heading>
            
            <Text mb={4} color={colorMode === 'dark' ? "gray.400" : "gray.600"}>
              Knowledge can be exported in multiple formats to integrate with other systems or for offline reference.
            </Text>
            
            <SimpleGrid columns={{ base: 2, sm: 3, md: 5 }} spacing={4}>
              <HStack 
                p={2} 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="md" 
                border="1px solid" 
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
              >
                <Icon as={FaFileExport} color={colorMode === 'dark' ? "yellow.300" : "yellow.500"} />
                <Text fontWeight="bold">JSON</Text>
              </HStack>
              <HStack 
                p={2} 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="md" 
                border="1px solid" 
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
              >
                <Icon as={FaFileExport} color={colorMode === 'dark' ? "green.300" : "green.500"} />
                <Text fontWeight="bold">CSV</Text>
              </HStack>
              <HStack 
                p={2} 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="md" 
                border="1px solid" 
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
              >
                <Icon as={FaFileExport} color={colorMode === 'dark' ? "red.300" : "red.500"} />
                <Text fontWeight="bold">PDF</Text>
              </HStack>
              <HStack 
                p={2} 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="md" 
                border="1px solid" 
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
              >
                <Icon as={FaFileExport} color={colorMode === 'dark' ? "orange.300" : "orange.500"} />
                <Text fontWeight="bold">HTML</Text>
              </HStack>
              <HStack 
                p={2} 
                bg={colorMode === 'dark' ? "gray.800" : "gray.200"} 
                borderRadius="md" 
                border="1px solid" 
                borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"}
              >
                <Icon as={FaFileExport} color={colorMode === 'dark' ? "purple.300" : "purple.500"} />
                <Text fontWeight="bold">Markdown</Text>
              </HStack>
            </SimpleGrid>
            
            <Alert status="info" mt={6} bg={colorMode === 'dark' ? "gray.800" : "gray.200"} color={colorMode === 'dark' ? "white" : "gray.900"} borderRadius="md">
              <AlertIcon color={colorMode === 'dark' ? "neon.blue" : "brand.600"} />
              Custom export formats can be configured for enterprise customers to match your existing systems.
            </Alert>
          </Box>
          
          <Divider borderColor={colorMode === 'dark' ? "gray.700" : "gray.300"} />
          
          {/* API Access */}
          <Box>
            <Heading size="md" mb={4} color={colorMode === 'dark' ? "neon.blue" : "brand.600"}>API Access</Heading>
            
            <Text mb={4} color={colorMode === 'dark' ? "gray.400" : "gray.600"}>
              Integrate knowledge base functionality directly into your applications using our comprehensive API.
            </Text>
            
            <Card bg={colorMode === 'dark' ? "gray.800" : "gray.200"} borderRadius="md" mb={4}>
              <CardBody>
                <VStack align="flex-start" spacing={2}>
                  <Heading size="sm" color={colorMode === 'dark' ? "white" : "gray.900"}>REST API Endpoints</Heading>
                  <List spacing={2}>
                    <ListItem>
                      <HStack>
                        <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "green.300" : "green.500"} />
                        <Text color={colorMode === 'dark' ? "white" : "gray.900"}><Code>/api/v1/knowledge</Code> - CRUD operations for knowledge items</Text>
                      </HStack>
                    </ListItem>
                    <ListItem>
                      <HStack>
                        <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "green.300" : "green.500"} />
                        <Text color={colorMode === 'dark' ? "white" : "gray.900"}><Code>/api/v1/search</Code> - Search across the knowledge base</Text>
                      </HStack>
                    </ListItem>
                    <ListItem>
                      <HStack>
                        <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "green.300" : "green.500"} />
                        <Text color={colorMode === 'dark' ? "white" : "gray.900"}><Code>/api/v1/export</Code> - Export knowledge in various formats</Text>
                      </HStack>
                    </ListItem>
                    <ListItem>
                      <HStack>
                        <ListIcon as={FaCheckCircle} color={colorMode === 'dark' ? "green.300" : "green.500"} />
                        <Text color={colorMode === 'dark' ? "white" : "gray.900"}><Code>/api/v1/analytics</Code> - Knowledge usage and trends</Text>
                      </HStack>
                    </ListItem>
                  </List>
                </VStack>
              </CardBody>
            </Card>
            
            <Text fontSize="sm" color={colorMode === 'dark' ? "gray.500" : "gray.700"}>
              Comprehensive API documentation is available for developers, including authentication, rate limits, and example code.
            </Text>
          </Box>
        </VStack>
      </Container>
      
      <Footer />
    </Box>
  );
};

export default KnowledgeBase;
