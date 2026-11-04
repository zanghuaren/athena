import type { ButtonHTMLAttributes } from 'react';
import styles from './Button.module.css';

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'primary' | 'link';
  size?: 'md' | 'sm';
  block?: boolean;
};

export function Button({
  variant = 'default',
  size = 'md',
  block = false,
  type = 'button',
  className,
  ...rest
}: Props) {
  const classes = [styles.btn, styles[variant], styles[size], block && styles.block, className];
  return <button type={type} className={classes.filter(Boolean).join(' ')} {...rest} />;
}
