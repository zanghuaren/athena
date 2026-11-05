// S-06 批改结果（SCAN-03）：汇总、原图标注、逐题结果；修改识别结果重批、“？”题自己确认、讲解这道题
import { useEffect, useEffectEvent, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router';
import type { Question } from '../../api/client';
import { fileUrl } from '../../api/files';
import { useJob } from '../../api/jobs';
import {
  useConfirm,
  useRefreshScan,
  useRegrade,
  useScan,
  type ScanItem,
  type StudentAnswer,
} from '../../api/scans';
import { Button } from '../../components/Button';
import type { ScannedQuestion } from '../../components/ChatView';
import { ChoiceChips } from '../../components/ChoiceChips';
import { Markdown } from '../../components/Markdown';
import { Notice } from '../../components/Notice';
import { AnswerText, QuestionView } from '../../components/QuestionView';
import { ERROR_REASON_LABELS } from '../../lib/labels';
import fieldStyles from '../../components/Field.module.css';
import styles from './ScanResult.module.css';

type Mark = { symbol: string; label: string; tone: 'ok' | 'bad' | 'warn' | 'muted' };

export function ScanResult() {
  const id = Number(useParams().scanId);
  const scan = useScan(id);

  if (scan.error) return <Notice tone="error">{scan.error.message}</Notice>;
  if (!scan.data) return null;
  if (scan.data.status !== 'done') return <Navigate to={`/student/scans/${id}/progress`} replace />;

  const { total, correct, unknown, items } = scan.data;
  const graded = total - unknown;
  const scrollTo = (seq: number) =>
    document.getElementById(`scan-item-${seq}`)?.scrollIntoView({ behavior: 'smooth' });

  return (
    <>
      <dl className={styles.stats}>
        <div>
          <dt>做对</dt>
          <dd>{correct}</dd>
        </div>
        <div>
          <dt>做错</dt>
          <dd>{graded - correct}</dd>
        </div>
        <div>
          <dt>待确认</dt>
          <dd>{unknown}</dd>
        </div>
        <div>
          <dt>正确率</dt>
          <dd>{graded ? `${Math.round((correct / graded) * 100)}%` : '—'}</dd>
        </div>
      </dl>
      {scan.data.truncated && <Notice>这页超过 20 道题，只批改了前 20 道，剩下的请分开拍</Notice>}
      <div className={styles.photo}>
        <img src={fileUrl(scan.data.image)} alt="作业原图" />
        {items.map((item) => {
          const mark = markOf(item);
          const { x, y, w } = item.bbox;
          return (
            <button
              key={item.seq}
              type="button"
              className={`${styles.pin} ${styles[mark.tone]}`}
              style={{ left: `${(x + w) * 100}%`, top: `${y * 100}%` }}
              aria-label={`第 ${item.seq} 题：${mark.label}`}
              onClick={() => scrollTo(item.seq)}
            >
              {mark.symbol}
            </button>
          );
        })}
      </div>
      {items.map((item) => (
        <ItemCard key={item.seq} scanId={id} item={item} />
      ))}
    </>
  );
}

function markOf(item: ScanItem): Mark {
  const { attempt } = item;
  if (!attempt) return { symbol: '?', label: '待确认', tone: 'warn' };
  if (attempt.grading_status === 'pending') return { symbol: '…', label: '待判分', tone: 'muted' };
  if (attempt.result === 'correct') return { symbol: '✓', label: '做对', tone: 'ok' };
  if (attempt.result === 'partial') {
    return { symbol: `${attempt.score}/${attempt.max_score}`, label: '部分对', tone: 'warn' };
  }
  return { symbol: '✗', label: '做错', tone: 'bad' };
}

function ItemCard({ scanId, item }: { scanId: number; item: ScanItem }) {
  const navigate = useNavigate();
  const confirm = useConfirm(scanId, item.seq);
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [regradeJob, setRegradeJob] = useState<number | null>(null);
  const { question, attempt } = item;
  const mark = markOf(item);
  const unsure = !attempt;

  function explain() {
    const ask: ScannedQuestion = { content: explainText(item), subject: question.subject };
    navigate('/student', { state: { ask } });
  }

  const kps = question.knowledge_points.map((k) => k.name).join('、');
  const summary = attempt?.grading_detail?.summary;
  return (
    <section id={`scan-item-${item.seq}`} className={styles.item}>
      <div>
        <p className={styles.subject}>
          第 {item.seq} 题{kps && ` · ${kps}`}
        </p>
        {/* 收起时只看题目，展开后带上参考答案和解析 */}
        <QuestionView
          question={
            expanded
              ? question
              : { ...question, answer: null, analysis: null, scoring_points: null }
          }
        />
        <p className={styles.line}>
          <span>你的作答</span>
          {item.answer ? (
            <AnswerOf answer={item.answer} />
          ) : (
            <span className={styles.muted}>没有看清你的作答</span>
          )}
        </p>
        {!expanded && attempt?.result !== 'correct' && question.answer && (
          <p className={styles.line}>
            <span>正确答案</span>
            <span className={styles.ok}>
              <AnswerText answer={question.answer} />
            </span>
          </p>
        )}
        {(attempt?.error_reason || summary) && (
          <p className={styles.reason}>
            {attempt?.error_reason && `错因：${ERROR_REASON_LABELS[attempt.error_reason]}。`}
            {summary}
          </p>
        )}
        {unsure && <p className={styles.reason}>识别或判断没有把握，请核对后确认对错</p>}
        {confirm.error && <Notice tone="error">{confirm.error.message}</Notice>}
        {regradeJob !== null ? (
          <RegradeProgress
            scanId={scanId}
            jobId={regradeJob}
            onFinished={() => setRegradeJob(null)}
          />
        ) : editing ? (
          <RegradeForm
            scanId={scanId}
            item={item}
            onCancel={() => setEditing(false)}
            onStarted={(jobId) => {
              setEditing(false);
              setRegradeJob(jobId);
            }}
          />
        ) : (
          <div className={styles.actions}>
            {attempt?.result !== 'correct' && (
              <Button variant="link" onClick={explain}>
                讲解这道题
              </Button>
            )}
            <Button variant="link" disabled={confirm.isPending} onClick={() => setEditing(true)}>
              修改识别结果
            </Button>
            {unsure && (
              <>
                <Button
                  variant="link"
                  disabled={confirm.isPending}
                  onClick={() => confirm.mutate('correct')}
                >
                  我做对了
                </Button>
                <Button
                  variant="link"
                  disabled={confirm.isPending}
                  onClick={() => confirm.mutate('wrong')}
                >
                  我做错了
                </Button>
              </>
            )}
            <Button variant="link" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
              {expanded ? '收起解析' : '查看解析'}
            </Button>
          </div>
        )}
      </div>
      <div className={`${styles.status} ${styles[mark.tone]}`}>
        <strong>{mark.symbol}</strong>
        {mark.label}
      </div>
    </section>
  );
}

/** 重批是长任务（题目改了要重新解题），完成后重新取整份结果。 */
function RegradeProgress({
  scanId,
  jobId,
  onFinished,
}: {
  scanId: number;
  jobId: number;
  onFinished: () => void;
}) {
  const job = useJob(jobId);
  const refresh = useRefreshScan();
  const status = job.data?.status;
  const finish = useEffectEvent(async () => {
    await refresh(scanId);
    onFinished();
  });
  useEffect(() => {
    if (status === 'succeeded') void finish();
  }, [status]);

  if (status === 'failed') {
    return (
      <>
        <Notice tone="error">{job.data?.error?.message ?? '重新批改没有完成'}</Notice>
        <Button size="sm" onClick={onFinished}>
          知道了
        </Button>
      </>
    );
  }
  return <p className={styles.reason}>正在重新批改…</p>;
}

function RegradeForm({
  scanId,
  item,
  onCancel,
  onStarted,
}: {
  scanId: number;
  item: ScanItem;
  onCancel: () => void;
  onStarted: (jobId: number) => void;
}) {
  const { question } = item;
  const [stem, setStem] = useState(question.content.stem);
  const [answer, setAnswer] = useState<StudentAnswer>(item.answer ?? emptyAnswer(question));
  const regrade = useRegrade(scanId, item.seq);
  const stemId = `regrade-stem-${item.seq}`;

  function submit() {
    const content = stem === question.content.stem ? null : { ...question.content, stem };
    regrade.mutate({ answer, content }, { onSuccess: ({ job_id }) => onStarted(job_id) });
  }

  return (
    <div className={styles.form}>
      <label className={fieldStyles.label} htmlFor={stemId}>
        题目
      </label>
      <textarea
        id={stemId}
        className={`${fieldStyles.input} ${styles.area}`}
        rows={3}
        value={stem}
        onChange={(e) => setStem(e.target.value)}
      />
      <AnswerInput question={question} answer={answer} onChange={setAnswer} />
      {regrade.error && <Notice tone="error">{regrade.error.message}</Notice>}
      <div className={styles.formBar}>
        <Button size="sm" onClick={onCancel}>
          取消
        </Button>
        <Button
          size="sm"
          variant="primary"
          disabled={!stem.trim() || regrade.isPending}
          onClick={submit}
        >
          重新批改
        </Button>
      </div>
    </div>
  );
}

const JUDGE_OPTIONS = [
  { value: 'true', label: '正确' },
  { value: 'false', label: '错误' },
];

type Part = { choice?: string[] | null; judge?: boolean | null; blanks?: string[] | null };

/** 按题型改作答；完形、阅读逐小题改。 */
function AnswerInput({
  question,
  answer,
  onChange,
}: {
  question: Question;
  answer: StudentAnswer;
  onChange: (answer: StudentAnswer) => void;
}) {
  const { content } = question;
  if ('text' in answer) {
    const id = `regrade-answer-${question.id}`;
    return (
      <>
        <label className={fieldStyles.label} htmlFor={id}>
          你的作答
        </label>
        <textarea
          id={id}
          className={`${fieldStyles.input} ${styles.area}`}
          rows={4}
          value={answer.text}
          onChange={(e) => onChange({ text: e.target.value })}
        />
      </>
    );
  }
  if ('sub' in answer) {
    return (
      <>
        {content.sub_questions!.map((sub) => {
          const part = answer.sub.find((p) => p.seq === sub.seq) ?? emptyPart(sub);
          return (
            <PartInput
              key={sub.seq}
              label={`第 ${sub.seq} 小题`}
              type={sub.type}
              options={sub.options?.map((o) => o.key)}
              part={part}
              onChange={(p) =>
                onChange({
                  sub: content.sub_questions!.map((s) =>
                    s.seq === sub.seq
                      ? { seq: s.seq, ...p }
                      : (answer.sub.find((x) => x.seq === s.seq) ?? {
                          seq: s.seq,
                          ...emptyPart(s),
                        }),
                  ),
                })
              }
            />
          );
        })}
      </>
    );
  }
  return (
    <PartInput
      label="你的作答"
      type={question.type}
      options={content.options?.map((o) => o.key)}
      part={answer}
      onChange={(p) => onChange(p as StudentAnswer)}
    />
  );
}

function PartInput({
  label,
  type,
  options,
  part,
  onChange,
}: {
  label: string;
  type: string;
  options?: string[];
  part: Part;
  onChange: (part: Part) => void;
}) {
  if (part.choice) {
    return (
      <ChoiceChips
        label={label}
        multiple={type === 'multiple'}
        options={options!.map((k) => ({ value: k, label: k }))}
        value={part.choice}
        onChange={(choice) => onChange({ choice })}
      />
    );
  }
  if (part.blanks) {
    const blanks = part.blanks;
    return (
      <fieldset className={fieldStyles.fieldset}>
        <legend className={fieldStyles.label}>{label}</legend>
        {blanks.map((b, i) => (
          <input
            key={i}
            className={fieldStyles.input}
            aria-label={`第 ${i + 1} 空`}
            placeholder={blanks.length > 1 ? `第 ${i + 1} 空` : undefined}
            value={b}
            onChange={(e) =>
              onChange({ blanks: blanks.map((x, j) => (j === i ? e.target.value : x)) })
            }
          />
        ))}
      </fieldset>
    );
  }
  return (
    <ChoiceChips
      label={label}
      options={JUDGE_OPTIONS}
      value={part.judge == null ? [] : [String(part.judge)]}
      onChange={([v]) => onChange({ judge: v === 'true' })}
    />
  );
}

function emptyPart(q: { type: string; blank_count?: number | null }): Part {
  if (q.type === 'single' || q.type === 'multiple') return { choice: [] };
  if (q.type === 'blank') return { blanks: Array<string>(q.blank_count!).fill('') };
  return { judge: null };
}

/** 识别不到作答时，按题型给一份空的作答让学生填。 */
function emptyAnswer(question: Question): StudentAnswer {
  const { content } = question;
  if (question.type === 'solution' || question.type === 'essay') return { text: '' };
  if (content.sub_questions) {
    return { sub: content.sub_questions.map((s) => ({ seq: s.seq, ...emptyPart(s) })) };
  }
  return emptyPart({ type: question.type, blank_count: content.blank_count }) as StudentAnswer;
}

function AnswerOf({ answer }: { answer: StudentAnswer }) {
  const text = answerText(answer);
  return 'text' in answer ? <Markdown text={text} /> : <Markdown inline text={text} />;
}

function answerText(answer: StudentAnswer): string {
  if ('text' in answer) return answer.text || '没有作答';
  if ('sub' in answer) return answer.sub.map((p) => `${p.seq}. ${partText(p)}`).join('；');
  return partText(answer);
}

function partText(part: Part): string {
  if (part.choice) return part.choice.join('、') || '没有作答';
  if (part.blanks) {
    const blanks = part.blanks.map((b) => b || '（空）');
    return blanks.length > 1 ? blanks.map((b, i) => `(${i + 1}) ${b}`).join('；') : blanks[0];
  }
  return part.judge == null ? '没有作答' : part.judge ? '正确' : '错误';
}

const MAX_ASK_LENGTH = 1000;

/** “讲解这道题”发给答疑的文字：题目和学生的作答，太长时截掉题目的末尾。 */
function explainText(item: ScanItem): string {
  const { content } = item.question;
  const parts = [`帮我讲讲这道题：\n\n${content.stem}`];
  if (content.material) parts.push(content.material);
  if (content.options) parts.push(content.options.map((o) => `${o.key}. ${o.text}`).join('\n'));
  for (const sub of content.sub_questions ?? []) {
    const options = sub.options?.map((o) => `${o.key}. ${o.text}`).join('　') ?? '';
    parts.push(`${sub.seq}. ${sub.stem} ${options}`.trim());
  }
  const mine = `我的作答：${item.answer ? answerText(item.answer) : '（没有识别出来）'}`;
  return `${parts.join('\n\n').slice(0, MAX_ASK_LENGTH - mine.length - 2)}\n\n${mine}`.slice(
    0,
    MAX_ASK_LENGTH,
  );
}
