import type { User } from '../api/client';

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
