import type { NextConfig } from 'next';
import { z } from 'zod';

// Where the API really runs (Render today). The extension, dashboard and admin
// panel only know this site's /api address, so moving the API to another host
// means changing BACKEND_ORIGIN in Vercel and redeploying: no extension release.
const backendOrigin = z
  .url()
  .optional()
  .parse(process.env.BACKEND_ORIGIN || undefined)
  ?.replace(/\/$/, '');

if (!backendOrigin && process.env.VERCEL_ENV === 'production') {
  throw new Error('BACKEND_ORIGIN must be set for production builds');
}

const nextConfig: NextConfig = {
  async rewrites() {
    if (!backendOrigin) return [];
    return {
      beforeFiles: [{ source: '/api/:path*', destination: `${backendOrigin}/api/:path*` }],
      afterFiles: [],
      fallback: [],
    };
  },
  cacheComponents: true,
  partialPrefetching: true,
  // The still picture shown before a YouTube video is played.
  images: { remotePatterns: [{ protocol: 'https', hostname: 'i.ytimg.com', pathname: '/vi/**' }] },
  turbopack: {
    rules: {
      '*.css': {
        loaders: ['@tailwindcss/turbopack'],
        as: '*.css',
      },
    },
  },
};

export default nextConfig;
