import type { ReactNode } from 'react';
import type { components } from '../api/schema';
import type { Question } from '../api/client';
import type { StudentAnswer } from '../api/scans';
import { answerText } from '../lib/answers';
import { QUESTION_TYPE_LABELS } from '../lib/labels';
import { Markdown } from './Markdown';
import styles from './QuestionView.module.css';

type Option = components['schemas']['Option'];
type Answer = NonNullable<Question['answer']>;
type SubAnswerItem = components['schemas']['SubAnswerItem'];

/**
 * 只读展示一道题（KP-03）。答案、解析、评分要点由接口决定是否返回，返回了才显示。
 * 作答控件由练习、作业等页面自己放在下面；children 放在题目和参考答案之间（如错题的“我的作答”）。
 */
export function QuestionView({ question, children }: { question: Question; children?: ReactNode }) {
  const { content } = question;
  // 学生手动添加的错题只有自己填的题目和答案，题型、难度、评分要点、解析都是占位，不显示
  const manual = question.source === 'manual';
  return (
    <article className={styles.question}>
      {!manual && (
        <p className={styles.meta}>
          {QUESTION_TYPE_LABELS[question.type]} · 难度 {question.difficulty}
          {question.source === 'ai' && ' · AI 生成'}
        </p>
      )}
      <Markdown text={content.stem} className={styles.stem} />
      {content.material && <Markdown text={content.material} className={styles.material} />}
      {content.options && <Options options={content.options} />}
      {content.sub_questions && (
        <ol className={styles.subs}>
          {content.sub_questions.map((sub) => (
            <li key={sub.seq}>
              <span className={styles.seq}>{sub.seq}.</span>
              <div>
                {sub.stem && <Markdown text={sub.stem} />}
                {sub.options && <Options options={sub.options} />}
              </div>
            </li>
          ))}
        </ol>
      )}
      {children}
      {question.answer && (
        <section className={styles.section}>
          <h4>参考答案</h4>
          <AnswerText answer={question.answer} />
        </section>
      )}
      {question.scoring_points && !manual && (
        <section className={styles.section}>
          <h4>评分要点</h4>
          <ul className={styles.points}>
            {question.scoring_points.map((p, i) => (
              <li key={i}>
                <Markdown inline text={p.point} />
                <span className={styles.score}>{p.score} 分</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {question.analysis && !manual && (
        <section className={styles.section}>
          <h4>解析</h4>
          <div className={styles.steps}>
            {question.analysis.map((step, i) => (
              <div className={styles.step} key={i}>
                <span className={styles.stepNumber}>{i + 1}</span>
                <div>
                  <h5>{step.title}</h5>
                  <Markdown text={step.body} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}

function Options({ options }: { options: Option[] }) {
  return (
    <ul className={styles.options}>
      {options.map((o) => (
        <li key={o.key}>
          <span className={styles.key}>{o.key}</span>
          <Markdown inline text={o.text} />
        </li>
      ))}
    </ul>
  );
}

/** 学生的作答；解答题按 Markdown 分段显示，其余显示成一行。 */
export function StudentAnswerText({ answer }: { answer: StudentAnswer }) {
  const text = answerText(answer);
  return 'text' in answer ? <Markdown text={text} /> : <Markdown inline text={text} />;
}

/** 参考答案；批改结果里“正确答案”也用它。 */
export function AnswerText({ answer }: { answer: Answer }) {
  if ('sub' in answer) {
    return (
      <ol className={styles.answerList}>
        {answer.sub.map((item) => (
          <li key={item.seq}>
            <span className={styles.seq}>{item.seq}.</span>
            <SubAnswerText item={item} />
          </li>
        ))}
      </ol>
    );
  }
  if ('text' in answer) {
    return (
      <>
        <Markdown text={answer.text} />
        {answer.final && (
          <p className={styles.final}>
            最终结果：
            <Markdown inline text={answer.final} />
          </p>
        )}
      </>
    );
  }
  return <SubAnswerText item={answer} />;
}

/** 单选、多选、判断、填空的答案；大题和小题共用。 */
function SubAnswerText({ item }: { item: Omit<Partial<SubAnswerItem>, 'seq'> }) {
  if (item.choice) return <span>{item.choice.join('、')}</span>;
  if (item.judge != null) return <span>{item.judge ? '正确' : '错误'}</span>;
  const { blanks } = item;
  if (!blanks) return null;
  return (
    <span className={styles.blanks}>
      {blanks.map((alternatives, i) => (
        <span key={i}>
          {blanks.length > 1 && `第 ${i + 1} 空：`}
          <Markdown inline text={alternatives[0]} />
          {alternatives.length > 1 && (
            <span className={styles.alt}>
              （也可写作 <Markdown inline text={alternatives.slice(1).join('、')} />）
            </span>
          )}
        </span>
      ))}
    </span>
  );
}
