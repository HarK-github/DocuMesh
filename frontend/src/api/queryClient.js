import { QueryClient } from '@tanstack/react-query';

/**
 * Shared QueryClient with sensible defaults:
 * - 1 retry on network failures
 * - 30 seconds stale time
 * - disabled aggressive refetch on window focus
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30000,
      refetchOnWindowFocus: false,
    },
  },
});
