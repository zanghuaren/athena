import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getToken } from '../lib/session';
import { api, ApiError, notifyUnauthorized, unwrap } from './client';
import type { components } from './schema';

export type Conversation = components['schemas']['ConversationOut'];
export type ConversationDetail = components['schemas']['ConversationDetail'];
export type Message = components['schemas']['MessageOut'];
export type MessageBody = components['schemas']['MessageIn'];
type ConversationPatch = components['schemas']['ConversationPatch'];

export const MAX_TURNS = 50;

const LIST_KEY = ['conversations'];
const detailKey = (id: number) => ['conversation', id];

export function useConversations(q = '', pageSize = 20) {
  return useQuery({
    queryKey: [...LIST_KEY, q, pageSize],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/conversations', {
          params: { query: { q: q || null, page_size: pageSize } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useConversation(id: number | null) {
  return useQuery({
    queryKey: detailKey(id ?? 0),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/conversations/{conversation_id}', {
          params: { path: { conversation_id: id! } },
        }),
      ),
    enabled: id !== null,
  });
}

export function useCreateConversation() {
  return useMutation({
    mutationFn: (body: components['schemas']['ConversationIn']) =>
      unwrap(api.POST('/api/v1/conversations', { body })),
  });
}

export function usePatchConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: ConversationPatch & { id: number }) =>
      unwrap(
        api.PATCH('/api/v1/conversations/{conversation_id}', {
          params: { path: { conversation_id: id } },
          body,
        }),
      ),
    onSuccess: (conversation) => {
      queryClient.setQueryData<ConversationDetail>(detailKey(conversation.id), (old) =>
        old ? { ...old, ...conversation } : old,
      );
      return queryClient.invalidateQueries({ queryKey: LIST_KEY });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(
        api.DELETE('/api/v1/conversations/{conversation_id}', {
          params: { path: { conversation_id: id } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

/** 回答结束后刷新列表（标题、排序会变），withDetail 时连这个会话的详情一起刷新。 */
export function useRefreshConversation() {
  const queryClient = useQueryClient();
  return (id: number, withDetail: boolean) =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: LIST_KEY }),
      withDetail && queryClient.invalidateQueries({ queryKey: detailKey(id) }),
    ]);
}

export type StreamEvent =
  | { event: 'start'; data: { message_id: number; conversation_id: number } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'replace'; data: { text: string } }
  | { event: 'done'; data: { message_id: number; status: 'done' | 'blocked' } }
  | { event: 'error'; data: { code: string; message: string } };

/**
 * 发一条消息并读取 SSE（接口约定 2.1）。`signal` 中止即“停止生成”，服务端会保存已生成的部分。
 * 建立流之前的错误照常抛 ApiError。
 */
export async function streamMessage(
  conversationId: number,
  body: MessageBody,
  signal: AbortSignal,
  onEvent: (e: StreamEvent) => void,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(
      `${import.meta.env.VITE_API_BASE ?? ''}/api/v1/conversations/${conversationId}/messages`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify(body),
        signal,
      },
    );
  } catch {
    if (signal.aborted) return;
    throw new ApiError(0, 'NETWORK', '网络已断开，请检查网络后重试');
  }
  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    const { error } = await response.json();
    throw new ApiError(response.status, error.code, error.message, error.fields);
  }

  const reader = response.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer += value;
      let end;
      while ((end = buffer.indexOf('\n\n')) !== -1) {
        onEvent(parseEvent(buffer.slice(0, end)));
        buffer = buffer.slice(end + 2);
      }
    }
  } catch {
    if (signal.aborted) return;
    throw new ApiError(0, 'NETWORK', '网络中断，回答没有生成完');
  }
}

function parseEvent(block: string): StreamEvent {
  const lines = block.split('\n');
  const event = lines.find((l) => l.startsWith('event: '))!.slice(7);
  const data = JSON.parse(lines.find((l) => l.startsWith('data: '))!.slice(6));
  return { event, data } as StreamEvent;
}

/** S-01 空状态的示例问题：每次进入都由 AI 按知识点重新出，离开后不缓存。 */
export function useSuggestions() {
  return useQuery({
    queryKey: ['conversation-suggestions'],
    queryFn: () => unwrap(api.GET('/api/v1/conversations/suggestions')),
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  });
}
