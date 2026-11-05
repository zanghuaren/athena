// S-14 错题详情（MIS-03）：题目、我的作答、答案解析、错因、笔记；讲解、标记已掌握、移出错题本
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import {
  useMistake,
  useRemoveMistake,
  useUpdateMistake,
  type MistakeDetail as Detail,
} from '../../api/mistakes';
import { Button } from '../../components/Button';
import type { ScannedQuestion } from '../../components/ChatView';
import { Markdown } from '../../components/Markdown';
import { Notice } from '../../components/Notice';
import { QuestionView, StudentAnswerText } from '../../components/QuestionView';
import { answerText, explainText } from '../../lib/answers';
import {
  ERROR_REASON_LABELS,
  MISTAKE_SOURCE_LABELS,
  SUBJECT_LABELS,
  mistakeStatusText,
} from '../../lib/labels';
import { reviewDueText } from '../../lib/time';
import fieldStyles from '../../components/Field.module.css';
import styles from './MistakeDetail.module.css';

const NOTE_MAX = 500;

export function MistakeDetail() {
  const id = Number(useParams().mistakeId);
  const mistake = useMistake(id);
  if (mistake.error) return <Notice tone="error">{mistake.error.message}</Notice>;
  if (!mistake.data) return null;
  return <Content mistake={mistake.data} />;
}

function Content({ mistake }: { mistake: Detail }) {
  const navigate = useNavigate();
  const update = useUpdateMistake(mistake.id);
  const { remove } = useRemoveMistake();
  const [note, setNote] = useState(mistake.note ?? '');
  const { question, attempt } = mistake;
  const kps = question.knowledge_points.map((k) => k.name).join('、');
  const mine = mistake.answer ? answerText(mistake.answer) : (mistake.my_answer ?? undefined);
  // 没有作答时批改总评也是“没有作答”，不重复显示
  const summary = attempt?.grading_detail?.summary;
  const showSummary = summary && summary !== mine;

  function explain() {
    const ask: ScannedQuestion = {
      content: explainText(question, mine),
      subject: question.subject,
    };
    navigate('/student', { state: { ask } });
  }

  function removeFromBook() {
    remove(mistake.id);
    navigate('/student/mistakes', { replace: true });
  }

  const review = [mistakeStatusText(mistake)];
  if (mistake.next_review_on) review.push(reviewDueText(mistake.next_review_on));
  return (
    <>
      <p className={styles.subject}>
        {[
          SUBJECT_LABELS[question.subject],
          kps,
          `来源：${MISTAKE_SOURCE_LABELS[mistake.source]}`,
          `错过 ${mistake.wrong_count} 次`,
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>
      <QuestionView question={question}>
        <section className={styles.mine}>
          <h4>我的作答</h4>
          {mistake.answer ? (
            <StudentAnswerText answer={mistake.answer} />
          ) : mistake.my_answer ? (
            <Markdown text={mistake.my_answer} />
          ) : (
            <p className={styles.muted}>没有记录</p>
          )}
          {attempt?.result === 'partial' && (
            <p className={styles.muted}>
              得分 {attempt.score} / {attempt.max_score}
            </p>
          )}
          {showSummary && <p className={styles.muted}>{summary}</p>}
        </section>
      </QuestionView>
      {mistake.tip && (
        <Notice>
          <Markdown inline text={mistake.tip} />
        </Notice>
      )}

      <label className={fieldStyles.label} htmlFor="mistake-reason">
        错因
      </label>
      <select
        id="mistake-reason"
        className={fieldStyles.input}
        value={mistake.error_reason ?? ''}
        disabled={update.isPending}
        onChange={(e) =>
          update.mutate({ error_reason: (e.target.value || null) as Detail['error_reason'] })
        }
      >
        <option value="">还没有分析</option>
        {Object.entries(ERROR_REASON_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>

      <label className={fieldStyles.label} htmlFor="mistake-note">
        笔记
      </label>
      <textarea
        id="mistake-note"
        className={`${fieldStyles.input} ${styles.note}`}
        rows={3}
        maxLength={NOTE_MAX}
        placeholder="记录这道题容易错在哪里"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <div className={styles.noteBar}>
        <span>
          {note.length} / {NOTE_MAX}
        </span>
        <Button
          size="sm"
          disabled={update.isPending || note === (mistake.note ?? '')}
          onClick={() => update.mutate({ note })}
        >
          保存笔记
        </Button>
      </div>
      {update.error && <Notice tone="error">{update.error.message}</Notice>}

      <p className={styles.review}>复习：{review.join(' · ')}</p>
      <Button variant="primary" block onClick={explain}>
        讲解这道题
      </Button>
      <div className={styles.actions}>
        <Button
          variant="link"
          disabled={update.isPending}
          onClick={() =>
            update.mutate({ status: mistake.status === 'mastered' ? 'pending' : 'mastered' })
          }
        >
          {mistake.status === 'mastered' ? '恢复复习' : '标记已掌握'}
        </Button>
        <Button variant="link" className={styles.danger} onClick={removeFromBook}>
          移出错题本
        </Button>
      </div>
    </>
  );
}
