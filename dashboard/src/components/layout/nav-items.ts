import {
  Briefcase,
  Crown,
  FilePenLine,
  LayoutDashboard,
  Newspaper,
  ScanSearch,
  Settings,
  User,
} from 'lucide-react';

export const NAV_ITEMS = [
  { label: 'Overview', href: '/app', icon: LayoutDashboard },
  { label: 'Check a job', href: '/app/check', icon: ScanSearch },
  { label: 'Fresh jobs', href: '/app/jobs', icon: Newspaper },
  { label: 'Applications', href: '/app/applications', icon: Briefcase },
  { label: 'Resume editor', href: '/app/resume', icon: FilePenLine },
  { label: 'Profile', href: '/app/profile', icon: User },
  { label: 'Plan & invites', href: '/app/plan', icon: Crown },
  { label: 'Settings', href: '/app/settings', icon: Settings },
] as const;
