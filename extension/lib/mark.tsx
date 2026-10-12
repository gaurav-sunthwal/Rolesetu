import type { CSSProperties } from 'react';

/** The Rolesetu mark: an R whose lower half is a bridge arch ("setu" means bridge). */
export function Mark({ style }: { style?: CSSProperties }) {
  return (
    <svg className="mark" viewBox="0 0 64 64" aria-hidden style={style}>
      <rect width="64" height="64" rx="15" fill="#2f5fe0" />
      <g fill="none" stroke="#fff" strokeWidth="7" strokeLinejoin="round">
        <path d="M21.5 48V19.5h12.75a8.25 8.25 0 0 1 0 16.5H21.5" />
        <path d="M21.5 48v-1.5a10.5 10.5 0 0 1 21 0V48" />
      </g>
    </svg>
  );
}
