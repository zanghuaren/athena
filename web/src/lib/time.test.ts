import { describe, expect, it } from 'vitest';
import { formatTime } from './time';

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
