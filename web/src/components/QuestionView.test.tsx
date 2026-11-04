import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Question } from '../api/client';
import { QuestionView } from './QuestionView';

const base: Omit<Question, 'type' | 'content' | 'answer'> = {
  id: 1,
  subject: 'english',
  difficulty: 2,
  source: 'preset',
  knowledge_points: [],
  analysis: null,
  scoring_points: null,
};

const cloze: Question = {
  ...base,
  type: 'cloze',
  content: {
    stem: '阅读短文，选择最佳答案。',
    images: [],
    options: null,
    blank_count: null,
    material: 'I __1__ a student.',
    sub_questions: [
      {
        seq: 1,
        type: 'single',
        stem: '',
        options: [
          { key: 'A', text: 'am' },
          { key: 'B', text: 'is' },
        ],
        blank_count: null,
        score: 1,
      },
    ],
  },
  answer: null,
};

describe('QuestionView', () => {
  it('学生作答时没有答案就不显示答案区', () => {
    const html = renderToStaticMarkup(<QuestionView question={cloze} />);
    expect(html).toContain('完形填空');
    expect(html).toContain('aria-label="第 1 空"');
    expect(html).toContain('am');
    expect(html).not.toContain('参考答案');
  });

  it('显示小题答案、填空的等价答案和解析', () => {
    const withAnswer = renderToStaticMarkup(
      <QuestionView question={{ ...cloze, answer: { sub: [{ seq: 1, choice: ['A'] }] } }} />,
    );
    expect(withAnswer).toContain('参考答案');

    const blank: Question = {
      ...base,
      subject: 'math',
      type: 'blank',
      source: 'ai',
      content: { ...cloze.content, stem: '$\\frac12=$____', material: null, sub_questions: null },
      answer: { blanks: [['0.5', '1/2']] },
      analysis: [{ title: '化成小数', body: '$1÷2=0.5$' }],
    };
    const html = renderToStaticMarkup(<QuestionView question={blank} />);
    expect(html).toContain('AI 生成');
    expect(html).toContain('也可写作');
    expect(html).toContain('化成小数');
    expect(html).not.toContain('第 1 空：');
  });
});
