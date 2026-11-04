// S-04 框选与确认（SCAN-02）：框选一道题 → 识别 → 学生核对修改 → 回到对话开始讲解
import Cropper from 'cropperjs';
import 'cropperjs/dist/cropper.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router';
import { ApiError, type User } from '../../api/client';
import { fileUrl } from '../../api/files';
import { useRecognize } from '../../api/scans';
import { Button } from '../../components/Button';
import type { ScannedQuestion } from '../../components/ChatView';
import { ChoiceChips } from '../../components/ChoiceChips';
import { Notice } from '../../components/Notice';
import { PageHeading } from '../../components/PageHeading';
import { SUBJECT_OPTIONS } from '../../lib/labels';
import fieldStyles from '../../components/Field.module.css';
import styles from './ScanCrop.module.css';

type Subject = NonNullable<User['preferred_subject']>;

export function ScanCrop() {
  const { state } = useLocation();
  const photo = (state as { photo?: File } | null)?.photo;
  const [params] = useSearchParams();
  // 刷新页面后照片就没有了，回到拍照页重新选
  if (!photo) return <Navigate to={`/student/scan?${params}`} replace />;
  return <CropAndConfirm photo={photo} conversationId={params.get('c')} />;
}

function CropAndConfirm({ photo, conversationId }: { photo: File; conversationId: string | null }) {
  const navigate = useNavigate();
  const { search } = useLocation();
  const recognize = useRecognize();
  const [text, setText] = useState('');
  const [subject, setSubject] = useState<Subject>('math');
  const [unsupported, setUnsupported] = useState(false);

  const src = useMemo(() => URL.createObjectURL(photo), [photo]);
  useEffect(() => () => URL.revokeObjectURL(src), [src]);

  const imageRef = useRef<HTMLImageElement>(null);
  const cropperRef = useRef<Cropper | null>(null);
  useEffect(() => {
    const cropper = new Cropper(imageRef.current!, {
      viewMode: 1,
      autoCropArea: 0.8,
      background: false,
      toggleDragModeOnDblclick: false,
    });
    cropperRef.current = cropper;
    return () => {
      cropper.destroy();
    };
  }, [src]);

  const retake = () => navigate(`/student/scan${search}`, { replace: true });
  const chatPath = conversationId ? `/student/c/${conversationId}` : '/student';

  function submit() {
    const canvas = cropperRef.current!.getCroppedCanvas({
      maxWidth: 2048,
      maxHeight: 2048,
      fillColor: '#fff',
    });
    canvas.toBlob(
      (blob) =>
        recognize.mutate(blob!, {
          onSuccess: (r) => {
            setText(r.text);
            setSubject(r.subject);
          },
        }),
      'image/jpeg',
      0.9,
    );
  }

  function start() {
    const ask: ScannedQuestion = { content: text.trim(), image: recognize.data!.file, subject };
    navigate(chatPath, { replace: true, state: { ask } });
  }

  if (recognize.isSuccess) {
    return (
      <>
        <PageHeading title="确认题目" description="识别结果可以直接修改" />
        <label className={fieldStyles.label} htmlFor="recognized">
          识别结果
        </label>
        <textarea
          id="recognized"
          className={`${fieldStyles.input} ${styles.text}`}
          rows={6}
          maxLength={1000}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <img className={styles.thumb} src={fileUrl(recognize.data.file)} alt="框选的题目" />
        <ChoiceChips
          label="学科"
          options={SUBJECT_OPTIONS}
          value={[subject]}
          onChange={([s]) => setSubject(s)}
        />
        <Button variant="primary" block disabled={!text.trim()} onClick={start}>
          开始讲解
        </Button>
      </>
    );
  }

  const code = recognize.error instanceof ApiError ? recognize.error.code : null;
  return (
    <>
      <div className={styles.stage}>
        <img ref={imageRef} src={src} alt="拍下的照片" onError={() => setUnsupported(true)} />
      </div>
      {unsupported ? (
        <>
          <Notice tone="error">不支持这种图片格式，请换一张 jpg 或 png 图片</Notice>
          <Button variant="primary" block onClick={retake}>
            重新拍照
          </Button>
        </>
      ) : code === 'NO_QUESTION_FOUND' ? (
        <>
          <Notice tone="error">没有识别到题目</Notice>
          <Button block onClick={retake}>
            重新拍照
          </Button>
          <Button block onClick={() => navigate(chatPath, { replace: true })}>
            手动输入题目
          </Button>
        </>
      ) : (
        <>
          {recognize.error && <Notice tone="error">{recognize.error.message}</Notice>}
          {!recognize.error && <p className={styles.hint}>拖动框选一道题，照片可以缩放</p>}
          <div className={styles.bar}>
            <Button onClick={retake}>重拍</Button>
            <Button variant="primary" disabled={recognize.isPending} onClick={submit}>
              {recognize.isPending
                ? '正在识别…'
                : code === 'MULTIPLE_QUESTIONS'
                  ? '重新识别'
                  : '识别'}
            </Button>
          </div>
        </>
      )}
    </>
  );
}
