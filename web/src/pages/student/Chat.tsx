// S-01 对话（ASK-01～04）
import { useParams } from 'react-router';
import { useSuggestion } from '../../api/conversations';
import { useCurrentUser } from '../../components/AppShell';
import { ChatView } from '../../components/ChatView';
import { Icon } from '../../components/Icon';
import { Markdown } from '../../components/Markdown';
import hero from './hero.webp';
import styles from './Chat.module.css';

// AI 出题失败时显示的语文问题
const FALLBACK = '如何理解“钱塘江上潮信来，今日方知我是我”？';

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
  // 由 AI 现编一个能引人思考的语文问题，每分钟换一个，也可以点刷新
  const suggestion = useSuggestion();
  const question = suggestion.data?.text ?? (suggestion.isError ? FALLBACK : null);
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
      <div className={styles.suggestion}>
        {question ? (
          <button type="button" className={styles.example} onClick={() => ask(question)}>
            <Markdown inline text={question} />
          </button>
        ) : (
          <p className={`${styles.example} ${styles.loading}`}>正在想一个问题…</p>
        )}
        <button
          type="button"
          className={styles.refresh}
          aria-label="换一个问题"
          disabled={suggestion.isFetching}
          onClick={() => void suggestion.refetch()}
        >
          <Icon name="refresh" className={suggestion.isFetching ? styles.spinning : undefined} />
        </button>
      </div>
    </>
  );
}
