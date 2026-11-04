import { describe, expect, it } from 'vitest';
import { renderInline, renderMarkdown } from './markdown';

describe('renderMarkdown', () => {
  it('渲染行内公式和独立公式', () => {
    expect(renderInline('$x^2$')).toContain('class="katex"');
    expect(renderMarkdown('$$\\frac{1}{2}$$')).toContain('katex-display');
  });

  it('也认 \\(...\\) 和 \\[...\\] 写的公式', () => {
    expect(renderInline('比值 \\(\\frac{12}{13}\\) 不变')).toContain('class="katex"');
    expect(renderMarkdown('\\[\nx = 2\n\\]')).toContain('katex-display');
    expect(renderInline('括号 \\(只开不关')).toBe('括号 (只开不关');
  });

  it('钱数里的 $ 不当成公式', () => {
    expect(renderInline('costs $5 and $10')).toBe('costs $5 and $10');
    expect(renderInline('\\$x$')).toBe('$x$');
  });

  it('公式写错时显示原始 LaTeX', () => {
    expect(renderInline('$\\frac{1$')).toBe('<code class="math-raw">$\\frac{1$</code>');
  });

  it('空位不会被当成加粗', () => {
    expect(renderInline('I __1__ a student.')).toBe(
      'I <span class="blank" aria-label="第 1 空">1</span> a student.',
    );
    expect(renderInline('$1+2=$____')).toContain('<span class="blank" aria-label="空"></span>');
    expect(renderInline('**重点**')).toBe('<strong>重点</strong>');
  });

  it('不渲染原始 HTML', () => {
    expect(renderInline('<img src=x onerror=alert(1)>')).not.toContain('<img');
  });

  it('支持表格和化学式', () => {
    expect(renderMarkdown('| a | b |\n|---|---|\n| 1 | 2 |')).toContain('<table>');
    expect(renderInline('$\\ce{H2O}$')).toContain('class="katex"');
  });
});
