import type { Metadata } from 'next';
import Link from 'next/link';

import { Logo } from '@/components/logo';

import { UninstallReasons } from './uninstall-reasons';

export const metadata: Metadata = {
  title: 'Sorry to see you go',
  robots: { index: false, follow: false },
};

/** Opened by the browser when the extension is removed. */
export default function Page() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center px-4 py-10">
      <Link href="/" className="mb-8">
        <Logo />
      </Link>
      <main className="bg-card w-full max-w-md rounded-2xl border p-7 shadow-xl shadow-black/5">
        <h1 className="text-2xl font-medium tracking-[-0.03em]">The extension is removed</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Your account and profile are untouched. One click tells us what to fix:
        </p>
        <UninstallReasons />
      </main>
    </div>
  );
}
