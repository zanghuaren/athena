// T-21 AI 助教（ASK-07）：和学生对话页同一个对话区，没有讲解方式和拍照入口
import { useParams } from 'react-router';
import { useCurrentUser } from '../../components/AppShell';
import { ChatView } from '../../components/ChatView';
import { PageHeading } from '../../components/PageHeading';
import styles from './Assistant.module.css';

const EXAMPLES = ['勾股定理有哪几种证明方法适合初二学生？', '学生总把斜边找错，怎么讲？'];

export function Assistant() {
  const { conversationId } = useParams();
  return (
    <ChatView
      user={useCurrentUser()}
      base="/teacher/assistant"
      conversationId={conversationId ? Number(conversationId) : null}
      Empty={Empty}
    />
  );
}

function Empty({ ask }: { ask: (text: string) => void }) {
  return (
    <>
      <PageHeading title="今天想准备什么？" description="解题思路、讲法、学生常见错误，都可以问" />
      {EXAMPLES.map((q) => (
        <button key={q} type="button" className={styles.example} onClick={() => ask(q)}>
          {q}
        </button>
      ))}
    </>
  );
}
