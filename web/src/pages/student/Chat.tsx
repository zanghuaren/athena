// S-01 对话（ASK-01～04）
import { useParams } from 'react-router';
import { useCurrentUser } from '../../components/AppShell';
import { ChatView } from '../../components/ChatView';
import hero from './hero.webp';
import styles from './Chat.module.css';

// 原型空状态里的三道示例题
const EXAMPLES = [
  '解方程 x² − 5x + 6 = 0。',
  '一个木块漂浮在水面上，浮力和重力有什么关系？',
  'I have lived here ___ three years. 应填 for 还是 since？',
];

export function Chat() {
  const { conversationId } = useParams();
  return (
    <ChatView
      user={useCurrentUser()}
      base="/student"
      conversationId={conversationId ? Number(conversationId) : null}
      Empty={Empty}
    />
  );
}

function Empty({ ask }: { ask: (text: string) => void }) {
  return (
    <>
      <div className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.eyebrow}>THE ATHENAEUM · 学思之间</span>
          <h2>
            <span>知其然，</span>
            <span>也知其所以然。</span>
          </h2>
          <p>让每一个问题，都有值得追寻的答案。</p>
        </div>
        <img src={hero} alt="" />
      </div>
      <svg
        className={styles.meander}
        viewBox="0 0 784 10"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <pattern id="greek-key" width="36" height="10" patternUnits="userSpaceOnUse">
            <path d="M0 9H35V1H7v5h21V4H14" fill="none" stroke="currentColor" strokeWidth=".65" />
          </pattern>
        </defs>
        <rect width="784" height="10" fill="url(#greek-key)" />
      </svg>
      <div className={styles.divider}>从一个问题开始</div>
      {EXAMPLES.map((q) => (
        <button key={q} type="button" className={styles.example} onClick={() => ask(q)}>
          {q}
        </button>
      ))}
    </>
  );
}
