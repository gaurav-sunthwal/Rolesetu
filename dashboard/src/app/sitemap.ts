import type { MetadataRoute } from 'next';

import { FEATURE_PAGES, featurePath } from '@/content/marketing';
import { absoluteUrl, SITE } from '@/lib/site';

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: absoluteUrl('/'), lastModified: SITE.updated, changeFrequency: 'weekly', priority: 1 },
    ...FEATURE_PAGES.map((page) => ({
      url: absoluteUrl(featurePath(page.slug)),
      lastModified: SITE.updated,
      changeFrequency: 'monthly' as const,
      priority: 0.8,
    })),
  ];
}
