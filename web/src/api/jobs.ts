import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from './client';
import type { components } from './schema';

export type Job = components['schemas']['JobOut'];

const POLL_MS = 2000;

/** 长任务进度（接口约定 2.2）：每 2 秒查一次，成功或失败后停止。 */
export function useJob(id: number | null) {
  return useQuery({
    queryKey: ['job', id],
    queryFn: () => unwrap(api.GET('/api/v1/jobs/{job_id}', { params: { path: { job_id: id! } } })),
    enabled: id !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'succeeded' || status === 'failed' ? false : POLL_MS;
    },
  });
}
