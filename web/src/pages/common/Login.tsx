// C-01 登录（ACC-02）
import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { homePath, useLogin } from '../../api/auth';
import { Brand } from '../../components/Brand';
import { Button } from '../../components/Button';
import { Notice } from '../../components/Notice';
import { PageHeading } from '../../components/PageHeading';
import { TextField } from '../../components/TextField';
import { AuthLayout } from './AuthLayout';
import styles from './Login.module.css';

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const login = useLogin();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  function submit(e: FormEvent) {
    e.preventDefault();
    login.mutate(
      { username, password },
      {
        onSuccess: ({ user }) => navigate(params.get('from') ?? homePath(user), { replace: true }),
      },
    );
  }

  return (
    <AuthLayout>
      <div className={styles.hero}>
        <Brand />
        <PageHeading title="知其然，也知其所以然。" description="连接学生和老师的 AI 学习助手" />
      </div>
      <form onSubmit={submit}>
        <TextField
          label="用户名"
          placeholder="请输入用户名"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <TextField
          label="密码"
          type="password"
          placeholder="请输入密码"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {login.error && <Notice tone="error">{login.error.message}</Notice>}
        <Button
          type="submit"
          variant="primary"
          block
          disabled={!username || !password || login.isPending}
        >
          {login.isPending ? '正在登录…' : '登录'}
        </Button>
      </form>
      <p className={styles.footer}>
        还没有账号？<Link to="/register">去注册</Link>
      </p>
    </AuthLayout>
  );
}
