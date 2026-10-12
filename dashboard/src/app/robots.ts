import type { MetadataRoute } from 'next';

import { SITE } from '@/lib/site';

// The signed-in app holds private data and has nothing for a search engine.
const PRIVATE = ['/app', '/login'];

// Crawlers that feed AI assistants and AI search. They follow the same rules as
// everyone else; naming them makes it explicit that the public pages are theirs to read.
const AI_CRAWLERS = [
  'GPTBot',
  'OAI-SearchBot',
  'ChatGPT-User',
  'ClaudeBot',
  'Claude-SearchBot',
  'Claude-User',
  'PerplexityBot',
  'Perplexity-User',
  'Google-Extended',
  'Applebot-Extended',
  'CCBot',
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: '*', allow: '/', disallow: PRIVATE },
      { userAgent: AI_CRAWLERS, allow: '/', disallow: PRIVATE },
    ],
    sitemap: `${SITE.url}/sitemap.xml`,
    host: SITE.url,
  };
}
