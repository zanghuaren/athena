import { Icon } from './Icon';
import styles from './Brand.module.css';

export function Brand() {
  return (
    <div className={styles.brand}>
      <Icon name="temple" className={styles.mark} />
      <div>
        <strong>雅典娜</strong>
        <span>ATHENA</span>
      </div>
    </div>
  );
}
