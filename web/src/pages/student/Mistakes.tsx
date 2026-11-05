// S-13 错题本（MIS-02）：学科、知识点、来源、状态筛选和排序；卡片显示复习状态，不显示掌握度（03 Q1）
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import {
  useMistakes,
  useRemoveMistake,
  useRemovingMistakes,
  type Mistake,
  type MistakeFilters,
} from '../../api/mistakes';
import { Button } from '../../components/Button';
import type { ScannedQuestion } from '../../components/ChatView';
import { Markdown } from '../../components/Markdown';
import { Notice } from '../../components/Notice';
import { PageHeading } from '../../components/PageHeading';
import { explainText } from '../../lib/answers';
import { MISTAKE_SOURCE_LABELS, SUBJECT_LABELS, mistakeStatusText } from '../../lib/labels';
import { reviewDueText } from '../../lib/time';
import styles from './Mistakes.module.css';

type Subject = Mistake['question']['subject'];

const SUBJECTS: [Subject | undefined, string][] = [
  [undefined, '全部'],
  ...(Object.entries(SUBJECT_LABELS) as [Subject, string][]),
];
const STATUS_LABELS = { pending: '待复习', reviewing: '复习中', mastered: '已掌握' };
const SORT_LABELS = { recent: '最近加入', wrong_count: '错误次数' };

export function Mistakes() {
  const [filters, setFilters] = useState<MistakeFilters>({});
  // 知识点选项取自全部错题，筛选后选项也不变
  const all = useMistakes();
  const list = useMistakes(filters);
  const removing = useRemovingMistakes();
  const { undo } = useRemoveMistake();
  const navigate = useNavigate();
  const set = (patch: MistakeFilters) => setFilters({ ...filters, ...patch });

  if (all.error) return <Notice tone="error">{all.error.message}</Notice>;
  if (!all.data) return null;
  const total = all.data.items.filter((m) => !removing.includes(m.id)).length;
  const undoBar = removing.length > 0 && (
    <div className={styles.undo} role="status">
      已移出错题本
      <Button variant="link" onClick={() => removing.forEach(undo)}>
        撤销
      </Button>
    </div>
  );
  if (total === 0) {
    return (
      <>
        <PageHeading title="我的错题" />
        <p className={styles.empty}>错题本还是空的。拍照批改一份作业，做错的题可以一键加入。</p>
        <Button variant="primary" block onClick={() => navigate('/student/scan?mode=grade')}>
          拍照批改
        </Button>
        {undoBar}
      </>
    );
  }

  const points = new Map<number, string>();
  for (const m of all.data.items) {
    if (filters.subject && m.question.subject !== filters.subject) continue;
    for (const k of m.question.knowledge_points) points.set(k.id, k.name);
  }
  const items = list.data?.items.filter((m) => !removing.includes(m.id));

  return (
    <>
      <PageHeading title="我的错题" description={`${total} 道错题，按知识点持续复习`} />
      <div className={styles.subjects} aria-label="按学科筛选">
        {SUBJECTS.map(([value, label]) => (
          <button
            key={label}
            type="button"
            aria-pressed={filters.subject === value}
            onClick={() => set({ subject: value, knowledge_point_id: undefined })}
          >
            {label}
          </button>
        ))}
      </div>
      <div className={styles.filters}>
        <Select
          label="知识点"
          value={filters.knowledge_point_id}
          options={[...points].map(([id, name]) => [id, name])}
          onChange={(v) => set({ knowledge_point_id: v === undefined ? undefined : Number(v) })}
        />
        <Select
          label="来源"
          value={filters.source}
          options={Object.entries(MISTAKE_SOURCE_LABELS)}
          onChange={(v) => set({ source: v as MistakeFilters['source'] })}
        />
        <Select
          label="状态"
          value={filters.status}
          options={Object.entries(STATUS_LABELS)}
          onChange={(v) => set({ status: v as MistakeFilters['status'] })}
        />
        <Select
          label="排序"
          value={filters.sort ?? 'recent'}
          options={Object.entries(SORT_LABELS)}
          onChange={(v) => set({ sort: v as MistakeFilters['sort'] })}
          required
        />
      </div>
      {list.error && <Notice tone="error">{list.error.message}</Notice>}
      {items?.length === 0 && (
        <p className={styles.empty}>没有符合筛选条件的错题，可以更换筛选条件。</p>
      )}
      {items?.map((m) => (
        <MistakeCard key={m.id} mistake={m} />
      ))}
      {undoBar}
    </>
  );
}

function Select<T extends string | number>({
  label,
  value,
  options,
  onChange,
  required = false,
}: {
  label: string;
  value: T | null | undefined;
  options: [T | string, string][];
  onChange: (value: string | undefined) => void;
  required?: boolean;
}) {
  return (
    <label className={styles.select}>
      {label}
      <select value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)}>
        {!required && <option value="">全部{label}</option>}
        {options.map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

function MistakeCard({ mistake }: { mistake: Mistake }) {
  const navigate = useNavigate();
  const { question } = mistake;
  const kps = question.knowledge_points.map((k) => k.name).join('、');
  const to = `/student/mistakes/${mistake.id}`;

  function explain() {
    const ask: ScannedQuestion = { content: explainText(question), subject: question.subject };
    navigate('/student', { state: { ask } });
  }

  const status = [mistakeStatusText(mistake)];
  if (mistake.next_review_on) status.push(reviewDueText(mistake.next_review_on));
  status.push(`错过 ${mistake.wrong_count} 次`);
  return (
    <article className={styles.card}>
      <p className={styles.subject}>
        {[SUBJECT_LABELS[question.subject], kps, MISTAKE_SOURCE_LABELS[mistake.source]]
          .filter(Boolean)
          .join(' · ')}
      </p>
      <Link to={to} className={styles.stem}>
        <Markdown text={question.content.stem} />
      </Link>
      {mistake.tip && <Markdown inline text={mistake.tip} className={styles.tip} />}
      <div className={styles.actions}>
        <Button variant="link" onClick={explain}>
          讲解
        </Button>
      </div>
      <p className={styles.status}>{status.join(' · ')}</p>
    </article>
  );
}
