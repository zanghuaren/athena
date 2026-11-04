import { api, unwrap } from './client';
import type { components } from './schema';

export type FileOut = components['schemas']['FileOut'];

/** 返回里的 url 是相对地址，Android App 里要拼上服务器地址（接口约定 2.3）。 */
export function fileUrl(file: FileOut): string {
  return `${import.meta.env.VITE_API_BASE ?? ''}${file.url}`;
}

export function uploadImage(image: Blob): Promise<FileOut> {
  const form = new FormData();
  form.append('file', image, 'photo.jpg');
  return unwrap(
    // 生成的类型把文件字段写成 string，实际发的是 FormData
    api.POST('/api/v1/files', { body: form as never, bodySerializer: () => form }),
  );
}
