import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from './client';
import type { components } from './schema';

export type KnowledgePoint = components['schemas']['KnowledgePointBrief'];
type Subject = components['schemas']['KnowledgeTree']['subject'];

/** KP-01：章节和知识点目录，很少变，取一次就一直用。 */
export function useKnowledgeTree(subject: Subject) {
  return useQuery({
    queryKey: ['knowledge-tree', subject],
    queryFn: () => unwrap(api.GET('/api/v1/knowledge-tree', { params: { query: { subject } } })),
    staleTime: Infinity,
  });
}
