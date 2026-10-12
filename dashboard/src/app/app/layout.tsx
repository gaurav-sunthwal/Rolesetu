import { AppSidebar } from '@/components/layout/app-sidebar';
import { AuthGuard } from '@/components/layout/auth-guard';
import { Topbar } from '@/components/layout/topbar';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';

export default function DashboardLayout({ children }: LayoutProps<'/app'>) {
  return (
    <AuthGuard>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <Topbar />
          <main className="flex-1 px-4 pt-8 pb-12 sm:px-6">{children}</main>
        </SidebarInset>
      </SidebarProvider>
    </AuthGuard>
  );
}
