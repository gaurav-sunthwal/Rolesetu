export type Settled = (() => void) & { cancel: () => void };

/**
 * Runs `task` once calls stop coming for `quietMs`, and in any case no later
 * than `atMostMs` after the first of them.
 *
 * The limit is what matters on a busy page. Job sites change something on the
 * page several times a second (timers, adverts, chat), so "wait until it goes
 * quiet" on its own can wait forever, and the task never runs.
 */
export function whenSettled(task: () => void, quietMs: number, atMostMs: number): Settled {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let deadline: number | null = null;

  const run = () => {
    timer = undefined;
    deadline = null;
    task();
  };
  const poke = () => {
    const now = Date.now();
    deadline ??= now + atMostMs;
    clearTimeout(timer);
    timer = setTimeout(run, Math.max(0, Math.min(quietMs, deadline - now)));
  };
  poke.cancel = () => {
    clearTimeout(timer);
    timer = undefined;
    deadline = null;
  };
  return poke;
}
