'use client';

import dynamic from 'next/dynamic';
import { useEffect, useRef } from 'react';

import { button } from '@/components/ui';

// The PDF library only runs in the browser and is large, so it loads when a resume is opened.
const ResumeViewer = dynamic(() => import('@/components/ResumeViewer'), { ssr: false });

/**
 * A popup over the page showing one resume. Built on the browser's own
 * <dialog>, which keeps keyboard focus inside and closes on Escape.
 */
export function ResumeModal({
  userId,
  resume,
  onClose,
}: {
  userId: string;
  resume: { id: string; filename: string };
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  // Opened once it is on the page. It is not closed on unmount: closing fires
  // the dialog's close event, which would tell the page to close it again (and
  // in development React mounts twice, so it would vanish at once). Removing an
  // open dialog from the page closes it anyway.
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      // A click on the dimmed area outside the box closes it.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      aria-labelledby="resume-modal-title"
      className="m-auto w-[min(960px,calc(100vw-2rem))] overflow-hidden rounded-xl bg-white p-0 shadow-2xl backdrop:bg-zinc-950/60"
    >
      <div className="flex items-center gap-3 border-b border-zinc-200 px-4 py-3">
        <h2 id="resume-modal-title" className="min-w-0 flex-1 truncate font-bold">
          {resume.filename}
        </h2>
        <button onClick={onClose} className={button} autoFocus>
          Close
        </button>
      </div>
      <ResumeViewer userId={userId} resumeId={resume.id} filename={resume.filename} />
    </dialog>
  );
}
