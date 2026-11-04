import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { clearToken, getToken, saveToken } from '../lib/session';
import { api, unwrap, type User } from './client';
import type { components } from './schema';

export type RegisterBody =
  components['schemas']['StudentRegister'] | components['schemas']['TeacherRegister'];
type LoginBody = components['schemas']['LoginIn'];

export const ME_KEY = ['me'];

export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: () => unwrap(api.GET('/api/v1/me')),
    enabled: getToken() !== null,
    staleTime: Infinity,
  });
}

function useSignIn<B>(request: (body: B) => Promise<{ token: string; user: User }>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: async ({ token, user }) => {
      await saveToken(token);
      queryClient.setQueryData(ME_KEY, user);
    },
  });
}

export const useLogin = () =>
  useSignIn((body: LoginBody) => unwrap(api.POST('/api/v1/auth/login', { body })));

export const useRegister = () =>
  useSignIn((body: RegisterBody) => unwrap(api.POST('/api/v1/auth/register', { body })));

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/auth/logout')),
    onSettled: async () => {
      await clearToken();
      queryClient.clear();
    },
  });
}

export function homePath(user: User): string {
  return user.role === 'student' ? '/student' : '/teacher';
}
