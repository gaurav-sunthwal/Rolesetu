import { createRoot, type Root } from 'react-dom/client';

import { ALL_SITES } from '@/lib/config';

import { App } from './App';
import { STYLES } from './styles';

declare global {
  interface Window {
    __rolesetuMounted?: boolean;
    __rolesetuManual?: boolean;
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
      // Already on the page: the popup asked again, so just open the panel.
      window.dispatchEvent(new Event('rolesetu:open'));
      return;
    }
    window.__rolesetuMounted = true;
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
        root?.unmount();
        window.__rolesetuMounted = false;
      },
    });
    ui.mount();
  },
});
