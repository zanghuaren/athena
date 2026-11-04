import createClient from 'openapi-fetch';
import { getToken } from '../lib/session';
import type { components, paths } from './schema';

export type User = components['schemas']['UserOut'];
export type Question = components['schemas']['QuestionOut'];

const REQUEST_TIMEOUT_MS = 15_000;

/** 接口约定 1.4 的错误体；断网和超时也转成同样的结构，页面只处理这一种错误。 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

type ErrorBody = { error: { code: string; message: string; fields?: Record<string, string> } };

let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE ?? '',
  fetch: (request) =>
    fetch(request, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) }).catch((e: unknown) => {
      if (e instanceof DOMException && e.name === 'TimeoutError') {
        throw new ApiError(0, 'TIMEOUT', '请求超时，请重试');
      }
      throw new ApiError(0, 'NETWORK', '网络已断开，请检查网络后重试');
    }),
});

api.use({
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401 && getToken()) onUnauthorized();
    return response;
  },
});

/** 把 openapi-fetch 的 {data, error} 变成“成功返回数据、失败抛 ApiError”，方便配合 TanStack Query。 */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined) {
    const body = (error as ErrorBody).error;
    throw new ApiError(response.status, body.code, body.message, body.fields);
  }
  return data as T;
}
