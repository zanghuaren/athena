import { describe, expect, it } from 'vitest';
import { formatTime, reviewDueText } from './time';

describe('formatTime', () => {
  const now = new Date(2026, 10, 4, 18, 0);

  it('今天只显示时刻', () => {
    expect(formatTime(new Date(2026, 10, 4, 9, 5).toISOString(), now)).toBe('今天 9:05');
  });

  it('今年显示月日，更早带年份', () => {
    expect(formatTime(new Date(2026, 10, 3, 9, 5).toISOString(), now)).toBe('11月3日');
    expect(formatTime(new Date(2025, 0, 2).toISOString(), now)).toBe('2025年1月2日');
  });
});

describe('reviewDueText', () => {
  const now = new Date(2026, 11, 30, 23, 30);

  it('到期和逾期都算今天', () => {
    expect(reviewDueText('2026-12-30', now)).toBe('今天复习');
    expect(reviewDueText('2026-12-01', now)).toBe('今天复习');
  });

  it('明天、后天，再往后显示日期，跨年带年份', () => {
    expect(reviewDueText('2026-12-31', now)).toBe('明天复习');
    expect(reviewDueText('2027-01-01', now)).toBe('后天复习');
    expect(reviewDueText('2027-01-05', now)).toBe('2027年1月5日复习');
    expect(reviewDueText('2026-12-30', new Date(2026, 11, 20))).toBe('12月30日复习');
  });
});
