'use client';

import { getApp, getApps, initializeApp } from 'firebase/app';
import { browserSessionPersistence, getAuth, setPersistence } from 'firebase/auth';
import { z } from 'zod';

const env = z
  .object({
    apiKey: z.string().min(1),
    authDomain: z.string().min(1),
    projectId: z.string().min(1),
    appId: z.string().min(1),
  })
  .parse({
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  });

export const firebaseAuth = getAuth(getApps().length ? getApp() : initializeApp(env));

// An admin stays signed in for this browser tab only: closing it signs them out.
void setPersistence(firebaseAuth, browserSessionPersistence);
