import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from './client';
import { uploadImage } from './files';
import type { components } from './schema';

export type Recognized = components['schemas']['RecognizeOut'];
export type Scan = components['schemas']['ScanOut'];
export type ScanItem = components['schemas']['ScanItemOut'];
export type StudentAnswer = NonNullable<ScanItem['answer']>;
type RegradeBody = components['schemas']['RegradeIn'];

const LIST_KEY = ['scans'];
const detailKey = (id: number) => ['scan', id];

/** SCAN-02：上传框选后的图，识别出这道题；图片留着，确认后随提问一起发出。 */
export function useRecognize() {
  return useMutation({
    mutationFn: async (image: Blob) => {
      const file = await uploadImage(image);
      const body = { image_file_id: file.id };
      return { file, ...(await unwrap(api.POST('/api/v1/recognize', { body }))) };
    },
  });
}

/** SCAN-03：上传整页照片并发起批改，返回的 job_id 用来查进度。 */
export function useCreateScan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (photo: Blob) => {
      const file = await uploadImage(photo);
      const body = { image_file_id: file.id };
      return unwrap(api.POST('/api/v1/scans', { body }));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

export function useScans() {
  return useQuery({
    queryKey: LIST_KEY,
    queryFn: () => unwrap(api.GET('/api/v1/scans', { params: { query: { page_size: 100 } } })),
  });
}

export function useScan(id: number) {
  return useQuery({
    queryKey: detailKey(id),
    queryFn: () =>
      unwrap(api.GET('/api/v1/scans/{scan_id}', { params: { path: { scan_id: id } } })),
  });
}

/** 批改结果变了（批改完成、重批、确认对错），详情和记录里的汇总都要重新取。 */
export function useRefreshScan() {
  const queryClient = useQueryClient();
  return (id: number) =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: detailKey(id) }),
      queryClient.invalidateQueries({ queryKey: LIST_KEY }),
    ]);
}

export function useRegrade(scanId: number, seq: number) {
  return useMutation({
    mutationFn: (body: RegradeBody) =>
      unwrap(
        api.POST('/api/v1/scans/{scan_id}/items/{seq}/regrade', {
          params: { path: { scan_id: scanId, seq } },
          body,
        }),
      ),
  });
}

export function useConfirm(scanId: number, seq: number) {
  const refresh = useRefreshScan();
  return useMutation({
    mutationFn: (result: 'correct' | 'wrong') =>
      unwrap(
        api.POST('/api/v1/scans/{scan_id}/items/{seq}/confirm', {
          params: { path: { scan_id: scanId, seq } },
          body: { result },
        }),
      ),
    onSuccess: () => refresh(scanId),
  });
}
