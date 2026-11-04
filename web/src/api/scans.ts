import { useMutation } from '@tanstack/react-query';
import { api, unwrap } from './client';
import { uploadImage } from './files';
import type { components } from './schema';

export type Recognized = components['schemas']['RecognizeOut'];

/** SCAN-02：上传框选后的图，识别出这道题；图片留着，确认后随提问一起发出。 */
export function useRecognize() {
  return useMutation({
    mutationFn: async (image: Blob) => {
      const file = await uploadImage(image);
      const body = { image_file_id: file.id };
      return { file, ...(await unwrap(api.POST('/api/v1/recognize', { body }))) };
    },
  });
}
