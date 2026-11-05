/** 列表里的时间：今天显示时刻，今年显示月日，更早的带上年份。 */
export function formatTime(iso: string, now = new Date()): string {
  const t = new Date(iso);
  const hm = `${t.getHours()}:${String(t.getMinutes()).padStart(2, '0')}`;
  if (t.toDateString() === now.toDateString()) return `今天 ${hm}`;
  const md = `${t.getMonth() + 1}月${t.getDate()}日`;
  return t.getFullYear() === now.getFullYear() ? md : `${t.getFullYear()}年${md}`;
}

/** 下次复习日期（北京时间的自然日，如 2026-11-06）：到期和逾期都是“今天复习”。 */
export function reviewDueText(day: string, now = new Date()): string {
  const [y, m, d] = day.split('-').map(Number);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((new Date(y, m - 1, d).getTime() - today.getTime()) / 86_400_000);
  if (days <= 0) return '今天复习';
  if (days === 1) return '明天复习';
  if (days === 2) return '后天复习';
  return y === now.getFullYear() ? `${m}月${d}日复习` : `${y}年${m}月${d}日复习`;
}
