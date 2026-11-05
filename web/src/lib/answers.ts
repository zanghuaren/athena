import type { Question } from '../api/client';
import type { StudentAnswer } from '../api/scans';

type Part = { choice?: string[] | null; judge?: boolean | null; blanks?: string[] | null };

/** 学生作答的文字：拍照批改、错题本里“你的作答”，以及发给答疑的讲解请求。 */
export function answerText(answer: StudentAnswer): string {
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

/** “讲解这道题”发给答疑的文字：题目和学生的作答（有的话），太长时截掉题目的末尾。 */
export function explainText(question: Question, mine?: string): string {
  const { content } = question;
  const parts = [`帮我讲讲这道题：\n\n${content.stem}`];
  if (content.material) parts.push(content.material);
  if (content.options) parts.push(content.options.map((o) => `${o.key}. ${o.text}`).join('\n'));
  for (const sub of content.sub_questions ?? []) {
    const options = sub.options?.map((o) => `${o.key}. ${o.text}`).join('　') ?? '';
    parts.push(`${sub.seq}. ${sub.stem} ${options}`.trim());
  }
  const tail = mine ? `\n\n我的作答：${mine}` : '';
  return `${parts.join('\n\n').slice(0, MAX_ASK_LENGTH - tail.length)}${tail}`.slice(
    0,
    MAX_ASK_LENGTH,
  );
}
