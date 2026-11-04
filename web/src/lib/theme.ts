// ME-03：主题和“减少动态效果”只存在本机，不同步到服务端
export type Theme = 'light' | 'dark' | 'system';

const THEME_KEY = 'athena.theme';
const REDUCE_MOTION_KEY = 'athena.reduceMotion';
const darkQuery = matchMedia('(prefers-color-scheme: dark)');

export function getTheme(): Theme {
  return (localStorage.getItem(THEME_KEY) as Theme | null) ?? 'light';
}

export function setTheme(theme: Theme): void {
  localStorage.setItem(THEME_KEY, theme);
  applyTheme();
}

export function getReduceMotion(): boolean {
  return localStorage.getItem(REDUCE_MOTION_KEY) === '1';
}

export function setReduceMotion(on: boolean): void {
  localStorage.setItem(REDUCE_MOTION_KEY, on ? '1' : '0');
  applyTheme();
}

function applyTheme(): void {
  const theme = getTheme();
  const dark = theme === 'dark' || (theme === 'system' && darkQuery.matches);
  const root = document.documentElement;
  root.dataset.theme = dark ? 'dark' : 'light';
  root.toggleAttribute('data-reduce-motion', getReduceMotion());
}

export function initTheme(): void {
  applyTheme();
  darkQuery.addEventListener('change', applyTheme);
}
