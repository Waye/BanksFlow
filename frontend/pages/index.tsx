import { Box, Container, Heading, Text, VStack, Button, Grid, GridItem, Stat, StatLabel, StatNumber, StatHelpText, useToast, SimpleGrid, Accordion, AccordionItem, AccordionButton, AccordionPanel, AccordionIcon, HStack, FormControl, FormLabel, Input, Select, AlertDialog, AlertDialogBody, AlertDialogFooter, AlertDialogHeader, AlertDialogContent, AlertDialogOverlay, useDisclosure } from '@chakra-ui/react';
import { useQuery, useMutation } from 'react-query';
import axios from 'axios';
import { useCallback, useState, useEffect } from 'react';
import { usePlaidLink } from 'react-plaid-link';
import React from 'react';
import { useQueryClient } from 'react-query';

// 临时用户ID，实际应用中应该从认证系统获取
const TEMP_USER_ID = 'test_user_1';

export default function Home() {
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const cancelRef = React.useRef();
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState('30');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [showDateSelector, setShowDateSelector] = useState(false);
  const [connectionStartDate, setConnectionStartDate] = useState('');
  const [connectionEndDate, setConnectionEndDate] = useState('');
  const queryClient = useQueryClient();

  // Calculate date range based on selection
  const getDateRange = () => {
    const endDate = new Date();
    let startDate = new Date();

    if (dateRange === 'custom') {
      if (!customStartDate || !customEndDate) {
        return null;
      }
      return {
        start_date: customStartDate,
        end_date: customEndDate
      };
    }

    const days = parseInt(dateRange);
    startDate.setDate(endDate.getDate() - days);
    
    return {
      start_date: startDate.toISOString().split('T')[0],
      end_date: endDate.toISOString().split('T')[0]
    };
  };

  // 获取账户汇总信息
  const { data: summary, isLoading: isLoadingSummary } = useQuery(
    ['summary', dateRange, customStartDate, customEndDate],
    async () => {
      const dateRangeParams = getDateRange();
      if (!dateRangeParams) return null;
      
      const response = await axios.get(`http://127.0.0.1:8000/summary/${TEMP_USER_ID}`, {
        params: dateRangeParams
      });
      return response.data;
    },
    {
      enabled: !!getDateRange()
    }
  );

  // 获取账户列表
  const { data: accounts, isLoading: isLoadingAccounts } = useQuery(
    'accounts',
    async () => {
      const response = await axios.get(`http://127.0.0.1:8000/accounts/${TEMP_USER_ID}`);
      return response.data;
    }
  );

  // 获取交易记录
  const { data: transactions, isLoading: isLoadingTransactions } = useQuery(
    'transactions',
    async () => {
      const response = await axios.get(`http://127.0.0.1:8000/transactions/${TEMP_USER_ID}`);
      return response.data;
    }
  );

  // 创建 link token
  const createLinkTokenMutation = useMutation(
    async () => {
      console.log('Creating link token...');
      const response = await axios.post('http://127.0.0.1:8000/create_link_token');
      console.log('Link token response:', response.data);
      return response.data;
    },
    {
      onSuccess: (data) => {
        console.log('Link token created successfully:', data);
        setLinkToken(data.link_token);
      },
      onError: (error: any) => {
        console.error('Error creating link token:', error);
        console.error('Error response:', error.response?.data);
        toast({
          title: 'Error',
          description: error.response?.data?.detail || 'Failed to create link token',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    }
  );

  // 交换 public token
  const exchangeTokenMutation = useMutation(
    async (publicToken: string) => {
      // If no dates selected, use last 30 days
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(endDate.getDate() - 30);

      const finalStartDate = connectionStartDate || startDate.toISOString().split('T')[0];
      const finalEndDate = connectionEndDate || endDate.toISOString().split('T')[0];

      const response = await axios.post('http://127.0.0.1:8000/exchange_token', {
        public_token: publicToken,
        user_id: TEMP_USER_ID,
        start_date: finalStartDate,
        end_date: finalEndDate
      });
      return response.data;
    },
    {
      onSuccess: (data) => {
        toast({
          title: 'Success',
          description: `Successfully connected account from ${data.institution_name}`,
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
        // Invalidate queries to refresh the UI
        queryClient.invalidateQueries(['summary']);
        queryClient.invalidateQueries(['accounts']);
        queryClient.invalidateQueries(['transactions']);
        // Force a page refresh after 2 seconds
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      },
      onError: (error: any) => {
        console.error('Token exchange error:', error);
        toast({
          title: 'Error',
          description: error.response?.data?.detail || 'Failed to connect account',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    }
  );

  // Add cleanup mutation
  const cleanupMutation = useMutation(
    async () => {
      const response = await axios.post('http://127.0.0.1:8000/clean_test_data', {
        user_id: TEMP_USER_ID
      });
      return response.data;
    },
    {
      onSuccess: () => {
        toast({
          title: 'Success',
          description: 'Test data cleaned successfully',
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
        // Invalidate queries to refresh the UI
        queryClient.invalidateQueries(['summary']);
        queryClient.invalidateQueries(['accounts']);
        queryClient.invalidateQueries(['transactions']);
        onClose();
      },
      onError: (error: any) => {
        toast({
          title: 'Error',
          description: error.response?.data?.detail || 'Failed to clean test data',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    }
  );

  const onSuccess = useCallback(async (publicToken: string) => {
    try {
      await exchangeTokenMutation.mutateAsync(publicToken);
    } catch (error) {
      console.error('Error in onSuccess:', error);
    }
  }, []);

  const onExit = useCallback(() => {
    console.log('User exited Plaid Link');
  }, []);

  const onEvent = useCallback((eventName: string, metadata: any) => {
    console.log('Plaid Link event:', eventName, metadata);
  }, []);

  const onLoad = useCallback(() => {
    console.log('Plaid Link loaded');
  }, []);

  // 初始化 Plaid Link
  useEffect(() => {
    let mounted = true;

    const initializePlaidLink = async () => {
      try {
        if (mounted) {
          await createLinkTokenMutation.mutateAsync();
        }
      } catch (error) {
        console.error('Error initializing Plaid Link:', error);
      }
    };

    initializePlaidLink();

    return () => {
      mounted = false;
    };
  }, []);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
    onExit,
    onEvent,
    onLoad,
    language: 'en',
    countryCodes: ['CA', 'US'],
    env: 'sandbox'
  });

  const handleConnectBank = useCallback(() => {
    if (!ready) {
      toast({
        title: 'Error',
        description: 'Plaid Link is not ready',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      return;
    }

    // If no dates selected, use last 30 days
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - 30);

    const finalStartDate = connectionStartDate || startDate.toISOString().split('T')[0];
    const finalEndDate = connectionEndDate || endDate.toISOString().split('T')[0];

    try {
      open();
    } catch (error) {
      console.error('Error opening Plaid Link:', error);
      toast({
        title: 'Error',
        description: 'Failed to open Plaid Link',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [ready, open, connectionStartDate, connectionEndDate]);

  return (
    <Box p={8}>
      <VStack spacing={8} align="stretch">
        <HStack justify="space-between">
          <Heading as="h1" size="2xl">
            Personal Finance Dashboard
          </Heading>
          <Button
            colorScheme="red"
            onClick={onOpen}
            isLoading={cleanupMutation.isLoading}
          >
            Clean Test Data
          </Button>
        </HStack>
        
        {/* Date Range Selection for Connection */}
        <Box p={4} borderWidth="1px" borderRadius="lg">
          <Text mb={2} fontWeight="bold">Select Historical Data Range (Optional)</Text>
          <Text mb={4} color="gray.600" fontSize="sm">
            Choose a date range for historical data when connecting your bank account. If no dates are selected, the last 30 days of data will be fetched.
          </Text>
          <HStack spacing={4}>
            <FormControl>
              <FormLabel>Start Date (Optional)</FormLabel>
              <Input
                type="date"
                value={connectionStartDate}
                onChange={(e) => setConnectionStartDate(e.target.value)}
                max={new Date().toISOString().split('T')[0]}
                min={new Date(new Date().setFullYear(new Date().getFullYear() - 5)).toISOString().split('T')[0]}
              />
            </FormControl>
            <FormControl>
              <FormLabel>End Date (Optional)</FormLabel>
              <Input
                type="date"
                value={connectionEndDate}
                onChange={(e) => setConnectionEndDate(e.target.value)}
                max={new Date().toISOString().split('T')[0]}
                min={new Date(new Date().setFullYear(new Date().getFullYear() - 5)).toISOString().split('T')[0]}
              />
            </FormControl>
          </HStack>
        </Box>
        
        <Button
          colorScheme="blue"
          onClick={handleConnectBank}
          isLoading={createLinkTokenMutation.isLoading || exchangeTokenMutation.isLoading}
          loadingText="Connecting..."
          isDisabled={!ready || !linkToken}
        >
          Connect Bank Account
        </Button>

        {/* Review Historical Data Section - Always visible */}
        <Box p={4} borderWidth="1px" borderRadius="lg">
          <Text mb={2} fontWeight="bold">Review Historical Data</Text>
          <Text mb={4} color="gray.600" fontSize="sm">
            {summary 
              ? "Your account includes 5 years of historical transaction data. Select a date range to view specific periods."
              : "Connect your bank account to view historical transaction data. You can select different date ranges to analyze your spending patterns."}
          </Text>
          <HStack spacing={4}>
            <FormControl>
              <FormLabel>Date Range</FormLabel>
              <Select
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
              >
                <option value="30">Last 30 Days</option>
                <option value="90">Last 90 Days</option>
                <option value="180">Last 6 Months</option>
                <option value="365">Last Year</option>
                <option value="custom">Custom Range (up to 5 years)</option>
              </Select>
            </FormControl>

            {dateRange === 'custom' && (
              <>
                <FormControl>
                  <FormLabel>Start Date</FormLabel>
                  <Input
                    type="date"
                    value={customStartDate}
                    onChange={(e) => setCustomStartDate(e.target.value)}
                    max={new Date().toISOString().split('T')[0]}
                    min={new Date(new Date().setFullYear(new Date().getFullYear() - 5)).toISOString().split('T')[0]}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>End Date</FormLabel>
                  <Input
                    type="date"
                    value={customEndDate}
                    onChange={(e) => setCustomEndDate(e.target.value)}
                    max={new Date().toISOString().split('T')[0]}
                    min={new Date(new Date().setFullYear(new Date().getFullYear() - 5)).toISOString().split('T')[0]}
                  />
                </FormControl>
              </>
            )}
          </HStack>
        </Box>

        {isLoadingSummary ? (
          <Text>Loading summary...</Text>
        ) : summary ? (
          <>
            <Grid templateColumns="repeat(3, 1fr)" gap={6}>
              <GridItem>
                <Stat>
                  <StatLabel>Total Balance</StatLabel>
                  <StatNumber>${summary.total_balance.toFixed(2)}</StatNumber>
                  <StatHelpText>Last updated: {new Date(summary.last_updated).toLocaleString()}</StatHelpText>
                </Stat>
              </GridItem>
              <GridItem>
                <Stat>
                  <StatLabel>Total Transactions</StatLabel>
                  <StatNumber>${summary.total_recent_transactions.toFixed(2)}</StatNumber>
                  <StatHelpText>Selected period</StatHelpText>
                </Stat>
              </GridItem>
              <GridItem>
                <Stat>
                  <StatLabel>Account Types</StatLabel>
                  <StatNumber>{Object.keys(summary.account_types || {}).length}</StatNumber>
                  <StatHelpText>Connected accounts</StatHelpText>
                </Stat>
              </GridItem>
            </Grid>

            {/* Financial Institutions Section */}
            <Box>
              <Heading size="md" mb={4}>Financial Institutions</Heading>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                {Object.entries(summary.institutions || {}).map(([name, data]: [string, any]) => (
                  <Box key={name} p={4} borderWidth="1px" borderRadius="lg">
                    <Heading size="sm" mb={2}>{name}</Heading>
                    <Text>Total Balance: ${data.total_balance.toFixed(2)}</Text>
                    <Text>Number of Accounts: {data.accounts.length}</Text>
                    <Text>Recent Transactions: {data.recent_transactions.length}</Text>
                    <Text color={name === "Unknown Institution" ? "red.500" : "inherit"}>
                      {name === "Unknown Institution" ? "⚠️ Institution name not available" : ""}
                    </Text>
                    <Accordion allowToggle>
                      <AccordionItem>
                        <h3>
                          <AccordionButton>
                            <Box flex="1" textAlign="left">
                              View Accounts
                            </Box>
                            <AccordionIcon />
                          </AccordionButton>
                        </h3>
                        <AccordionPanel pb={4}>
                          <VStack align="stretch" spacing={2}>
                            {data.accounts.map((account: any) => (
                              <Box key={account.account_id} p={2} bg="gray.50" borderRadius="md">
                                <Text fontWeight="bold">{account.name}</Text>
                                <Text>Type: {account.type}</Text>
                                <Text>Balance: ${account.balances.current.toFixed(2)}</Text>
                              </Box>
                            ))}
                          </VStack>
                        </AccordionPanel>
                      </AccordionItem>
                    </Accordion>
                  </Box>
                ))}
              </SimpleGrid>
            </Box>

            {/* Account Types Section */}
            <Box>
              <Heading size="md" mb={4}>Account Types</Heading>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                {Object.entries(summary.account_types || {}).map(([type, data]: [string, any]) => (
                  <Box key={type} p={4} borderWidth="1px" borderRadius="lg">
                    <Heading size="sm" mb={2}>{type.toUpperCase()}</Heading>
                    <Text>Total Balance: ${data.total_balance.toFixed(2)}</Text>
                    <Text>Recent Transactions: {data.recent_transactions.length}</Text>
                    <Accordion allowToggle>
                      <AccordionItem>
                        <h3>
                          <AccordionButton>
                            <Box flex="1" textAlign="left">
                              View Accounts
                            </Box>
                            <AccordionIcon />
                          </AccordionButton>
                        </h3>
                        <AccordionPanel pb={4}>
                          <VStack align="stretch" spacing={2}>
                            {data.accounts.map((account: any) => (
                              <Box key={account.account_id} p={2} bg="gray.50" borderRadius="md">
                                <Text fontWeight="bold">{account.name}</Text>
                                <Text>Institution: {account.institution_name}</Text>
                                <Text>Balance: ${account.balances.current.toFixed(2)}</Text>
                              </Box>
                            ))}
                          </VStack>
                        </AccordionPanel>
                      </AccordionItem>
                    </Accordion>
                  </Box>
                ))}
              </SimpleGrid>
            </Box>

            {/* Transaction Categories Section */}
            <Box>
              <Heading size="md" mb={4}>Transaction Categories</Heading>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                {Object.entries(summary.categories || {}).map(([category, data]: [string, any]) => (
                  <Box key={category} p={4} borderWidth="1px" borderRadius="lg">
                    <Heading size="sm" mb={2}>{category}</Heading>
                    <Text>Total Amount: ${data.total_amount.toFixed(2)}</Text>
                    <Text>Number of Transactions: {data.count}</Text>
                    <Accordion allowToggle>
                      <AccordionItem>
                        <h3>
                          <AccordionButton>
                            <Box flex="1" textAlign="left">
                              View Transactions
                            </Box>
                            <AccordionIcon />
                          </AccordionButton>
                        </h3>
                        <AccordionPanel pb={4}>
                          <VStack align="stretch" spacing={2}>
                            {data.transactions.map((transaction: any) => (
                              <Box key={transaction.transaction_id} p={2} bg="gray.50" borderRadius="md">
                                <Text fontWeight="bold">{transaction.name}</Text>
                                <Text>Amount: ${transaction.amount.toFixed(2)}</Text>
                                <Text>Date: {transaction.date}</Text>
                                {transaction.merchant_name && (
                                  <Text>Merchant: {transaction.merchant_name}</Text>
                                )}
                              </Box>
                            ))}
                          </VStack>
                        </AccordionPanel>
                      </AccordionItem>
                    </Accordion>
                  </Box>
                ))}
              </SimpleGrid>
            </Box>
          </>
        ) : (
          <Text>No financial data available. Connect your bank account to get started.</Text>
        )}

        {/* Add AlertDialog for cleanup confirmation */}
        <AlertDialog
          isOpen={isOpen}
          leastDestructiveRef={cancelRef}
          onClose={onClose}
        >
          <AlertDialogOverlay>
            <AlertDialogContent>
              <AlertDialogHeader fontSize='lg' fontWeight='bold'>
                Clean Test Data
              </AlertDialogHeader>

              <AlertDialogBody>
                Are you sure you want to clean all test data? This action cannot be undone.
                You will need to reconnect your bank account after cleaning the data.
              </AlertDialogBody>

              <AlertDialogFooter>
                <Button ref={cancelRef} onClick={onClose}>
                  Cancel
                </Button>
                <Button
                  colorScheme='red'
                  onClick={() => cleanupMutation.mutate()}
                  ml={3}
                  isLoading={cleanupMutation.isLoading}
                >
                  Clean Data
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialogOverlay>
        </AlertDialog>
      </VStack>
    </Box>
  );
} 