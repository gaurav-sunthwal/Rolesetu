import { useMutation } from '@tanstack/react-query';

import { collectExport } from '@/features/settings/api';

export function useExportData() {
  return useMutation({ mutationFn: collectExport });
}
