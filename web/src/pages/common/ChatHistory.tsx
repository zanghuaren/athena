// S-02 会话历史（ASK-04），教师的 AI 助教也用这一页
import { useRef, useState } from 'react';
import { Link } from 'react-router';
import {
  useConversations,
  useDeleteConversation,
  usePatchConversation,
  type Conversation,
} from '../../api/conversations';
import { useCurrentUser } from '../../components/AppShell';
import { Button } from '../../components/Button';
import { Notice } from '../../components/Notice';
import { TextField } from '../../components/TextField';
import { SUBJECT_LABELS } from '../../lib/labels';
import { formatTime } from '../../lib/time';
import fieldStyles from '../../components/Field.module.css';
import styles from './ChatHistory.module.css';

export function ChatHistory() {
  const user = useCurrentUser();
  const base = user.role === 'student' ? '/student' : '/teacher/assistant';
  const [q, setQ] = useState('');
  const list = useConversations(q.trim(), 100);
  const [editing, setEditing] = useState<Conversation | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  function edit(c: Conversation) {
    setEditing(c);
    dialogRef.current?.showModal();
  }

  return (
    <>
      <label className={fieldStyles.label} htmlFor="history-search">
        搜索对话
      </label>
      <input
        id="history-search"
        type="search"
        className={fieldStyles.input}
        placeholder="输入标题或对话内容"
        maxLength={50}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {list.isError && <Notice tone="error">{list.error.message}</Notice>}
      {list.data?.items.map((c) => (
        <div key={c.id} className={styles.row}>
          <Link to={`${base}/c/${c.id}`}>
            <b>{c.title}</b>
            <span>
              {c.subject ? SUBJECT_LABELS[c.subject] : '自动识别'} · {formatTime(c.updated_at)}
            </span>
          </Link>
          <Button size="sm" aria-label={`编辑${c.title}`} onClick={() => edit(c)}>
            编辑
          </Button>
        </div>
      ))}
      {list.data?.items.length === 0 && (
        <p className={styles.empty}>
          {q.trim() ? '没有匹配的对话，试试其他关键词。' : '还没有对话，回到对话页问一个问题吧。'}
        </p>
      )}
      <dialog ref={dialogRef} className={styles.dialog} onClose={() => setEditing(null)}>
        {editing && <EditForm key={editing.id} conversation={editing} dialog={dialogRef} />}
      </dialog>
    </>
  );
}

function EditForm({
  conversation,
  dialog,
}: {
  conversation: Conversation;
  dialog: React.RefObject<HTMLDialogElement | null>;
}) {
  const [title, setTitle] = useState(conversation.title);
  const patch = usePatchConversation();
  const remove = useDeleteConversation();
  const close = () => dialog.current?.close();
  const error = patch.error ?? remove.error;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        patch.mutate({ id: conversation.id, title: title.trim() }, { onSuccess: close });
      }}
    >
      <TextField
        label="对话标题"
        required
        maxLength={30}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      {error && <Notice tone="error">{error.message}</Notice>}
      <div className={styles.buttons}>
        <Button type="submit" variant="primary" disabled={!title.trim() || patch.isPending}>
          保存标题
        </Button>
        <Button
          disabled={remove.isPending}
          onClick={() => remove.mutate(conversation.id, { onSuccess: close })}
        >
          删除对话
        </Button>
        <Button onClick={close}>取消</Button>
      </div>
    </form>
  );
}
