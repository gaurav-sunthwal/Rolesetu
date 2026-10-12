/**
 * Talks to the Rolesetu browser extension from this page. The extension runs
 * a small script on the dashboard that listens for these messages; nothing is
 * sent anywhere else, and messages are restricted to this page's own origin.
 */

const PAGE_SOURCE = 'rolesetu-dashboard';
const EXTENSION_SOURCE = 'rolesetu-extension';
const REPLY_TIMEOUT_MS = 1500;

type Reply = { source: typeof EXTENSION_SOURCE; type: string; connected?: boolean };

function send(message: Record<string, unknown>, expect: string): Promise<Reply | null> {
  return new Promise((resolve) => {
    const finish = (reply: Reply | null) => {
      window.removeEventListener('message', onMessage);
      clearTimeout(timer);
      resolve(reply);
    };
    const onMessage = (event: MessageEvent<Reply>) => {
      if (event.source !== window || event.origin !== window.location.origin) return;
      if (event.data?.source === EXTENSION_SOURCE && event.data.type === expect) finish(event.data);
    };
    // No answer means the extension is not installed in this browser.
    const timer = setTimeout(() => finish(null), REPLY_TIMEOUT_MS);
    window.addEventListener('message', onMessage);
    window.postMessage({ source: PAGE_SOURCE, ...message }, window.location.origin);
  });
}

/** Whether the extension is installed here, and whether it already holds a key. */
export async function findExtension(): Promise<{ installed: boolean; connected: boolean }> {
  const reply = await send({ type: 'ping' }, 'present');
  return { installed: reply !== null, connected: reply?.connected === true };
}

export async function giveKeyToExtension(token: string): Promise<boolean> {
  return (await send({ type: 'connect', token }, 'connected')) !== null;
}

export async function clearExtensionKey(): Promise<void> {
  await send({ type: 'disconnect' }, 'disconnected');
}
