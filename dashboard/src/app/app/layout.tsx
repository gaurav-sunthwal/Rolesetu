import type { Metadata } from 'next';

import { AppSidebar } from '@/components/layout/app-sidebar';
import { AuthGuard } from '@/components/layout/auth-guard';
import { Topbar } from '@/components/layout/topbar';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { SITE_NAME } from '@/lib/site';

// Private pages: nothing here belongs in search results.
export const metadata: Metadata = {
  title: { default: 'Dashboard', template: `%s | ${SITE_NAME}` },
  robots: { index: false, follow: false },
};

export default function DashboardLayout({ children }: LayoutProps<'/app'>) {
  return (
    <AuthGuard>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <Topbar />
          {/* Resumes, profiles and emails are shown here: kept out of Clarity recordings. */}
          <main className="flex-1 px-4 pt-8 pb-12 sm:px-6" data-clarity-mask="true">
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </AuthGuard>
  );
}
