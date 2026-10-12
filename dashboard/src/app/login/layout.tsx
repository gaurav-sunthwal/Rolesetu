import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Log in',
  description: 'Log in to Rolesetu or create an account.',
  robots: { index: false, follow: true },
};

export default function LoginLayout({ children }: LayoutProps<'/login'>) {
  return children;
}
