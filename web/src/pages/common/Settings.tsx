// C-06 设置（ME-03 主题；ME-02 讲解偏好、ME-04 修改密码随 ME 模块补上）
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useLogout } from '../../api/auth';
import { Button } from '../../components/Button';
import { getReduceMotion, getTheme, setReduceMotion, setTheme, type Theme } from '../../lib/theme';
import fieldStyles from '../../components/Field.module.css';
import styles from './Settings.module.css';

export function Settings() {
  const [theme, setThemeState] = useState(getTheme);
  const [reduceMotion, setReduceMotionState] = useState(getReduceMotion);
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <>
      <h3 className={styles.h}>阅读外观</h3>
      <label className={fieldStyles.label} htmlFor="theme">
        主题
      </label>
      <select
        id="theme"
        className={fieldStyles.input}
        value={theme}
        onChange={(e) => {
          const value = e.target.value as Theme;
          setTheme(value);
          setThemeState(value);
        }}
      >
        <option value="light">纸感书房</option>
        <option value="dark">夜间自习</option>
        <option value="system">跟随系统</option>
      </select>
      <label className={styles.row}>
        <span>减少动态效果</span>
        <input
          type="checkbox"
          checked={reduceMotion}
          onChange={(e) => {
            setReduceMotion(e.target.checked);
            setReduceMotionState(e.target.checked);
          }}
        />
      </label>
      <Button
        block
        disabled={logout.isPending}
        onClick={() =>
          logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) })
        }
      >
        退出登录
      </Button>
    </>
  );
}
