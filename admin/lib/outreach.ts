import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type { EmailDefaults } from '@/lib/types';

/** The suggested email to people without the extension, and how many it would reach. */
export function useEmailDefaults() {
  return useQuery({
    queryKey: ['admin', 'email-defaults'],
    queryFn: () => api<EmailDefaults>('/admin/emails/extension-nudge'),
  });
}
