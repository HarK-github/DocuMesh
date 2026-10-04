import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';

export const queryKeys = {
  document: (id) => ['document', id],
  documentText: (id) => ['documentText', id],
  taxonomy: () => ['taxonomy'],
  annotations: (documentId) => ['annotations', documentId],
  relations: (documentId) => ['relations', documentId],
  graph: (documentId) => ['graph', documentId],
  suggestions: (documentId) => ['suggestions', documentId],
  job: (id) => ['job', id],
};

export function useTaxonomy() {
  return useQuery({
    queryKey: queryKeys.taxonomy(),
    queryFn: () => api.get('/taxonomy'),
  });
}

export function useDocument(documentId) {
  return useQuery({
    queryKey: queryKeys.document(documentId),
    queryFn: () => api.get(`/documents/${documentId}`),
    enabled: Boolean(documentId),
  });
}

export function useDocumentText(documentId) {
  return useQuery({
    queryKey: queryKeys.documentText(documentId),
    queryFn: () => api.get(`/documents/${documentId}/text`),
    enabled: Boolean(documentId),
  });
}

export function useAnnotations(documentId) {
  return useQuery({
    queryKey: queryKeys.annotations(documentId),
    queryFn: () => api.get(`/documents/${documentId}/annotations`),
    enabled: Boolean(documentId),
  });
}

export function useCreateAnnotation(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data) => api.post(`/documents/${documentId}/annotations`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.annotations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
    },
  });
}

export function useUpdateAnnotation(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => api.patch(`/annotations/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.annotations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        queryClient.invalidateQueries({ queryKey: queryKeys.annotations(documentId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
      }
    },
  });
}

export function useDeleteAnnotation(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.delete(`/annotations/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.annotations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.relations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
    },
  });
}

export function useRelations(documentId) {
  return useQuery({
    queryKey: queryKeys.relations(documentId),
    queryFn: () => api.get(`/documents/${documentId}/relations`),
    enabled: Boolean(documentId),
  });
}

export function useCreateRelation(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data) => api.post(`/documents/${documentId}/relations`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.relations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
    },
  });
}

export function useUpdateRelation(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => api.patch(`/relations/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.relations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        queryClient.invalidateQueries({ queryKey: queryKeys.relations(documentId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
      }
    },
  });
}

export function useDeleteRelation(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.delete(`/relations/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.relations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
    },
  });
}

export function useGraph(documentId) {
  return useQuery({
    queryKey: queryKeys.graph(documentId),
    queryFn: () => api.get(`/documents/${documentId}/graph`),
    enabled: Boolean(documentId),
  });
}

/**
 * useJob hook that polls GET /jobs/{id} with refetchInterval
 * and stops when status is done or failed.
 */
export function useJob(jobId) {
  return useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => api.get(`/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 1000;
      if (data.status === 'done' || data.status === 'failed') {
        return false;
      }
      return 1000;
    },
  });
}

/**
 * useChat hook for asking document-scoped questions with graph context.
 */
export function useChat(documentId) {
  return useMutation({
    mutationFn: ({ question, history = [] }) =>
      api.post(`/documents/${documentId}/chat`, { question, history }),
  });
}

export function useSuggestions(documentId) {
  return useQuery({
    queryKey: queryKeys.suggestions(documentId),
    queryFn: () => api.get(`/documents/${documentId}/suggestions`),
    enabled: Boolean(documentId),
  });
}

export function useSuggestHighlights(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ seed_annotation_id, scope }) =>
      api.post(`/documents/${documentId}/suggest-highlights`, { seed_annotation_id, scope }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.suggestions(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
    },
  });
}

export function useAcceptSuggestion(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sugId) => api.post(`/suggestions/${sugId}/accept`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.annotations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.relations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.suggestions(documentId) });
    },
  });
}

export function useRejectSuggestion(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sugId) => api.post(`/suggestions/${sugId}/reject`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.suggestions(documentId) });
    },
  });
}

export function useAcceptAllSuggestions(documentId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sugIds) => {
      const results = [];
      for (const id of sugIds) {
        results.push(await api.post(`/suggestions/${id}/accept`));
      }
      return results;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.annotations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.relations(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(documentId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.suggestions(documentId) });
    },
  });
}
