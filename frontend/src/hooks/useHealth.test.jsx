import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockUseQuery = vi.fn();
const mockUseQueryClient = vi.fn();

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args) => mockUseQuery(...args),
  useQueryClient: (...args) => mockUseQueryClient(...args),
}));

import { useHealth } from './useHealth';

describe('useHealth hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns isOnline: true and isReconnecting: false when query has no error', () => {
    mockUseQueryClient.mockReturnValue({ invalidateQueries: vi.fn() });
    mockUseQuery.mockReturnValue({
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    });

    const result = useHealth();
    expect(result.isOnline).toBe(true);
    expect(result.isReconnecting).toBe(false);
  });

  it('returns isOnline: false and isReconnecting: true when query has error and is fetching', () => {
    const mockRefetch = vi.fn();
    const mockInvalidate = vi.fn();
    mockUseQueryClient.mockReturnValue({ invalidateQueries: mockInvalidate });
    mockUseQuery.mockReturnValue({
      isError: true,
      isFetching: true,
      refetch: mockRefetch,
    });

    const result = useHealth();
    expect(result.isOnline).toBe(false);
    expect(result.isReconnecting).toBe(true);

    result.reconnect();
    expect(mockInvalidate).toHaveBeenCalled();
    expect(mockRefetch).toHaveBeenCalled();
  });
});
