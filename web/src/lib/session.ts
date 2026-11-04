import { Preferences } from '@capacitor/preferences';

// 登录 token：Web 上 Preferences 落在 localStorage，App 里落在系统存储。
// 启动时读一次放进内存，之后同步读取。
const TOKEN_KEY = 'athena.token';
let token: string | null = null;

export async function loadToken(): Promise<void> {
  token = (await Preferences.get({ key: TOKEN_KEY })).value;
}

export function getToken(): string | null {
  return token;
}

export async function saveToken(value: string): Promise<void> {
  token = value;
  await Preferences.set({ key: TOKEN_KEY, value });
}

export async function clearToken(): Promise<void> {
  token = null;
  await Preferences.remove({ key: TOKEN_KEY });
}
