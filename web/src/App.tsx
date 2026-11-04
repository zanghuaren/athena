import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router';
import { ApiError, setUnauthorizedHandler } from './api/client';
import { clearToken } from './lib/session';
import { router } from './router';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 业务错误（4xx）重试也没用，只重试断网、超时和 5xx
      retry: (count, error) =>
        count < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
    },
  },
});

// 登录过期：清掉本机登录状态，登录后回到原页面（02 第 16 节）
setUnauthorizedHandler(async () => {
  await clearToken();
  queryClient.clear();
  const from = location.pathname + location.search;
  await router.navigate(`/login?from=${encodeURIComponent(from)}`, { replace: true });
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
