'use client';

import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';

import { button } from '@/components/ui';
import { apiFile, errorMessage } from '@/lib/api';

// Set here, in the module that draws the PDF, so react-pdf's default cannot override it.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const ZOOMS = [0.75, 1, 1.25, 1.5, 2];
const MAX_PAGE_WIDTH = 820;

/** Width available for a page, followed as the window resizes. */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

/**
 * A user's resume PDF, drawn in the page. Fetched only when an admin opens it
 * (the API records each opening) and never kept after the viewer closes.
 */
export default function ResumeViewer({
  userId,
  resumeId,
  filename,
}: {
  userId: string;
  resumeId: string;
  filename: string;
}) {
  const file = useQuery({
    queryKey: ['admin', 'user', userId, 'resume-file', resumeId],
    queryFn: () => apiFile(`/admin/users/${userId}/resumes/${resumeId}/file`),
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });
  const [pages, setPages] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [renderError, setRenderError] = useState<string | null>(null);
  const { ref, width } = useWidth();
  const pageWidth = Math.min(width, MAX_PAGE_WIDTH) * zoom;

  function download() {
    if (!file.data) return;
    const url = URL.createObjectURL(file.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  const zoomIndex = ZOOMS.indexOf(zoom);

  return (
    <div className="bg-zinc-100">
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 bg-white px-4 py-2 text-sm">
        <span className="text-zinc-500">
          {pages > 0 ? `${pages} ${pages === 1 ? 'page' : 'pages'}` : 'Loading…'}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setZoom(ZOOMS[zoomIndex - 1])}
            disabled={zoomIndex <= 0}
            className={button}
            aria-label="Zoom out"
          >
            −
          </button>
          <span className="w-12 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
          <button
            onClick={() => setZoom(ZOOMS[zoomIndex + 1])}
            disabled={zoomIndex >= ZOOMS.length - 1}
            className={button}
            aria-label="Zoom in"
          >
            +
          </button>
          <button onClick={download} disabled={!file.data} className={button}>
            Download
          </button>
        </div>
      </div>

      <div ref={ref} className="max-h-[calc(100dvh-10rem)] overflow-auto p-4">
        {file.isPending ? (
          <div
            role="status"
            aria-label="Loading resume"
            className="mx-auto aspect-[1/1.414] w-full max-w-[820px] animate-pulse rounded bg-white motion-reduce:animate-none"
          />
        ) : file.isError ? (
          <p role="alert" className="py-10 text-center text-sm text-red-700">
            The resume could not be opened. {errorMessage(file.error)}
          </p>
        ) : renderError ? (
          <p role="alert" className="py-10 text-center text-sm text-red-700">
            {renderError} Use Download to open it in another app.
          </p>
        ) : (
          <Document
            file={file.data}
            onLoadSuccess={({ numPages }) => setPages(numPages)}
            onLoadError={() => setRenderError('This PDF could not be drawn here.')}
            loading={null}
            className="flex flex-col items-center gap-4"
          >
            {width > 0 &&
              Array.from({ length: pages }, (_, index) => (
                <Page
                  key={index}
                  pageNumber={index + 1}
                  width={pageWidth}
                  className="shadow-sm"
                  loading={null}
                />
              ))}
          </Document>
        )}
      </div>
    </div>
  );
}
