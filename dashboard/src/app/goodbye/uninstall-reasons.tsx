'use client';

import Link from 'next/link';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { trackSetup } from '@/lib/install-events';

const REASONS = [
  { value: 'no_account', label: 'I did not want to create an account' },
  { value: 'setup_failed', label: 'I could not get it set up' },
  { value: 'did_not_work', label: 'It did not work on the sites I use' },
  { value: 'not_job_hunting', label: 'I am not looking for a job right now' },
  { value: 'privacy', label: 'I was worried about my privacy' },
  { value: 'other', label: 'Something else' },
] as const;

export function UninstallReasons() {
  const [chosen, setChosen] = useState<string | null>(null);

  if (chosen) {
    return (
      <div className="mt-6 text-sm" role="status">
        <p className="font-medium">Thank you. That helps us make it better.</p>
        <p className="text-muted-foreground mt-2">
          Changed your mind?{' '}
          <Link href="/" className="text-primary font-medium underline-offset-4 hover:underline">
            Go back to Rolesetu
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 flex flex-col gap-2">
      {REASONS.map((reason) => (
        <Button
          key={reason.value}
          variant="outline"
          className="h-auto justify-start py-2.5 text-left whitespace-normal"
          onClick={() => {
            trackSetup('uninstall_reason', { reason: reason.value });
            setChosen(reason.value);
          }}
        >
          {reason.label}
        </Button>
      ))}
    </div>
  );
}
