/** 列表里的时间：今天显示时刻，今年显示月日，更早的带上年份。 */
export function formatTime(iso: string, now = new Date()): string {
  const t = new Date(iso);
  const hm = `${t.getHours()}:${String(t.getMinutes()).padStart(2, '0')}`;
  if (t.toDateString() === now.toDateString()) return `今天 ${hm}`;
  const md = `${t.getMonth() + 1}月${t.getDate()}日`;
  return t.getFullYear() === now.getFullYear() ? md : `${t.getFullYear()}年${md}`;
}
