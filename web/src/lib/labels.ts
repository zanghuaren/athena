import type { Question, User } from '../api/client';
import type { components } from '../api/schema';

type Subject = NonNullable<User['preferred_subject']>;
type Grade = NonNullable<User['grade']>;

export const SUBJECT_LABELS: Record<Subject, string> = {
  math: '数学',
  physics: '物理',
  english: '英语',
};

export const GRADE_LABELS: Record<Grade, string> = {
  7: '七年级',
  8: '八年级',
  9: '九年级',
};

export const QUESTION_TYPE_LABELS: Record<Question['type'], string> = {
  single: '单选题',
  multiple: '多选题',
  judge: '判断题',
  blank: '填空题',
  solution: '解答题',
  cloze: '完形填空',
  reading: '阅读理解',
  essay: '作文',
};

type ErrorReason = NonNullable<components['schemas']['AttemptResult']['error_reason']>;

export const ERROR_REASON_LABELS: Record<ErrorReason, string> = {
  concept: '概念不清',
  calculation: '计算失误',
  reading: '审题错误',
  method: '方法不当',
  careless: '粗心',
  other: '其他',
};

export const SUBJECT_OPTIONS = Object.entries(SUBJECT_LABELS).map(([value, label]) => ({
  value: value as Subject,
  label,
}));

export const GRADE_OPTIONS = Object.entries(GRADE_LABELS).map(([value, label]) => ({
  value: Number(value) as Grade,
  label,
}));

/** 侧栏和“我的”页里那一行身份说明，如“八年级”“数学 · 八年级、九年级”。 */
export function userSummary(user: User): string {
  if (user.role === 'student') return user.grade ? GRADE_LABELS[user.grade] : '';
  const subjects = (user.teach_subjects ?? []).map((s) => SUBJECT_LABELS[s]).join('、');
  const grades = (user.teach_grades ?? []).map((g) => GRADE_LABELS[g]).join('、');
  return `${subjects} · ${grades}`;
}

type Mistake = components['schemas']['MistakeOut'];

export const MISTAKE_SOURCE_LABELS: Record<Mistake['source'], string> = {
  homework: '作业',
  scan: '拍照批改',
  ask: '答疑',
  practice: '练习',
  manual: '手动添加',
};

/** 错题的复习状态（MIS-02）：待复习 / 复习中 · 第 N 次 / 已掌握。 */
export function mistakeStatusText(mistake: Pick<Mistake, 'status' | 'review_count'>): string {
  if (mistake.status === 'mastered') return '已掌握';
  if (mistake.status === 'reviewing') return `复习中 · 第 ${mistake.review_count} 次`;
  return '待复习';
}
