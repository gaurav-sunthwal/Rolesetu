'use client';

import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Toaster } from 'sonner';

import { ThemeProvider } from '@/components/theme-provider';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ApiError } from '@/lib/api/client';
import { AuthProvider, useAuth } from '@/lib/auth-context';

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // A 4xx will not fix itself; only retry network and server failures.
        retry: (failureCount, error) => {
          const status = error instanceof ApiError ? error.status : null;
          if (status !== null && status < 500) return false;
          return failureCount < 2;
        },
      },
    },
  });
}

/** Drops cached data when the signed-in account changes, so one user never sees another's. */
function ClearCacheOnAccountChange() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const uid = user?.uid ?? null;
  const previous = useRef(uid);

  useEffect(() => {
    if (previous.current !== uid) {
      previous.current = uid;
      queryClient.clear();
    }
  }, [uid, queryClient]);

  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(createQueryClient);

  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ClearCacheOnAccountChange />
          <TooltipProvider>
            {children}
            <Toaster richColors position="top-right" />
          </TooltipProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
