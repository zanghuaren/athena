// C-04 我的（ME）。班级、学情等入口随对应模块开发时补上
import { Link } from 'react-router';
import { useCurrentUser } from '../../components/AppShell';
import { Icon } from '../../components/Icon';
import { PageHeading } from '../../components/PageHeading';
import { userSummary } from '../../lib/labels';
import styles from './Me.module.css';

export function Me() {
  const user = useCurrentUser();
  return (
    <>
      <PageHeading title={user.role === 'student' ? '我的学习空间' : '我的'} />
      <div className={styles.hero}>
        <span className={styles.avatar}>{user.display_name.slice(0, 1)}</span>
        <div>
          <b>{user.display_name}</b>
          <span>{userSummary(user)}</span>
        </div>
      </div>
      <div className={styles.group}>其他</div>
      <Link to="settings" className={styles.link}>
        <span>
          <span className={styles.title}>设置</span>
          <span className={styles.desc}>
            {user.role === 'student' ? '主题、讲解方式、修改密码' : '主题、修改密码'}
          </span>
        </span>
        <Icon name="right" className={styles.chevron} />
      </Link>
    </>
  );
}
