'use client';

import { signOut } from 'firebase/auth';
import { ChevronsUpDown, LogOut, Settings, User } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuth } from '@/lib/auth-context';
import { firebaseAuth } from '@/lib/firebase';

function initialsOf(name: string) {
  const parts = name
    .trim()
    .split(/[\s@._-]+/)
    .filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '?';
}

export function UserMenu() {
  const router = useRouter();
  const { user } = useAuth();
  const email = user?.email ?? '';
  const name = user?.displayName || email.split('@')[0] || 'Your account';

  async function handleSignOut() {
    try {
      await signOut(firebaseAuth);
      router.replace('/');
    } catch {
      toast.error('Could not sign out. Please try again.');
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className="hover:bg-sidebar-accent focus-visible:ring-ring/50 flex w-full items-center gap-3 rounded-lg p-2 text-left transition-colors outline-none group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0 focus-visible:ring-3"
      >
        <Avatar className="size-9">
          {user?.photoURL ? <AvatarImage src={user.photoURL} alt="" /> : null}
          <AvatarFallback className="bg-foreground text-background text-xs font-medium">
            {initialsOf(user?.displayName || email)}
          </AvatarFallback>
        </Avatar>
        <span className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
          <span className="block truncate text-sm font-medium">{name}</span>
          <span className="text-muted-foreground block truncate text-xs">{email}</span>
        </span>
        <ChevronsUpDown className="text-muted-foreground size-4 shrink-0 group-data-[collapsible=icon]:hidden" />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-56">
        <DropdownMenuItem render={<Link href="/app/profile" />}>
          <User />
          Profile
        </DropdownMenuItem>
        <DropdownMenuItem render={<Link href="/app/settings" />}>
          <Settings />
          Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={handleSignOut}>
          <LogOut />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
