// C-02 注册（ACC-01）：选身份 → 设置账号 → 完善资料
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { homePath, useRegister } from '../../api/auth';
import { ApiError, type User } from '../../api/client';
import { Button } from '../../components/Button';
import { ChoiceChips } from '../../components/ChoiceChips';
import { Icon } from '../../components/Icon';
import { Notice } from '../../components/Notice';
import { PageHeading } from '../../components/PageHeading';
import { TextField } from '../../components/TextField';
import { GRADE_OPTIONS, SUBJECT_OPTIONS } from '../../lib/labels';
import { AuthLayout } from './AuthLayout';
import styles from './Register.module.css';

type Step = 'role' | 'account' | 'profile';
type Subject = NonNullable<User['preferred_subject']>;
type Grade = NonNullable<User['grade']>;

// 与服务端 app/schemas/auth.py 的规则一致，前端先校验是为了即时提示
function usernameError(v: string) {
  return /^[A-Za-z0-9_]{4,20}$/.test(v) ? '' : '用户名为 4～20 位字母、数字或下划线';
}
function passwordError(v: string) {
  return v.length >= 8 && v.length <= 32 && /[A-Za-z]/.test(v) && /\d/.test(v)
    ? ''
    : '密码为 8～32 位，必须同时包含字母和数字';
}

export function Register() {
  const navigate = useNavigate();
  const register = useRegister();
  const [step, setStep] = useState<Step>('role');
  const [role, setRole] = useState<User['role']>('student');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [grade, setGrade] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  // 点过“下一步”后，空着的必填项也要提示；之前只提示已经填了但不合格的
  const [tried, setTried] = useState<Record<Step, boolean>>({
    role: false,
    account: false,
    profile: false,
  });
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  const show = (s: Step, value: unknown, error: string) =>
    tried[s] || (Array.isArray(value) ? value.length > 0 : !!value) ? error : '';

  const accountErrors = {
    username: serverErrors.username || usernameError(username),
    password: passwordError(password),
    confirm: confirm === password ? '' : '两次输入的密码不一致',
  };
  const profileErrors = {
    display_name: displayName.trim() ? '' : role === 'student' ? '请填写昵称' : '请填写姓名',
    grade: role === 'student' && !grade.length ? '请选择年级' : '',
    teach_subjects: role === 'teacher' && !subjects.length ? '请选择任教学科' : '',
    teach_grades: role === 'teacher' && !grades.length ? '请选择任教年级' : '',
  };

  function chooseRole(r: User['role']) {
    setRole(r);
    setStep('account');
  }

  function nextFromAccount() {
    setTried({ ...tried, account: true });
    if (!Object.values(accountErrors).some(Boolean)) setStep('profile');
  }

  function submit() {
    setTried({ ...tried, profile: true });
    if (Object.values(profileErrors).some(Boolean)) return;
    const base = { username, password, display_name: displayName.trim() };
    const body =
      role === 'student'
        ? { ...base, role, grade: grade[0] }
        : { ...base, role, teach_subjects: subjects, teach_grades: grades };
    register.mutate(body, {
      onSuccess: ({ user }) => navigate(homePath(user), { replace: true }),
      onError: (e) => {
        // 用户名被占用时回到账号这一步，已填的内容都保留
        if (e instanceof ApiError && e.fields.username) {
          setServerErrors(e.fields);
          setStep('account');
        }
      },
    });
  }

  if (step === 'role') {
    return (
      <AuthLayout>
        <Button variant="link" onClick={() => navigate('/login')}>
          ‹ 返回登录
        </Button>
        <div className={styles.top}>
          <PageHeading title="你是学生，还是老师？" description="身份注册后不能修改" />
        </div>
        <RoleOption
          icon="book"
          title="我是学生"
          description="答疑、批改、错题复习，完成老师布置的作业"
          onClick={() => chooseRole('student')}
        />
        <RoleOption
          icon="users"
          title="我是老师"
          description="备课、组卷、布置和批改作业、查看学情"
          onClick={() => chooseRole('teacher')}
        />
      </AuthLayout>
    );
  }

  if (step === 'account') {
    return (
      <AuthLayout>
        <Button variant="link" onClick={() => setStep('role')}>
          ‹ 上一步
        </Button>
        <div className={styles.top}>
          <PageHeading title="设置账号" />
        </div>
        <TextField
          label="用户名（4～20 位字母、数字、下划线）"
          autoComplete="username"
          value={username}
          onChange={(e) => {
            setUsername(e.target.value);
            setServerErrors({});
          }}
          error={show('account', username, accountErrors.username)}
        />
        <TextField
          label="密码（8～32 位，含字母和数字）"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={show('account', password, accountErrors.password)}
        />
        <TextField
          label="确认密码"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={show('account', confirm, accountErrors.confirm)}
        />
        <Button variant="primary" block onClick={nextFromAccount}>
          下一步
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <Button variant="link" onClick={() => setStep('account')}>
        ‹ 上一步
      </Button>
      <div className={styles.top}>
        <PageHeading
          title="完善资料"
          description={role === 'student' ? '不需要手机号，也不收集真实姓名' : undefined}
        />
      </div>
      <TextField
        label={role === 'student' ? '昵称' : '姓名'}
        maxLength={20}
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        error={show('profile', displayName, profileErrors.display_name)}
      />
      {role === 'student' ? (
        <ChoiceChips
          label="年级"
          options={GRADE_OPTIONS}
          value={grade}
          onChange={setGrade}
          error={show('profile', grade, profileErrors.grade)}
        />
      ) : (
        <>
          <ChoiceChips
            label="任教学科（可多选）"
            options={SUBJECT_OPTIONS}
            value={subjects}
            onChange={setSubjects}
            multiple
            error={show('profile', subjects, profileErrors.teach_subjects)}
          />
          <ChoiceChips
            label="任教年级（可多选）"
            options={GRADE_OPTIONS}
            value={grades}
            onChange={setGrades}
            multiple
            error={show('profile', grades, profileErrors.teach_grades)}
          />
        </>
      )}
      {register.error &&
        !(register.error instanceof ApiError && register.error.fields.username) && (
          <Notice tone="error">{register.error.message}</Notice>
        )}
      <Button variant="primary" block onClick={submit} disabled={register.isPending}>
        {register.isPending ? '正在注册…' : '完成注册'}
      </Button>
    </AuthLayout>
  );
}

function RoleOption(props: {
  icon: 'book' | 'users';
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button type="button" className={styles.option} onClick={props.onClick}>
      <Icon name={props.icon} className={styles.optionIcon} />
      <span>
        <span className={styles.optionTitle}>{props.title}</span>
        <span className={styles.optionDesc}>{props.description}</span>
      </span>
      <Icon name="right" className={styles.chevron} />
    </button>
  );
}
