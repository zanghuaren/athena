import type { ReactNode } from 'react';
import styles from './Notice.module.css';

export function Notice({
  tone = 'gray',
  children,
}: {
  tone?: 'gray' | 'error';
  children: ReactNode;
}) {
  return (
    <div className={`${styles.box} ${styles[tone]}`} role={tone === 'error' ? 'alert' : undefined}>
      {children}
    </div>
  );
}
