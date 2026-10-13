'use client';

import { Play } from 'lucide-react';
import Image from 'next/image';
import { useState } from 'react';

/**
 * A YouTube video that costs nothing until it is played: a still picture and a
 * play button first, and the player (and YouTube's scripts) only after a click.
 */
export function VideoPlayer({ videoId, title }: { videoId: string; title: string }) {
  const [playing, setPlaying] = useState(false);

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-2xl border bg-black shadow-2xl shadow-black/20">
      {playing ? (
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0`}
          title={title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          referrerPolicy="strict-origin-when-cross-origin"
          allowFullScreen
          className="absolute inset-0 size-full"
        />
      ) : (
        <button
          type="button"
          onClick={() => setPlaying(true)}
          className="group focus-visible:ring-ring/60 absolute inset-0 size-full outline-none focus-visible:ring-4"
        >
          <Image
            src={`https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`}
            alt=""
            fill
            sizes="(min-width: 1024px) 640px, 100vw"
            className="object-cover transition-transform duration-500 group-hover:scale-[1.02] motion-reduce:transition-none"
          />
          <span aria-hidden className="absolute inset-0 bg-black/20" />
          <span className="bg-primary text-primary-foreground absolute top-1/2 left-1/2 flex size-16 -translate-1/2 items-center justify-center rounded-full shadow-xl transition-transform group-hover:scale-110 motion-reduce:transition-none sm:size-20">
            <Play className="ml-1 size-7 fill-current" />
          </span>
          <span className="sr-only">Play video: {title}</span>
        </button>
      )}
    </div>
  );
}
