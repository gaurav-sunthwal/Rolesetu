import { defineConfig } from 'vitest/config';

// Only the parts with no browser in them are tested here: turning failures
// into messages, fitting requests to the server's limits, and the score sum.
export default defineConfig({ test: { include: ['tests/**/*.test.ts'], environment: 'node' } });
