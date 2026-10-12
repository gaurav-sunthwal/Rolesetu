/**
 * Styles for the badge and panel. They live in a shadow root, so the host
 * page's CSS cannot reach them and theirs cannot leak out. Kept as a string
 * (not a .css file) so the script also works when injected on demand into a
 * site that is not on the built-in list.
 */
export const STYLES = `
:host { all: initial; }
* { box-sizing: border-box; }
.aa {
  --bg: #ffffff; --fg: #14151a; --muted: #6b6f7b; --line: #e6e7ec; --soft: #f4f4f7;
  --brand: #2f5fe0; --good: #1f9d55; --warn: #d98a00; --bad: #d64545;
  font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  color: var(--fg);
}
@media (prefers-color-scheme: dark) {
  .aa { --bg: #17181d; --fg: #f1f1f4; --muted: #a0a3ad; --line: #2b2d36; --soft: #22242c; }
}
button { font: inherit; color: inherit; cursor: pointer; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }

.badge {
  position: fixed; right: 20px; bottom: 20px; z-index: 2147483646;
  display: flex; align-items: center; gap: 10px; height: 48px; padding: 0 16px 0 8px;
  background: var(--bg); border: 1px solid var(--line); border-radius: 999px;
  box-shadow: 0 8px 28px rgba(15, 20, 40, .18);
}
.badge:hover { box-shadow: 0 10px 34px rgba(15, 20, 40, .26); }
.badge .label { font-weight: 600; white-space: nowrap; }
.badge .sub { color: var(--muted); font-size: 12px; }
.ring { position: relative; width: 34px; height: 34px; flex: none; }
.ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.ring span { position: absolute; inset: 0; display: grid; place-items: center; font-size: 12px; font-weight: 700; }
.ring.big { width: 84px; height: 84px; }
.ring.big span { font-size: 26px; }
.dot { width: 22px; height: 22px; border-radius: 50%; background: var(--brand); color: #fff;
  display: grid; place-items: center; font-weight: 700; font-size: 12px; flex: none; margin-left: 4px; }
.spin { width: 18px; height: 18px; border-radius: 50%; border: 2px solid var(--line);
  border-top-color: var(--brand); animation: aa-spin .8s linear infinite; margin-left: 6px; }
@keyframes aa-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }

.panel {
  position: fixed; top: 16px; right: 16px; bottom: 16px; z-index: 2147483647;
  width: min(400px, calc(100vw - 32px)); display: flex; flex-direction: column;
  background: var(--bg); border: 1px solid var(--line); border-radius: 20px;
  box-shadow: 0 24px 70px rgba(15, 20, 40, .32); overflow: hidden;
}
.head { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--line); }
.head strong { flex: 1; font-size: 15px; }
.icon { width: 32px; height: 32px; border: 0; border-radius: 50%; background: transparent;
  display: grid; place-items: center; font-size: 18px; color: var(--muted); }
.icon:hover { background: var(--soft); color: var(--fg); }
.body { flex: 1; overflow-y: auto; padding: 16px; }
.summary { display: flex; align-items: center; gap: 14px; }
.summary h2 { margin: 2px 0 0; font-size: 16px; line-height: 1.3; }
.band { font-size: 12px; font-weight: 600; }
.muted { color: var(--muted); }
.small { font-size: 12px; }
.note { margin: 14px 0 0; padding: 10px 12px; border-radius: 12px; background: var(--soft); font-size: 13px;
  border-left: 4px solid var(--muted); }
.note strong { display: block; }
.note p { margin: 6px 0 0; }
.note .facts { display: flex; gap: 16px; margin-top: 4px; }
.note.meets, .note.open_to_freshers { border-left-color: var(--good); }
.note.short { border-left-color: var(--warn); }
.note.well_short { border-left-color: var(--bad); }
.note.well_short strong { color: var(--bad); }
h3 { margin: 20px 0 6px; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
ul { list-style: none; margin: 0; padding: 0; }
.skill { display: flex; align-items: flex-start; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--line); }
.skill:last-child { border-bottom: 0; }
.skill div { flex: 1; min-width: 0; }
.skill p { margin: 0; }
.skill .name { font-weight: 600; }
.verdict { display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px; border-radius: 999px;
  background: var(--soft); font-size: 12px; font-weight: 600; white-space: nowrap; }
.verdict i { width: 6px; height: 6px; border-radius: 50%; }
.gaps { display: flex; flex-wrap: wrap; gap: 6px; }
.hint { margin: 0 0 8px; }
.group { margin: 12px 0 6px; font-size: 12px; font-weight: 600; color: var(--muted); }
.retitle { display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; }
.retitle label { display: flex; align-items: flex-start; gap: 8px; font-size: 13px; cursor: pointer; }
.retitle input[type="checkbox"] { margin: 2px 0 0; accent-color: var(--brand); }
.retitle input[type="text"] { width: 100%; height: 34px; padding: 0 10px; font: inherit; color: var(--fg);
  background: var(--bg); border: 1px solid var(--line); border-radius: 8px; }
.retitle input[type="text"]:disabled { opacity: .55; }
.chip { padding: 5px 11px; border-radius: 999px; border: 1px solid transparent; background: var(--soft);
  font-size: 13px; font-weight: 500; }
.chip:hover { border-color: var(--line); }
.chip.on { background: var(--brand); color: #fff; }
.btn.wide { display: block; width: 100%; flex: none; margin-top: 12px; }
.problem { margin: 10px 0 0; color: var(--bad); font-size: 13px; }
.tailored { position: relative; margin-top: 14px; padding: 14px; border: 1px solid var(--line);
  border-radius: 16px; background: var(--soft); }
.tailored .close { position: absolute; top: 6px; right: 6px; }
.tailored strong { display: block; padding-right: 28px; }
.tailored p { margin: 8px 0 0; }
.added { margin-top: 6px; font-size: 13px; }
.saved { color: var(--good); font-weight: 600; font-size: 13px; }
.confirm { margin-top: 12px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--bg); }
.confirm p { margin: 0; }
.confirm .row { display: flex; gap: 8px; margin-top: 10px; }
.confirm .btn { height: 36px; }
.added li { padding: 2px 0; }
.preview { display: block; width: 100%; margin-top: 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.foot { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--line); }
.btn { flex: 1; height: 40px; border-radius: 999px; border: 1px solid var(--line); background: var(--bg); font-weight: 600; }
.btn:hover { background: var(--soft); }
.btn.primary { background: var(--brand); border-color: var(--brand); color: #fff; }
.btn.primary:hover { filter: brightness(1.08); background: var(--brand); }
.btn:active:not(:disabled), .chip:active { transform: scale(.97); }
.btn:disabled { opacity: .6; cursor: default; }
.btn .spin { display: inline-block; width: 14px; height: 14px; margin: 0 8px 0 0; vertical-align: -2px; }
.btn.primary .spin { border-color: rgba(255, 255, 255, .4); border-top-color: #fff; }
@media (prefers-reduced-motion: reduce) { .btn:active:not(:disabled), .chip:active { transform: none; } }
.notice {
  position: fixed; right: 20px; bottom: 84px; z-index: 2147483647;
  width: min(340px, calc(100vw - 40px)); display: flex; flex-direction: column; gap: 6px;
  padding: 14px 40px 14px 16px; background: var(--bg); border: 1px solid var(--line);
  border-radius: 16px; box-shadow: 0 16px 48px rgba(15, 20, 40, .28);
}
.notice .row { display: flex; gap: 8px; margin-top: 6px; }
.notice .btn { height: 36px; }
.notice .close { position: absolute; top: 6px; right: 6px; }
/* Opposite corner from the score, so the two never overlap. */
.notice.autofill { right: auto; left: 20px; bottom: 20px; }
.center { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 10px; padding: 36px 12px; }
.center .spin { width: 28px; height: 28px; border-width: 3px; margin: 0; }
`;
