import { createBrowserRouter, Navigate, type RouteObject } from 'react-router';
import { homePath, useMe } from './api/auth';
import type { User } from './api/client';
import { AppShell, type RouteHandle } from './components/AppShell';
import { Button } from './components/Button';
import { Notice } from './components/Notice';
import { getToken } from './lib/session';
import { Login } from './pages/common/Login';
import { ChatHistory } from './pages/common/ChatHistory';
import { Me } from './pages/common/Me';
import { Pending } from './pages/common/Pending';
import { Register } from './pages/common/Register';
import { Settings } from './pages/common/Settings';
import { Chat } from './pages/student/Chat';
import { MistakeDetail } from './pages/student/MistakeDetail';
import { Mistakes } from './pages/student/Mistakes';
import { Scan } from './pages/student/Scan';
import { ScanCrop } from './pages/student/ScanCrop';
import { ScanHistory } from './pages/student/ScanHistory';
import { ScanProgress } from './pages/student/ScanProgress';
import { ScanResult } from './pages/student/ScanResult';
import { Assistant } from './pages/teacher/Assistant';

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
  extra: Omit<RouteHandle, 'title' | 'back'> = {},
): RouteObject => ({
  ...(path ? { path } : { index: true }),
  element,
  handle: { title, back, ...extra } satisfies RouteHandle,
});

// S-01：手机顶栏左边“历史记录”、右边“新对话”；电脑上这两个入口在侧栏
const studentChat: RouteHandle = {
  title: '对话',
  fill: true,
  links: [
    { to: '/student/history', label: '历史记录', left: true, phoneOnly: true },
    { to: '/student', label: '新对话', phoneOnly: true },
  ],
};
// T-21：原型没有历史入口，ASK-04 要求能回看会话，加在顶栏右边
const teacherChat: RouteHandle = {
  title: 'AI 助教',
  fill: true,
  links: [{ to: '/teacher/assistant/history', label: '历史记录' }],
};

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
  {
    path: '/student',
    element: <RequireRole role="student" />,
    children: [
      page(undefined, '对话', <Chat />, false, studentChat),
      page('c/:conversationId', '对话', <Chat />, false, studentChat),
      page('history', '会话历史', <ChatHistory />, true),
      page('scan', '拍照', <Scan />, true),
      page('scan/crop', '框选题目', <ScanCrop />, true),
      page('scans', '批改记录', <ScanHistory />, true),
      page('scans/:scanId', '批改结果', <ScanResult />, true),
      page('scans/:scanId/progress', '批改中', <ScanProgress />, true),
      page('today', '今日'),
      page('homework', '全部作业'),
      page('mistakes', '错题本', <Mistakes />),
      page('mistakes/:mistakeId', '错题详情', <MistakeDetail />, true),
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
      page('assistant', 'AI 助教', <Assistant />, false, teacherChat),
      page('assistant/c/:conversationId', 'AI 助教', <Assistant />, false, teacherChat),
      page('assistant/history', '会话历史', <ChatHistory />, true),
      page('me', '我的', <Me />),
      page('me/settings', '设置', <Settings />, true),
    ],
  },
  { path: '*', element: <GoHome /> },
]);
