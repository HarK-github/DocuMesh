import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

export function useHealth() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health'),
    refetchInterval: (q) => (q.state.error ? 2500 : 10000),
    retry: 1,
  });

  return {
    ...query,
    isOnline: !query.isError,
    isReconnecting: query.isFetching && query.isError,
    reconnect: () => {
      queryClient.invalidateQueries();
      return query.refetch();
    },
  };
}

