import styles from './PageHeading.module.css';

/** 原型的 section-top：宋体标题 + 一句说明。 */
export function PageHeading({ title, description }: { title: string; description?: string }) {
  return (
    <div className={styles.heading}>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
    </div>
  );
}
