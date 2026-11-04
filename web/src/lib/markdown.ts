import katex from 'katex';
import 'katex/contrib/mhchem';
import MarkdownIt, { type StateInline } from 'markdown-it';

// 内容来自模型和用户输入，不允许原始 HTML
const md = new MarkdownIt({ html: false, breaks: true, linkify: false });

md.inline.ruler.before('escape', 'math', math);
md.inline.ruler.before('escape', 'math_paren', mathParen);
md.inline.ruler.before('emphasis', 'blank', blank);

md.renderer.rules.math = (tokens, idx) => {
  const { content, markup } = tokens[idx];
  try {
    return katex.renderToString(content, { displayMode: markup === '$$', throwOnError: true });
  } catch {
    // KP-03：公式渲染失败时显示原始 LaTeX，不能是空白
    return `<code class="math-raw">${md.utils.escapeHtml(markup + content + markup)}</code>`;
  }
};

md.renderer.rules.blank = (tokens, idx) => {
  const seq = tokens[idx].content;
  return seq
    ? `<span class="blank" aria-label="第 ${seq} 空">${seq}</span>`
    : '<span class="blank" aria-label="空"></span>';
};

/** 渲染题干、解析、AI 回答等成段的文字。写法见数据库设计 10.1。 */
export function renderMarkdown(src: string): string {
  return md.render(src);
}

/** 渲染选项这类单行文字，不包一层 <p>。 */
export function renderInline(src: string): string {
  return md.renderInline(src);
}

/**
 * `$...$` 和 `$$...$$`，按 Pandoc 的规则识别：开头的 `$` 后面、结尾的 `$` 前面不能是空白，
 * 结尾的 `$` 后面不能紧跟数字，这样 “costs $5 and $10” 不会被当成公式。
 */
function math(state: StateInline, silent: boolean): boolean {
  const { src, pos } = state;
  if (src[pos] !== '$') return false;
  const markup = src.startsWith('$$', pos) ? '$$' : '$';
  const from = pos + markup.length;
  if (markup === '$' && /\s/.test(src[from] ?? ' ')) return false;

  let end = src.indexOf(markup, from);
  while (end !== -1 && !isClosing(src, end, markup)) end = src.indexOf(markup, end + 1);
  if (end === -1 || end === from) return false;

  if (!silent) {
    const token = state.push('math', '', 0);
    token.content = src.slice(from, end);
    token.markup = markup;
  }
  state.pos = end + markup.length;
  return true;
}

/**
 * `\\(...\\)` 和 `\\[...\\]`。提示词要求模型用 `$`，但看图讲题时它常常还是用这两种写法，
 * 不识别的话页面上会显示一串反斜杠。
 */
function mathParen(state: StateInline, silent: boolean): boolean {
  const { src, pos } = state;
  const open = src.slice(pos, pos + 2);
  const close = { '\\(': '\\)', '\\[': '\\]' }[open];
  if (!close) return false;
  const end = src.indexOf(close, pos + 2);
  if (end === -1 || end === pos + 2) return false;

  if (!silent) {
    const token = state.push('math', '', 0);
    token.content = src.slice(pos + 2, end);
    token.markup = open === '\\(' ? '$' : '$$';
  }
  state.pos = end + 2;
  return true;
}

function isClosing(src: string, end: number, markup: string): boolean {
  if (src[end - 1] === '\\') return false;
  if (markup === '$$') return true;
  return !/\s/.test(src[end - 1]) && !/\d/.test(src[end + 1] ?? '');
}

/** 填空的空 `____`（至少 3 个下划线）和完形填空的空 `__1__`，要在加粗规则之前识别。 */
function blank(state: StateInline, silent: boolean): boolean {
  const match = /^(?:__(\d+)__(?!_)|_{3,})/.exec(state.src.slice(state.pos));
  if (!match) return false;
  if (!silent) state.push('blank', '', 0).content = match[1] ?? '';
  state.pos += match[0].length;
  return true;
}
