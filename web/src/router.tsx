import { createBrowserRouter, Navigate, type RouteObject } from 'react-router';
import { homePath, useMe } from './api/auth';
import type { User } from './api/client';
import { AppShell, type RouteHandle } from './components/AppShell';
import { Button } from './components/Button';
import { Notice } from './components/Notice';
import { getToken } from './lib/session';
import { Login } from './pages/common/Login';
import { Me } from './pages/common/Me';
import { Pending } from './pages/common/Pending';
import { Register } from './pages/common/Register';
import { Settings } from './pages/common/Settings';

/** 登录后才能进的页面：没登录去登录页，身份不对去自己的首页。 */
function RequireRole({ role }: { role: User['role'] }) {
  const me = useMe();
  if (!getToken()) return <Navigate to="/login" replace />;
  if (me.error) {
    return (
      <Notice tone="error">
        {me.error.message}
        <Button size="sm" onClick={() => me.refetch()}>
          重试
        </Button>
      </Notice>
    );
  }
  if (!me.data) return null;
  if (me.data.role !== role) return <Navigate to={homePath(me.data)} replace />;
  return <AppShell user={me.data} />;
}

function GoHome() {
  const me = useMe();
  if (!getToken()) return <Navigate to="/login" replace />;
  return me.data ? <Navigate to={homePath(me.data)} replace /> : null;
}

const page = (
  path: string | undefined,
  title: string,
  element = <Pending />,
  back = false,
): RouteObject => ({
  ...(path ? { path } : { index: true }),
  element,
  handle: { title, back } satisfies RouteHandle,
});

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
  {
    path: '/student',
    element: <RequireRole role="student" />,
    children: [
      page(undefined, '对话'),
      page('today', '今日'),
      page('homework', '全部作业'),
      page('mistakes', '错题本'),
      page('review', '复习'),
      page('profile', '学情画像'),
      page('me', '我的', <Me />),
      page('me/settings', '设置', <Settings />, true),
    ],
  },
  {
    path: '/teacher',
    element: <RequireRole role="teacher" />,
    children: [
      page(undefined, '工作台'),
      page('classes', '班级'),
      page('homework', '作业'),
      page('prep', '备课'),
      page('papers', '组卷'),
      page('analytics', '学情'),
      page('assistant', 'AI 助教'),
      page('me', '我的', <Me />),
      page('me/settings', '设置', <Settings />, true),
    ],
  },
  { path: '*', element: <GoHome /> },
]);
