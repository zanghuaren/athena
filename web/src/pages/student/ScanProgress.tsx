// S-05 批改进度（SCAN-03）：按阶段显示进度，可以离开；完成后换成 S-06，失败时提示重拍
import { useEffect, useEffectEvent } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router';
import { fileUrl } from '../../api/files';
import { useJob, type Job } from '../../api/jobs';
import { useRefreshScan, useScan } from '../../api/scans';
import { Button } from '../../components/Button';
import { Notice } from '../../components/Notice';
import styles from './ScanProgress.module.css';

const STAGES = [
  { stage: 'recognize_questions', label: '识别题目' },
  { stage: 'recognize_answers', label: '识别手写作答' },
  { stage: 'grade_questions', label: '逐题批改' },
];

const FAIL_MESSAGES = {
  unclear: '照片不清楚，没法识别',
  no_question: '没有识别到题目',
  error: '批改没有完成，请重新拍一次',
};

export function ScanProgress() {
  const id = Number(useParams().scanId);
  const navigate = useNavigate();
  const scan = useScan(id);
  const job = useJob(scan.data?.job_id ?? null);
  const refresh = useRefreshScan();
  const jobStatus = job.data?.status;

  const finish = useEffectEvent(async (succeeded: boolean) => {
    // 先取到最新的批改，否则结果页拿到的还是“批改中”，又会跳回来
    await refresh(id);
    if (succeeded) navigate(`/student/scans/${id}`, { replace: true });
  });
  useEffect(() => {
    if (jobStatus === 'succeeded' || jobStatus === 'failed') void finish(jobStatus === 'succeeded');
  }, [jobStatus]);

  if (scan.error) return <Notice tone="error">{scan.error.message}</Notice>;
  if (!scan.data) return null;
  if (scan.data.status === 'done') return <Navigate to={`/student/scans/${id}`} replace />;

  const retake = () => navigate('/student/scan?mode=grade', { replace: true });
  return (
    <>
      <img className={styles.photo} src={fileUrl(scan.data.image)} alt="作业原图" />
      {scan.data.status === 'failed' ? (
        <>
          <Notice tone="error">
            {job.data?.error?.message ?? FAIL_MESSAGES[scan.data.fail_reason ?? 'error']}
          </Notice>
          <Button variant="primary" block onClick={retake}>
            重新拍
          </Button>
        </>
      ) : (
        <>
          {job.data && <Stages job={job.data} />}
          {job.error && <Notice tone="error">{job.error.message}</Notice>}
          <p className={styles.hint}>
            可以离开这个页面，批改会在后台继续，完成后在“我的 › 批改记录”里查看
          </p>
        </>
      )}
    </>
  );
}

function Stages({ job }: { job: Job }) {
  // 排队时还没有阶段，算作第一个阶段
  const current = Math.max(
    0,
    STAGES.findIndex((s) => s.stage === job.stage),
  );
  return (
    <>
      <ol className={styles.stages}>
        {STAGES.map((s, i) => (
          <li key={s.stage} className={i < current ? styles.done : i === current ? styles.now : ''}>
            <span aria-hidden="true">{i < current ? '✓' : i === current ? '…' : '○'}</span>
            {s.label}
          </li>
        ))}
      </ol>
      <div
        className={styles.bar}
        role="progressbar"
        aria-label="批改进度"
        aria-valuenow={job.progress}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <i style={{ width: `${job.progress}%` }} />
      </div>
    </>
  );
}
