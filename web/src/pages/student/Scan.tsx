// S-03 拍照（SCAN-01）：拍照和相册都交给系统选图，拍照答疑进 S-04 框选，作业批改上传后进 S-05
import type { ChangeEvent } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router';
import { useCreateScan } from '../../api/scans';
import { Icon } from '../../components/Icon';
import { Notice } from '../../components/Notice';
import styles from './Scan.module.css';

const MODES = [
  { value: 'ask', label: '拍照答疑' },
  { value: 'grade', label: '作业批改' },
] as const;

export function Scan() {
  const [params, setParams] = useSearchParams();
  const { search } = useLocation();
  const navigate = useNavigate();
  const grading = params.get('mode') === 'grade';
  const createScan = useCreateScan();

  function pick(e: ChangeEvent<HTMLInputElement>) {
    const photo = e.target.files?.[0];
    // 清空后再选同一张也能触发
    e.target.value = '';
    if (!photo) return;
    if (!grading) {
      navigate(`/student/scan/crop${search}`, { state: { photo } });
      return;
    }
    // 换成进度页，批改完从结果页返回时直接回到进入拍照前的页面
    createScan.mutate(photo, {
      onSuccess: ({ scan }) => navigate(`/student/scans/${scan.id}/progress`, { replace: true }),
    });
  }

  return (
    <>
      <div className={styles.seg}>
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            aria-pressed={(m.value === 'grade') === grading}
            onClick={() => {
              params.set('mode', m.value);
              setParams(params, { replace: true });
            }}
          >
            {m.label}
          </button>
        ))}
      </div>
      <div className={styles.view}>{grading ? '把整页作业放平，对齐四角' : '对准一道题'}</div>
      {grading && createScan.error && <Notice tone="error">{createScan.error.message}</Notice>}
      {createScan.isPending ? (
        <p className={styles.uploading}>正在上传…</p>
      ) : (
        <div className={styles.bar}>
          <label className={styles.album}>
            相册
            <input type="file" accept="image/*" onChange={pick} />
          </label>
          <label className={styles.shutter} aria-label="拍摄照片">
            <Icon name="camera" />
            <input type="file" accept="image/*" capture="environment" onChange={pick} />
          </label>
          <span className={styles.album} aria-hidden="true" />
        </div>
      )}
    </>
  );
}
