/**
 * Keeps Rolesetu's UI usable when a page opens a modal <dialog> (EPAM's
 * application form is one). The browser draws a modal dialog in its "top layer",
 * above every z-index, and makes everything outside it inert: our card would be
 * hidden behind it and its buttons would not react. So while a modal dialog is
 * open, our container is moved inside it, and back to where it was when it closes.
 *
 * The dialogs are only looked for when the page changes, at most once a frame,
 * so a page that changes often costs one cheap query per frame.
 */
export function followModalDialogs(host: HTMLElement, home: ParentNode): () => void {
  let scheduled = false;

  const place = () => {
    scheduled = false;
    // The newest open modal dialog is the one in front.
    const dialogs = [...document.querySelectorAll('dialog')].filter((dialog) =>
      dialog.matches(':modal'),
    );
    const target = dialogs[dialogs.length - 1] ?? home;
    if (host.parentNode !== target) target.append(host);
  };

  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(place);
  };

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['open'],
  });
  place();

  return () => {
    observer.disconnect();
    if (host.isConnected && host.parentNode !== home) home.append(host);
  };
}
