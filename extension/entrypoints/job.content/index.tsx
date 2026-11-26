import { createRoot, type Root } from 'react-dom/client';

import { ALL_SITES } from '@/lib/config';

import { followModalDialogs } from '@/lib/top-layer';
import { watchErrors } from '@/lib/analytics';

import { App } from './App';
import { STYLES } from './styles';

declare global {
  interface Window {
    __rolesetuMounted?: boolean;
    __rolesetuManual?: boolean;
    // The user pressed "Fill a form on this page" in the popup.
    __rolesetuFill?: boolean;
  }
}

/**
 * Shows the match score and the autofill offer. It is never loaded by the
 * browser on its own: the background worker injects it once the detector has
 * found a job or an application form, or when the user presses "Check this
 * page" in the popup.
 */
export default defineContentScript({
  matches: ALL_SITES,
  registration: 'runtime',
  cssInjectionMode: 'manual',
  async main(ctx) {
    if (window.__rolesetuMounted) {
      // Already on the page: the popup asked again, so just do what it asked.
      const fill = window.__rolesetuFill === true;
      window.__rolesetuFill = false;
      window.dispatchEvent(new Event(fill ? 'rolesetu:fill' : 'rolesetu:open'));
      return;
    }
    window.__rolesetuMounted = true;
    // Only failures in our own code: the page's errors are none of our business.
    watchErrors('content', window);
    const manual = window.__rolesetuManual === true;

    const ui = await createShadowRootUi<Root>(ctx, {
      name: 'rolesetu-root',
      position: 'inline',
      anchor: 'body',
      onMount(container, shadow) {
        const style = document.createElement('style');
        style.textContent = STYLES;
        shadow.append(style);
        const root = createRoot(container);
        root.render(<App ctx={ctx} manual={manual} />);
        return root;
      },
      onRemove(root) {
        stopFollowing?.();
        root?.unmount();
        window.__rolesetuMounted = false;
      },
    });
    ui.mount();
    // A modal application form (a <dialog>) would hide the panel and its buttons:
    // while one is open, the panel lives inside it.
    const stopFollowing = followModalDialogs(ui.shadowHost, document.body);
  },
});
