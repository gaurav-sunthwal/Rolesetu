import type { MetadataRoute } from 'next';

import { SITE } from '@/lib/site';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE.title,
    short_name: SITE.name,
    description: SITE.description,
    start_url: '/',
    display: 'standalone',
    background_color: '#ffffff',
    theme_color: '#2f5fe0',
    categories: ['business', 'productivity'],
    icons: [
      { src: '/icon.png', sizes: 'any', type: 'image/png' },
      { src: '/apple-icon.png', sizes: '180x180', type: 'image/png' },
    ],
  };
}
