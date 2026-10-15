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
      retry: (failureCount, error) => {
        // Do not retry permanent client errors
        if (error?.status === 404 || error?.status === 422 || error?.status === 409) {
          return false;
        }
        return failureCount < 4;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 8000),
      staleTime: 15000,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
  },
});
