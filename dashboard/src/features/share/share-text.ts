import type { ShareCard } from '@/lib/api/types';

/** The words that go with a shared link, in the user's voice. */
export function shareText(card: Pick<ShareCard, 'score' | 'role' | 'company'>): string {
  const job = [card.role, card.company].filter(Boolean).join(' at ');
  const target = job ? ` for ${job}` : '';
  return `I checked my resume against a real job posting: ${card.score}% match${target}. Here is what matched, checked with Rolesetu:`;
}

/** Where each network's own share box opens, with the link filled in. */
export function shareTargets(url: string, text: string) {
  const link = encodeURIComponent(url);
  const words = encodeURIComponent(text);
  return [
    {
      name: 'LinkedIn',
      href: `https://www.linkedin.com/sharing/share-offsite/?url=${link}`,
    },
    { name: 'X', href: `https://x.com/intent/post?text=${words}&url=${link}` },
    { name: 'WhatsApp', href: `https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}` },
    { name: 'Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${link}` },
  ];
}
