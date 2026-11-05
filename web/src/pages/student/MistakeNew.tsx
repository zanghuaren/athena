// S-15 添加错题（MIS-01 手动添加）：拍照识别或输入题目，自己填答案，知识点从目录里选
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { useMe } from '../../api/auth';
import type { User } from '../../api/client';
import type { KnowledgePoint } from '../../api/knowledge';
import { useAddMistake } from '../../api/mistakes';
import { Button } from '../../components/Button';
import { ChoiceChips } from '../../components/ChoiceChips';
import { KnowledgePicker } from '../../components/KnowledgePicker';
import { Notice } from '../../components/Notice';
import { SUBJECT_OPTIONS } from '../../lib/labels';
import fieldStyles from '../../components/Field.module.css';
import styles from './MistakeNew.module.css';

type Subject = NonNullable<User['preferred_subject']>;
/** S-04 拍照识别后带回来的题目 */
export type RecognizedForMistake = { text: string; subject: Subject };

const MAX_POINTS = 3;

export function MistakeNew() {
  const me = useMe();
  const navigate = useNavigate();
  const recognized = (useLocation().state as { recognized?: RecognizedForMistake } | null)
    ?.recognized;
  const add = useAddMistake();
  const [stem, setStem] = useState(recognized?.text ?? '');
  const [mine, setMine] = useState('');
  const [answer, setAnswer] = useState('');
  const [subject, setSubject] = useState<Subject>(
    recognized?.subject ?? me.data?.preferred_subject ?? 'math',
  );
  const [points, setPoints] = useState<KnowledgePoint[]>([]);

  function save() {
    add.mutate(
      {
        source: 'manual',
        subject,
        stem: stem.trim(),
        answer: answer.trim(),
        my_answer: mine.trim(),
        knowledge_point_ids: points.map((k) => k.id),
      },
      { onSuccess: (m) => navigate(`/student/mistakes/${m.id}`, { replace: true }) },
    );
  }

  const ready = stem.trim() && answer.trim() && points.length > 0;
  return (
    <>
      {/* 识别完回到这一页，返回时直接回错题本 */}
      <Button
        block
        onClick={() => navigate('/student/scan?mode=ask&for=mistake', { replace: true })}
      >
        拍照识别一道题
      </Button>
      <label className={fieldStyles.label} htmlFor="new-stem">
        题目
      </label>
      <textarea
        id="new-stem"
        className={`${fieldStyles.input} ${styles.area}`}
        rows={5}
        maxLength={1000}
        value={stem}
        onChange={(e) => setStem(e.target.value)}
      />
      <label className={fieldStyles.label} htmlFor="new-mine">
        我的答案
      </label>
      <textarea
        id="new-mine"
        className={`${fieldStyles.input} ${styles.area}`}
        rows={2}
        maxLength={1000}
        value={mine}
        onChange={(e) => setMine(e.target.value)}
      />
      <label className={fieldStyles.label} htmlFor="new-answer">
        正确答案
      </label>
      <textarea
        id="new-answer"
        className={`${fieldStyles.input} ${styles.area}`}
        rows={2}
        maxLength={1000}
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
      />
      <ChoiceChips
        label="学科"
        options={SUBJECT_OPTIONS}
        value={[subject]}
        onChange={([s]) => {
          setSubject(s);
          setPoints([]);
        }}
      />
      <KnowledgePicker
        subject={subject}
        grade={me.data?.grade ?? null}
        value={points}
        onChange={setPoints}
        max={MAX_POINTS}
      />
      {add.error && <Notice tone="error">{add.error.message}</Notice>}
      <Button variant="primary" block disabled={!ready || add.isPending} onClick={save}>
        {add.isPending ? '正在保存…' : '保存错题'}
      </Button>
      {!ready && <p className={styles.hint}>请填写题目、正确答案，并选择知识点</p>}
    </>
  );
}
