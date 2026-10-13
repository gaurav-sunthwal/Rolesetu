'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '@/lib/api';

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // A 4xx will not fix itself; only retry network and server failures.
            retry: (failures, error) => {
              const status = error instanceof ApiError ? error.status : null;
              return (status === null || status >= 500) && failures < 2;
            },
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
