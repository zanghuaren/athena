import type { ReactNode } from 'react';
import styles from './AuthLayout.module.css';

/** 登录、注册这类没有导航的页面（原型里的 bare 页面）。 */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className={styles.page}>
      <div className={styles.column}>{children}</div>
    </main>
  );
}
