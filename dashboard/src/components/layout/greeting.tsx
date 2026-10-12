'use client';

import { useAuth } from '@/lib/auth-context';

export function Greeting() {
  const { user } = useAuth();
  const firstName = user?.displayName?.trim().split(/\s+/)[0];

  return (
    <div>
      <h2 className="text-3xl leading-tight font-medium tracking-[-0.035em] sm:text-4xl">
        {firstName ? `Welcome, ${firstName}` : 'Welcome'}
      </h2>
      <p className="text-muted-foreground mt-2 text-base">Here is where your job hunt stands.</p>
    </div>
  );
}
