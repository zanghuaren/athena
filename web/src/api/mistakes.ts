import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { api, unwrap } from './client';
import type { components, operations } from './schema';

export type Mistake = components['schemas']['MistakeOut'];
export type MistakeDetail = components['schemas']['MistakeDetail'];
export type MistakeFilters = NonNullable<
  operations['list_mistakes_api_v1_mistakes_get']['parameters']['query']
>;
type MistakePatch = components['schemas']['MistakePatch'];

const LIST_KEY = ['mistakes'];
const detailKey = (id: number) => ['mistake', id];

/** MIS-02：一次取 100 条，错题本按知识点持续复习，不会太多。 */
export function useMistakes(filters: MistakeFilters = {}) {
  return useQuery({
    queryKey: [...LIST_KEY, filters],
    queryFn: () =>
      unwrap(api.GET('/api/v1/mistakes', { params: { query: { ...filters, page_size: 100 } } })),
  });
}

export function useMistake(id: number) {
  return useQuery({
    queryKey: detailKey(id),
    queryFn: () =>
      unwrap(api.GET('/api/v1/mistakes/{mistake_id}', { params: { path: { mistake_id: id } } })),
  });
}

export function useUpdateMistake(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: MistakePatch) =>
      unwrap(
        api.PATCH('/api/v1/mistakes/{mistake_id}', {
          params: { path: { mistake_id: id } },
          body,
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(detailKey(id), data);
      return queryClient.invalidateQueries({ queryKey: LIST_KEY });
    },
  });
}

// 移出错题本可以撤销（原型 S-14）：先从列表里藏起来，几秒后才真正删除。
// 计时放在组件外面，离开页面也会照常删除
const UNDO_MS = 5000;
const removing = new Map<number, ReturnType<typeof setTimeout>>();
const listeners = new Set<() => void>();
let removingIds: number[] = [];

function emit() {
  removingIds = [...removing.keys()];
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => void listeners.delete(listener);
}

/** 正在等待删除、可以撤销的错题。 */
export function useRemovingMistakes() {
  return useSyncExternalStore(subscribe, () => removingIds);
}

export function useRemoveMistake() {
  const queryClient = useQueryClient();
  async function commit(id: number) {
    removing.delete(id);
    try {
      await unwrap(
        api.DELETE('/api/v1/mistakes/{mistake_id}', { params: { path: { mistake_id: id } } }),
      );
      queryClient.removeQueries({ queryKey: detailKey(id) });
    } finally {
      // 删除失败时这道题重新出现在列表里；拍照批改结果里“已在错题本”也要跟着变
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: LIST_KEY }),
        queryClient.invalidateQueries({ queryKey: ['scan'] }),
      ]);
      emit();
    }
  }
  return {
    remove(id: number) {
      removing.set(
        id,
        setTimeout(() => void commit(id), UNDO_MS),
      );
      emit();
    },
    undo(id: number) {
      clearTimeout(removing.get(id));
      removing.delete(id);
      emit();
    },
  };
}

/** SCAN-03：拍照批改里的错题加入错题本，单题和“全部错题”都走这里。 */
export function useAddFromScan(scanId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (seqs: number[]) =>
      unwrap(api.POST('/api/v1/mistakes/batch', { body: { scan_id: scanId, seqs } })),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: LIST_KEY }),
        queryClient.invalidateQueries({ queryKey: ['scan', scanId] }),
      ]),
  });
}

export type QuestionDraft = components['schemas']['QuestionDraft'];
type MistakeIn = components['schemas']['AskMistakeIn'] | components['schemas']['ManualMistakeIn'];

/** ASK-05：从这条讲解里提取题目，给学生确认。 */
export function useExtractQuestion() {
  return useMutation({
    mutationFn: (messageId: number) =>
      unwrap(
        api.POST('/api/v1/messages/{message_id}/extract-question', {
          params: { path: { message_id: messageId } },
        }),
      ),
  });
}

/** 答疑里确认过的题、手动添加的题加入错题本。 */
export function useAddMistake() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: MistakeIn) => unwrap(api.POST('/api/v1/mistakes', { body })),
    onSuccess: (data) => {
      queryClient.setQueryData(detailKey(data.id), data);
      return queryClient.invalidateQueries({ queryKey: LIST_KEY });
    },
  });
}
