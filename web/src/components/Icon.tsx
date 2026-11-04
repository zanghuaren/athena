import type { ReactNode } from 'react';

// 图标取自原型的 SVG sprite，线宽和描边方式与原型一致
const ICONS = {
  temple: [
    '0 0 32 36',
    <>
      <path d="M3 12 16 4l13 8M4 14h24M6 17v13M11 17v13M21 17v13M26 17v13M4 31h24M2 34h28M14 17v13M18 17v13" />
      <circle cx="16" cy="10" r="1.2" />
    </>,
  ],
  olive: [
    '0 0 90 45',
    <path d="M5 38C25 35 48 23 75 7M20 33c-8-3-10-10-7-12 7 0 11 5 7 12ZM32 28c-5-6-4-12 0-13 5 3 6 8 0 13ZM45 22c-2-8 0-12 4-12 4 5 2 9-4 12ZM58 16c0-7 4-11 8-9 1 5-2 8-8 9ZM26 31c5 6 12 7 14 4-2-6-9-8-14-4ZM42 24c6 5 12 5 14 1-3-4-9-5-14-1ZM57 16c7 4 13 2 13-2-4-3-9-2-13 2Z" />,
  ],
  plus: ['0 0 24 24', <path d="M12 5v14M5 12h14" />],
  left: ['0 0 24 24', <path d="m15 5-7 7 7 7" />],
  right: ['0 0 24 24', <path d="m9 5 7 7-7 7" />],
  chat: [
    '0 0 24 24',
    <path d="M20.5 11.3c0 4.4-3.9 7.7-8.7 7.7a10 10 0 0 1-3.3-.5L4 21l1.1-4.4a7.3 7.3 0 0 1-2-5.3c0-4.3 3.9-7.7 8.7-7.7s8.7 3.4 8.7 7.7Z" />,
  ],
  plan: [
    '0 0 24 24',
    <>
      <rect x="4" y="4" width="16" height="17" rx="2" />
      <path d="M8 2v4M16 2v4M4 9h16M8 13h3M8 17h7" />
    </>,
  ],
  book: [
    '0 0 24 24',
    <path d="M12 5.2C9.4 3.6 6.2 3 3 4v15c3.2-1 6.4-.4 9 1.2 2.6-1.6 5.8-2.2 9-1.2V4c-3.2-1-6.4-.4-9 1.2ZM12 5.2v15M6 8h3M15 8h3M6 11h3M15 11h3" />,
  ],
  cards: [
    '0 0 24 24',
    <>
      <rect x="5" y="5" width="15" height="15" rx="2" />
      <path d="M16 2H4a2 2 0 0 0-2 2v12M9 10h7M9 14h5" />
    </>,
  ],
  user: [
    '0 0 24 24',
    <>
      <circle cx="12" cy="7" r="4" />
      <path d="M4 21v-2a8 8 0 0 1 16 0v2H4Z" />
    </>,
  ],
  users: [
    '0 0 24 24',
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20v-1a6.5 6.5 0 0 1 13 0v1M16 4.6a3.5 3.5 0 0 1 0 6.8M18 13.6a6.5 6.5 0 0 1 3.5 5.9V20" />
    </>,
  ],
  checklist: [
    '0 0 24 24',
    <>
      <rect x="4" y="3" width="16" height="19" rx="2" />
      <path d="m8 8 1 1 2-2M14 8h3M8 13h3M14 13h3M8 17h7" />
    </>,
  ],
  pen: ['0 0 24 24', <path d="m16 3 5 5L8 21H3v-5L16 3ZM13 6l5 5M3 21l5-5" />],
  document: [
    '0 0 24 24',
    <path d="M14 2H5a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8l-6-6ZM14 2v6h6M8 12h8M8 16h8" />,
  ],
  chart: ['0 0 24 24', <path d="M4 3v17h17M8 16v-4M12 16V8M16 16v-6M20 16V6" />],
} satisfies Record<string, [string, ReactNode]>;

export type IconName = keyof typeof ICONS;

export function Icon({ name, className }: { name: IconName; className?: string }) {
  const [viewBox, shape] = ICONS[name];
  return (
    <svg
      viewBox={viewBox}
      className={className}
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {shape}
    </svg>
  );
}
