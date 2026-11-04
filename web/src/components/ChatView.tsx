// S-01 对话 / T-21 AI 助教共用的对话区：消息流、讲解方式切换、回答后的操作、输入框
import {
  useEffect,
  useEffectEvent,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
} from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { ApiError, type User } from '../api/client';
import {
  MAX_TURNS,
  streamMessage,
  useConversation,
  useCreateConversation,
  usePatchConversation,
  useRefreshConversation,
  type Message,
  type MessageBody,
  type StreamEvent,
} from '../api/conversations';
import { fileUrl, type FileOut } from '../api/files';
import { SUBJECT_OPTIONS } from '../lib/labels';
import { Button } from './Button';
import { Icon } from './Icon';
import { Markdown } from './Markdown';
import { Notice } from './Notice';
import styles from './ChatView.module.css';

type Subject = User['preferred_subject'];
type ExplainMode = User['explain_mode'];

const ACTION_LABELS: Record<NonNullable<Message['action']>, string> = {
  hint: '再给点提示',
  full: '看完整解答',
  example: '举个例子',
};

/** S-04 确认后带回对话页的题目，进入页面后自动发出（SCAN-02）。 */
export type ScannedQuestion = { content: string; image: FileOut; subject: NonNullable<Subject> };

/** 正在生成或刚停止的消息先放在本地；正常结束后以服务端为准。 */
type Local = { conversationId: number; messages: Message[] };

type Props = {
  user: User;
  /** 对话页的路径：/student 或 /teacher/assistant，会话是 `${base}/c/:id` */
  base: string;
  conversationId: number | null;
  /** 空会话时显示的内容，ask 直接发出一个示例问题 */
  Empty: ComponentType<{ ask: (text: string) => void }>;
};

export function ChatView({ user, base, conversationId, Empty }: Props) {
  const isStudent = user.role === 'student';
  const navigate = useNavigate();
  const location = useLocation();
  const detail = useConversation(conversationId);
  const create = useCreateConversation();
  const patch = usePatchConversation();
  const refresh = useRefreshConversation();

  const [local, setLocal] = useState<Local | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [copied, setCopied] = useState<number | null>(null);
  // 新会话还没建，先记下选择，发第一条消息时一起建
  const [newSettings, setNewSettings] = useState<{ subject: Subject; explain_mode: ExplainMode }>({
    subject: user.preferred_subject,
    explain_mode: user.explain_mode,
  });
  const abortRef = useRef<AbortController | null>(null);

  const conversation = conversationId === null ? null : detail.data;
  const messages = useMemo(
    () =>
      local && local.conversationId === conversationId
        ? local.messages
        : (conversation?.messages ?? []),
    [local, conversationId, conversation],
  );
  const settings = conversation ?? newSettings;
  const last = messages.at(-1);
  const tooLong = (conversation?.turn_count ?? 0) >= MAX_TURNS;

  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages, streaming, error]);

  function changeSettings(change: { subject?: Subject; explain_mode?: ExplainMode }) {
    if (conversationId === null) setNewSettings({ ...newSettings, ...change });
    else patch.mutate({ id: conversationId, ...change });
  }

  // 拍照答疑：等会话详情加载好再发，否则本地消息列表里没有之前的消息
  const scanned = (location.state as { ask?: ScannedQuestion } | null)?.ask;
  const ready = conversationId === null || conversation !== undefined;
  const scannedSent = useRef(false);
  const sendScanned = useEffectEvent(async (q: ScannedQuestion) => {
    // 清掉页面状态，刷新或返回时不会再发一次
    navigate(location.pathname, { replace: true, state: null });
    if (conversation && conversation.subject !== q.subject) {
      await patch.mutateAsync({ id: conversation.id, subject: q.subject });
    }
    await send({ content: q.content, image_file_id: q.image.id }, q);
  });
  useEffect(() => {
    if (!scanned || !ready || scannedSent.current) return;
    scannedSent.current = true;
    void sendScanned(scanned);
  }, [scanned, ready]);

  async function send(body: MessageBody, scan?: ScannedQuestion) {
    setError(null);
    stickRef.current = true;
    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);

    let id = conversationId;
    try {
      if (id === null) {
        const settings = scan ? { ...newSettings, subject: scan.subject } : newSettings;
        id = (await create.mutateAsync(settings)).id;
        navigate(`${base}/c/${id}`, { replace: true });
      }
      await streamReply(id, body, controller.signal, scan?.image ?? null);
      if (controller.signal.aborted) {
        // 服务端这时可能还没存完，先保留本地内容，只刷新列表
        void refresh(id, false);
      } else {
        await refresh(id, true);
        setLocal(null);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '发送失败，请重试');
      if (id !== null) await refresh(id, true);
      setLocal(null);
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  async function streamReply(
    id: number,
    body: MessageBody,
    signal: AbortSignal,
    image: FileOut | null,
  ) {
    let current = [...messages];
    const show = (next: Message[]) => {
      current = next;
      setLocal({ conversationId: id, messages: next });
    };
    if (body.action === 'regenerate') show(current.slice(0, -1));
    else if (body.action !== 'continue') {
      show([...current, localMessage(-1, 'user', body.content, body.action ?? null, image)]);
    }

    let replyId = 0;
    const updateReply = (change: (m: Message) => Message) =>
      show(current.map((m) => (m.id === replyId ? change(m) : m)));

    await streamMessage(id, body, signal, (e: StreamEvent) => {
      switch (e.event) {
        case 'start':
          replyId = e.data.message_id;
          if (body.action !== 'continue') {
            show([...current, localMessage(replyId, 'assistant', '', null)]);
          }
          break;
        case 'delta':
          updateReply((m) => ({ ...m, content: m.content + e.data.text }));
          break;
        case 'replace':
          updateReply((m) => ({ ...m, content: e.data.text }));
          break;
        case 'done':
          updateReply((m) => ({ ...m, status: e.data.status }));
          break;
        case 'error':
          setError(e.data.message);
          break;
      }
    });
    if (signal.aborted) updateReply((m) => ({ ...m, status: 'interrupted' }));
  }

  function submit() {
    const text = draft.trim();
    if (!text || streaming) return;
    setDraft('');
    void send({ content: text });
  }

  async function copy(message: Message) {
    await navigator.clipboard.writeText(message.content);
    setCopied(message.id);
    setTimeout(() => setCopied(null), 2000);
  }

  // 拍照答疑识别出的题目回到当前会话里发（SCAN-02）
  const scanPath = (mode: 'ask' | 'grade') =>
    `/student/scan?mode=${mode}${conversationId ? `&c=${conversationId}` : ''}`;

  const lastReply = !streaming && last?.role === 'assistant' ? last : null;
  // 已经看过完整解答，就不再给“再给点提示”“看完整解答”
  const solved = messages.at(-2)?.action === 'full';

  return (
    <>
      <div
        ref={scrollRef}
        className={styles.scroll}
        onScroll={(e) => {
          const el = e.currentTarget;
          stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
      >
        <div className={styles.read}>
          <div className={styles.head}>
            <span>{conversation?.title}</span>
            <label>
              学科
              <select
                value={settings.subject ?? ''}
                onChange={(e) => changeSettings({ subject: (e.target.value || null) as Subject })}
              >
                <option value="">自动识别</option>
                {SUBJECT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            {isStudent && (
              <label>
                讲解方式
                <select
                  value={settings.explain_mode ?? 'guided'}
                  onChange={(e) => changeSettings({ explain_mode: e.target.value as ExplainMode })}
                >
                  <option value="guided">引导式</option>
                  <option value="direct">直接讲解</option>
                </select>
              </label>
            )}
          </div>
          {messages.length === 0 && conversationId === null ? (
            <Empty ask={(text) => void send({ content: text })} />
          ) : (
            <>
              {detail.isError && <Notice tone="error">{detail.error.message}</Notice>}
              {messages.map((m) =>
                m.role === 'user' ? (
                  <div key={m.id} className={styles.me}>
                    <div>
                      {m.image && (
                        <img className={styles.photo} src={fileUrl(m.image)} alt="题目图片" />
                      )}
                      {m.action ? ACTION_LABELS[m.action] : <Markdown text={m.content} />}
                    </div>
                  </div>
                ) : (
                  <div key={m.id} className={styles.ai}>
                    <div className={styles.aiHead}>
                      <Icon name="temple" />
                      <span>ATHENA</span>
                    </div>
                    {m.content ? (
                      <Markdown text={m.content} />
                    ) : (
                      streaming && <p className={styles.thinking}>正在思考…</p>
                    )}
                  </div>
                ),
              )}
              {lastReply?.status === 'interrupted' && !error && (
                <Notice tone="error">回答没有生成完</Notice>
              )}
              {error && <Notice tone="error">{error}</Notice>}
              {lastReply && (
                <div className={styles.actions}>
                  {lastReply.status === 'interrupted' ? (
                    <>
                      <Button size="sm" onClick={() => send({ content: '', action: 'continue' })}>
                        继续生成
                      </Button>
                      <Button size="sm" onClick={() => send({ content: '', action: 'regenerate' })}>
                        重新生成
                      </Button>
                    </>
                  ) : lastReply.status === 'done' ? (
                    <>
                      {isStudent && settings.explain_mode === 'guided' && !solved && (
                        <>
                          <Button size="sm" onClick={() => send({ content: '', action: 'hint' })}>
                            再给点提示
                          </Button>
                          <Button size="sm" onClick={() => send({ content: '', action: 'full' })}>
                            看完整解答
                          </Button>
                        </>
                      )}
                      <Button
                        variant="link"
                        onClick={() => send({ content: '', action: 'example' })}
                      >
                        举个例子
                      </Button>
                      <Button variant="link" onClick={() => copy(lastReply)}>
                        {copied === lastReply.id ? '已复制' : '复制'}
                      </Button>
                      <Button
                        variant="link"
                        onClick={() => send({ content: '', action: 'regenerate' })}
                      >
                        重新生成
                      </Button>
                    </>
                  ) : null}
                </div>
              )}
              {tooLong && (
                <Notice>
                  这个会话太长了，开一个新会话吧。 <Link to={base}>开启新对话</Link>
                </Notice>
              )}
            </>
          )}
        </div>
      </div>
      <div className={styles.dock}>
        <div className={styles.read}>
          {isStudent && (
            <div className={styles.tools}>
              <Link to={scanPath('ask')}>
                <Icon name="camera" />
                拍照答疑
              </Link>
              <Link to={scanPath('grade')}>
                <Icon name="checklist" />
                作业批改
              </Link>
            </div>
          )}
          <div className={styles.composer}>
            {isStudent ? (
              <Link to={scanPath('ask')} className={styles.attach} aria-label="拍照添加题目">
                <Icon name="camera" />
              </Link>
            ) : (
              <Link to={base} className={styles.attach} aria-label="开启助教新对话">
                <Icon name="plus" />
              </Link>
            )}
            <textarea
              aria-label={isStudent ? '输入问题或你的想法' : '向 AI 助教提问'}
              placeholder={isStudent ? '写下问题，一起想明白。' : '问问备课、讲法或解题思路'}
              rows={1}
              maxLength={1000}
              value={draft}
              disabled={tooLong}
              onChange={(e) => {
                setDraft(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = `${Math.min(e.target.scrollHeight, 112)}px`;
              }}
              onKeyDown={(e) => {
                // 输入法选词时的回车不发送
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            {streaming ? (
              <button
                type="button"
                className={styles.send}
                aria-label="停止生成"
                onClick={() => abortRef.current?.abort()}
              >
                <Icon name="stop" />
              </button>
            ) : (
              <button
                type="button"
                className={styles.send}
                aria-label="发送问题"
                disabled={!draft.trim() || tooLong}
                onClick={submit}
              >
                <Icon name="send" />
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function localMessage(
  id: number,
  role: Message['role'],
  content: string,
  action: Message['action'],
  image: FileOut | null = null,
): Message {
  const created_at = new Date().toISOString();
  return { id, role, action, content, status: 'done', image, created_at };
}
