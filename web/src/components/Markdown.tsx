import 'katex/dist/katex.min.css';
import { useMemo } from 'react';
import { renderInline, renderMarkdown } from '../lib/markdown';
import styles from './Markdown.module.css';

/** 题目、解析、AI 回答统一用它渲染：Markdown + LaTeX 公式。 */
export function Markdown({
  text,
  inline = false,
  className,
}: {
  text: string;
  inline?: boolean;
  className?: string;
}) {
  const html = useMemo(() => (inline ? renderInline(text) : renderMarkdown(text)), [text, inline]);
  const Tag = inline ? 'span' : 'div';
  const classes = [styles.markdown, className].filter(Boolean).join(' ');
  // 渲染器关掉了原始 HTML，这里的 HTML 只来自 markdown-it 和 KaTeX
  return <Tag className={classes} dangerouslySetInnerHTML={{ __html: html }} />;
}
