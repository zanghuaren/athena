import { useEffect, useEffectEvent, useRef, useState } from 'react';
import { Link } from 'react-router';
import { useAddMistake, useExtractQuestion, type QuestionDraft } from '../api/mistakes';
import { SUBJECT_LABELS } from '../lib/labels';
import { Button } from './Button';
import { Markdown } from './Markdown';
import { Notice } from './Notice';
import { AnswerText } from './QuestionView';
import fieldStyles from './Field.module.css';
import styles from './AddMistakeDialog.module.css';

/**
 * 答疑“加入错题本”的弹窗（原型 S-01 加入错题本弹窗，ASK-05）：
 * AI 从讲解里提取题干、正确答案、知识点，学生可以改题干，确认后入本。
 */
export function AddMistakeDialog({
  messageId,
  onClose,
}: {
  messageId: number;
  onClose: (added: number | null) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const extract = useExtractQuestion();
  const add = useAddMistake();
  const [stem, setStem] = useState('');

  // 打开时提取一次；开发模式下 effect 会执行两遍，用 ref 挡住第二次调用模型
  const started = useRef(false);
  const start = useEffectEvent(() => {
    dialogRef.current?.showModal();
    if (started.current) return;
    started.current = true;
    extract.mutate(messageId, { onSuccess: ({ question }) => setStem(question.content.stem) });
  });
  useEffect(() => start(), []);

  function confirm(draft: QuestionDraft) {
    const { knowledge_points, ...rest } = draft;
    const question = {
      ...rest,
      content: { ...draft.content, stem: stem.trim() },
      knowledge_point_ids: knowledge_points.map((k) => k.id),
    };
    add.mutate(
      { source: 'ask', message_id: messageId, question },
      { onSuccess: (m) => onClose(m.id) },
    );
  }

  const data = extract.data;
  return (
    <dialog ref={dialogRef} className={styles.dialog} onClose={() => onClose(null)}>
      <h3>加入错题本</h3>
      {extract.isPending && <p className={styles.muted}>正在从讲解里整理题目…</p>}
      {extract.error && <Notice tone="error">{extract.error.message}</Notice>}
      {data?.mistake_id != null && (
        <Notice>
          这道题已经在错题本里了。 <Link to={`/student/mistakes/${data.mistake_id}`}>查看</Link>
        </Notice>
      )}
      {data && data.mistake_id == null && (
        <>
          <label className={fieldStyles.label} htmlFor="mistake-stem">
            题目（可以修改）
          </label>
          <textarea
            id="mistake-stem"
            className={`${fieldStyles.input} ${styles.area}`}
            rows={4}
            maxLength={1000}
            value={stem}
            onChange={(e) => setStem(e.target.value)}
          />
          {data.question.content.options?.map((o) => (
            <p key={o.key} className={styles.option}>
              {o.key}. <Markdown inline text={o.text} />
            </p>
          ))}
          <p className={fieldStyles.label}>正确答案</p>
          <div className={styles.answer}>
            <AnswerText answer={data.question.answer} />
          </div>
          <p className={styles.muted}>
            {SUBJECT_LABELS[data.question.subject]} ·{' '}
            {data.question.knowledge_points.map((k) => k.name).join('、')}
          </p>
        </>
      )}
      {add.error && <Notice tone="error">{add.error.message}</Notice>}
      <div className={styles.buttons}>
        <Button onClick={() => dialogRef.current?.close()}>
          {data?.mistake_id != null ? '关闭' : '取消'}
        </Button>
        {data && data.mistake_id == null && (
          <Button
            variant="primary"
            disabled={!stem.trim() || add.isPending}
            onClick={() => confirm(data.question)}
          >
            {add.isPending ? '正在加入…' : '确认加入'}
          </Button>
        )}
      </div>
      <p className={styles.muted}>新加入的错题明天开始复习；已有错题会保留复习进度。</p>
    </dialog>
  );
}
