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

  it('posts chat queries with question and history, returning answer and citations', async () => {
    const mockChatResponse = {
      answer: 'According to the text [s1], Turing proposed the test.',
      citations: [
        { type: 'sentence', id: 1, start: 0, end: 19 },
        { type: 'annotation', id: 2, start: 20, end: 68 },
      ],
      used_context: true,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: {
        get: (h) => (h === 'content-type' ? 'application/json' : null),
      },
      json: async () => mockChatResponse,
    });

    const requestBody = {
      question: 'What test did Turing propose?',
      history: [{ role: 'user', content: 'Hello' }],
    };

    const res = await api.post('/documents/1/chat', requestBody);

    expect(res).toEqual(mockChatResponse);
    expect(res.used_context).toBe(true);
    expect(res.citations).toHaveLength(2);
    expect(res.citations[0].type).toBe('sentence');
    expect(res.citations[1].type).toBe('annotation');

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/documents/1/chat',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(requestBody),
      })
    );
  });
});
