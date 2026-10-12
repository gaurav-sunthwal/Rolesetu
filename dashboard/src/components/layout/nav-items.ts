import { Briefcase, LayoutDashboard, ScanSearch, Settings, User } from 'lucide-react';

export const NAV_ITEMS = [
  { label: 'Overview', href: '/app', icon: LayoutDashboard },
  { label: 'Check a job', href: '/app/check', icon: ScanSearch },
  { label: 'Applications', href: '/app/applications', icon: Briefcase },
  { label: 'Profile', href: '/app/profile', icon: User },
  { label: 'Settings', href: '/app/settings', icon: Settings },
] as const;
