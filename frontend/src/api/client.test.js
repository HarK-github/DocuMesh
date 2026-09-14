import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api, ApiError } from './client';

describe('API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('performs successful GET requests and parses JSON', async () => {
    const mockData = { status: 'ok' };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: {
        get: (h) => (h === 'content-type' ? 'application/json' : null),
      },
      json: async () => mockData,
    });

    const result = await api.get('/health');
    expect(result).toEqual({ status: 'ok' });
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/health', expect.objectContaining({
      method: 'GET',
    }));
  });

  it('throws ApiError with status and message on HTTP errors', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      headers: {
        get: (h) => (h === 'content-type' ? 'application/json' : null),
      },
      json: async () => ({ detail: 'Document not found' }),
    });

    await expect(api.get('/documents/999')).rejects.toThrow(ApiError);
    try {
      await api.get('/documents/999');
    } catch (err) {
      expect(err.status).toBe(404);
      expect(err.message).toBe('Document not found');
    }
  });
});
