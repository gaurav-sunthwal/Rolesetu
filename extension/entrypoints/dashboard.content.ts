import { DASHBOARD_MATCHES } from '@/lib/config';
import { EXTENSION_SOURCE, PAGE_SOURCE } from '@/lib/messages';
import { accessKey } from '@/lib/storage';

type PageMessage =
  | { source: typeof PAGE_SOURCE; type: 'ping' }
  | { source: typeof PAGE_SOURCE; type: 'connect'; token: string }
  | { source: typeof PAGE_SOURCE; type: 'disconnect' };

/**
 * Runs only on the Rolesetu dashboard. It is how the dashboard hands this
 * browser its key: the page posts a message, this script stores the key and
 * answers. Messages from any other origin or frame are ignored.
 */
export default defineContentScript({
  matches: DASHBOARD_MATCHES,
  main() {
    const reply = (type: string, extra: Record<string, unknown> = {}) =>
      window.postMessage({ source: EXTENSION_SOURCE, type, ...extra }, window.location.origin);

    window.addEventListener('message', (event: MessageEvent<PageMessage>) => {
      if (event.source !== window || event.origin !== window.location.origin) return;
      const message = event.data;
      if (!message || message.source !== PAGE_SOURCE) return;

      void (async () => {
        if (message.type === 'connect' && typeof message.token === 'string') {
          await accessKey.setValue(message.token);
          reply('connected');
        } else if (message.type === 'disconnect') {
          await accessKey.setValue(null);
          reply('disconnected');
        } else if (message.type === 'ping') {
          reply('present', { connected: (await accessKey.getValue()) !== null });
        }
      })();
    });

    // Announce on load too, in case the page asked before this script was ready.
    void accessKey.getValue().then((key) => reply('present', { connected: key !== null }));
  },
});
