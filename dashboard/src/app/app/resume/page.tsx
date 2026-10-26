import type { Metadata } from 'next';

import { ResumeEditorPage } from '@/features/resume-editor/components/resume-editor-page';

export const metadata: Metadata = { title: 'Resume editor' };

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <ResumeEditorPage />;
}
