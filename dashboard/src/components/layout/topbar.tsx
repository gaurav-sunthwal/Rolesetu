'use client';

import { ScanSearch } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { NAV_ITEMS } from '@/components/layout/nav-items';
import { ThemeToggle } from '@/components/layout/theme-toggle';
import { Button } from '@/components/ui/button';
import { SidebarTrigger } from '@/components/ui/sidebar';

export function Topbar() {
  const pathname = usePathname();
  const title = NAV_ITEMS.find((item) => item.href === pathname)?.label ?? 'Rolesetu';
  const hideCta = pathname === '/app' || pathname === '/app/check';

  return (
    <header className="bg-background/85 sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-dashed px-4 backdrop-blur-lg sm:px-6">
      <SidebarTrigger className="text-muted-foreground -ml-1" />
      <h1 className="text-base font-medium tracking-tight">{title}</h1>
      <div className="ml-auto flex items-center gap-2">
        <ThemeToggle />
        {hideCta ? null : (
          <Button nativeButton={false} render={<Link href="/app/check" />}>
            <ScanSearch />
            Check a job
          </Button>
        )}
      </div>
    </header>
  );
}
