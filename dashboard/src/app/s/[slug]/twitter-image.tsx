import { CARD_SIZE, renderCardImage } from '@/features/share/card-image';

// Its own file so the site-wide picture is not used for shared scores on X.
export const alt = 'A shared Rolesetu match score';
export const size = CARD_SIZE;
export const contentType = 'image/png';

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return renderCardImage(slug);
}
