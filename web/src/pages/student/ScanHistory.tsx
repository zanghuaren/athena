// S-07 批改记录（SCAN-04）：按时间倒序，批改中和失败的进 S-05，完成的进 S-06
import { Link, useNavigate } from 'react-router';
import { useScans, type Scan } from '../../api/scans';
import { Button } from '../../components/Button';
import { Notice } from '../../components/Notice';
import { SUBJECT_LABELS } from '../../lib/labels';
import { formatTime } from '../../lib/time';
import styles from './ScanHistory.module.css';

const FAIL_LABELS = { unclear: '照片不清楚', no_question: '没有识别到题目', error: '批改失败' };

export function ScanHistory() {
  const list = useScans();
  const navigate = useNavigate();
  if (list.error) return <Notice tone="error">{list.error.message}</Notice>;
  if (!list.data) return null;
  if (list.data.items.length === 0) {
    return (
      <div className={styles.empty}>
        <p>还没有批改记录</p>
        <Button block onClick={() => navigate('/student/scan?mode=grade')}>
          拍一份作业试试
        </Button>
      </div>
    );
  }
  return list.data.items.map((scan) => (
    <Link
      key={scan.id}
      to={`/student/scans/${scan.id}${scan.status === 'done' ? '' : '/progress'}`}
      className={styles.row}
    >
      <b>
        {formatTime(scan.created_at)} · {scan.subject ? SUBJECT_LABELS[scan.subject] : '作业'}
      </b>
      <span>{summary(scan)}</span>
    </Link>
  ));
}

function summary(scan: Scan): string {
  if (scan.status === 'processing') return '正在批改…';
  if (scan.status === 'failed') return FAIL_LABELS[scan.fail_reason ?? 'error'];
  const { total, correct, unknown } = scan;
  if (correct === total) return `${total} 题 · 全对`;
  const parts = [`${total} 题`, `对 ${correct}`, `错 ${total - correct - unknown}`];
  if (unknown) parts.push(`待确认 ${unknown}`);
  return parts.join(' · ');
}
