import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useMatches,
  useNavigate,
  useOutletContext,
} from 'react-router';
import type { User } from '../api/client';
import { useConversations } from '../api/conversations';
import { userSummary } from '../lib/labels';
import { Brand } from './Brand';
import { Button } from './Button';
import { Icon, type IconName } from './Icon';
import styles from './AppShell.module.css';

type NavItem = { to: string; label: string; icon: IconName };

// 导航项与原型 NAV 一致：宽屏用侧栏（web），窄屏用底部 Tab（phone）
const NAV: Record<User['role'], { web: NavItem[]; phone: NavItem[]; motto: [string, string] }> = {
  student: {
    web: [
      { to: '/student', label: '对话', icon: 'chat' },
      { to: '/student/today', label: '今日任务', icon: 'plan' },
      { to: '/student/homework', label: '作业', icon: 'checklist' },
      { to: '/student/mistakes', label: '错题本', icon: 'book' },
      { to: '/student/review', label: '复习', icon: 'cards' },
      { to: '/student/profile', label: '学情', icon: 'chart' },
      { to: '/student/me', label: '我的', icon: 'user' },
    ],
    phone: [
      { to: '/student', label: '对话', icon: 'chat' },
      { to: '/student/today', label: '今日', icon: 'plan' },
      { to: '/student/mistakes', label: '错题本', icon: 'book' },
      { to: '/student/review', label: '复习', icon: 'cards' },
      { to: '/student/me', label: '我的', icon: 'user' },
    ],
    motto: ['每一次追问，', '都向智慧更近一步。'],
  },
  teacher: {
    web: [
      { to: '/teacher', label: '工作台', icon: 'temple' },
      { to: '/teacher/classes', label: '班级', icon: 'users' },
      { to: '/teacher/homework', label: '作业', icon: 'checklist' },
      { to: '/teacher/prep', label: '备课', icon: 'pen' },
      { to: '/teacher/papers', label: '组卷', icon: 'document' },
      { to: '/teacher/analytics', label: '学情', icon: 'chart' },
      { to: '/teacher/assistant', label: 'AI 助教', icon: 'chat' },
      { to: '/teacher/me', label: '我的', icon: 'user' },
    ],
    phone: [
      { to: '/teacher', label: '工作台', icon: 'temple' },
      { to: '/teacher/homework', label: '作业', icon: 'checklist' },
      { to: '/teacher/analytics', label: '学情', icon: 'chart' },
      { to: '/teacher/me', label: '我的', icon: 'user' },
    ],
    motto: ['教学相长，', '学然后知不足。'],
  },
};

type TopLink = { to: string; label: string; phoneOnly?: boolean; left?: boolean };

/**
 * back：二级页面，顶栏显示“返回”（原型里的 back 页面）。
 * links：顶栏链接（原型的 topL / topR），left 的放在标题左边，phoneOnly 的只在手机上显示。
 * fill：页面自己管理滚动和底部输入框（对话页），外框不加内边距、不滚动。
 */
export type RouteHandle = { title: string; back?: boolean; links?: TopLink[]; fill?: boolean };

export function AppShell({ user }: { user: User }) {
  const nav = NAV[user.role];
  const navigate = useNavigate();
  const handle = useMatches().at(-1)?.handle as RouteHandle | undefined;
  const { pathname } = useLocation();
  // 首页（/student、/teacher）是其他页面的前缀，只在完全匹配时高亮；学生首页是对话，会话和历史也算
  const home = `/${user.role}`;
  const homeActive =
    pathname === home || (user.role === 'student' && /^\/student\/(c\/|history)/.test(pathname));
  const navClass =
    (to: string) =>
    ({ isActive }: { isActive: boolean }) =>
      (to === home ? homeActive : isActive) ? styles.on : undefined;

  return (
    <div className={styles.shell}>
      <aside className={styles.side}>
        <div className={styles.brand}>
          <Brand />
        </div>
        {user.role === 'student' && (
          <NavLink to={home} end className={styles.newChat}>
            <Icon name="plus" />
            开启新对话
          </NavLink>
        )}
        <nav>
          {nav.web.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === home} className={navClass(n.to)}>
              <Icon name={n.icon} />
              {n.label}
            </NavLink>
          ))}
        </nav>
        {user.role === 'student' && <RecentConversations />}
        <div className={styles.motto}>
          <Icon name="olive" className={styles.olive} />
          <p>
            {nav.motto[0]}
            <br />
            {nav.motto[1]}
          </p>
        </div>
        <NavLink to={`${home}/me`} className={styles.foot}>
          <span className={styles.avatar}>{user.display_name.slice(0, 1)}</span>
          <span>
            {user.display_name}
            <small>{userSummary(user)}</small>
          </span>
        </NavLink>
      </aside>
      <div className={styles.main}>
        <header className={styles.topbar}>
          {handle?.back && (
            <Button variant="link" onClick={() => navigate(-1)}>
              ‹ 返回
            </Button>
          )}
          {handle?.links?.filter((l) => l.left).map(topLink)}
          <h1>{handle?.title}</h1>
          {handle?.links?.filter((l) => !l.left).map(topLink)}
        </header>
        <main className={handle?.fill ? styles.fill : styles.content}>
          <Outlet context={user} />
        </main>
        <nav className={styles.tabs}>
          {nav.phone.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === home} className={navClass(n.to)}>
              <Icon name={n.icon} />
              {n.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}

function topLink(l: TopLink) {
  return (
    <Link key={l.to} to={l.to} className={l.phoneOnly ? styles.phoneOnly : undefined}>
      {l.label}
    </Link>
  );
}

function RecentConversations() {
  const recent = useConversations('', 3);
  if (!recent.data?.items.length) return null;
  return (
    <div className={styles.recent}>
      <p>最近对话</p>
      {recent.data.items.map((c) => (
        <NavLink
          key={c.id}
          to={`/student/c/${c.id}`}
          className={({ isActive }) => (isActive ? styles.on : undefined)}
        >
          {c.title}
        </NavLink>
      ))}
      <Link to="/student/history">全部对话</Link>
    </div>
  );
}

/** 外框里的页面取当前用户，外框已经保证用户存在。 */
export function useCurrentUser(): User {
  return useOutletContext<User>();
}
