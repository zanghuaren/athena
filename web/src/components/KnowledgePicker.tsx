import { useState } from 'react';
import { useKnowledgeTree, type KnowledgePoint } from '../api/knowledge';
import type { User } from '../api/client';
import { GRADE_LABELS } from '../lib/labels';
import { Notice } from './Notice';
import fieldStyles from './Field.module.css';
import styles from './KnowledgePicker.module.css';

type Subject = NonNullable<User['preferred_subject']>;

/** 从知识点目录里选知识点：先选章节，再点选这一章的知识点；已选的点一下去掉。 */
export function KnowledgePicker({
  subject,
  grade,
  value,
  onChange,
  max,
}: {
  subject: Subject;
  /** 默认打开这个年级的第一章 */
  grade: number | null;
  value: KnowledgePoint[];
  onChange: (value: KnowledgePoint[]) => void;
  max: number;
}) {
  const tree = useKnowledgeTree(subject);
  const [chapterId, setChapterId] = useState<number | null>(null);
  if (tree.error) return <Notice tone="error">{tree.error.message}</Notice>;
  const chapters = tree.data?.chapters ?? [];
  const chapter =
    chapters.find((c) => c.id === chapterId) ??
    chapters.find((c) => c.grade === grade) ??
    chapters[0];
  const chosen = new Set(value.map((k) => k.id));

  function toggle(point: KnowledgePoint) {
    if (chosen.has(point.id)) onChange(value.filter((k) => k.id !== point.id));
    else if (value.length < max) onChange([...value, point]);
  }

  return (
    <fieldset className={fieldStyles.fieldset}>
      <legend className={fieldStyles.label}>
        知识点（选 1～{max} 个，已选 {value.length} 个）
      </legend>
      {value.length > 0 && (
        <div className={styles.chosen}>
          {value.map((k) => (
            <button key={k.id} type="button" onClick={() => toggle(k)} aria-label={`去掉${k.name}`}>
              {k.name} ×
            </button>
          ))}
        </div>
      )}
      <select
        className={fieldStyles.input}
        aria-label="章节"
        value={chapter?.id ?? ''}
        onChange={(e) => setChapterId(Number(e.target.value))}
      >
        {chapters.map((c) => (
          <option key={c.id} value={c.id}>
            {c.grade ? `${GRADE_LABELS[c.grade]} · ` : ''}
            {c.title}
          </option>
        ))}
      </select>
      <div className={fieldStyles.chips}>
        {chapter?.knowledge_points.map((k) => (
          <button
            key={k.id}
            type="button"
            className={fieldStyles.chip}
            aria-pressed={chosen.has(k.id)}
            disabled={!chosen.has(k.id) && value.length >= max}
            onClick={() => toggle(k)}
          >
            {k.name}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
