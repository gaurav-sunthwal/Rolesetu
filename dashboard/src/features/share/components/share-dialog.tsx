'use client';

import { Check, Copy, Link2Off, Share2 } from 'lucide-react';
import { useId, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { shareUrl, useShareMatch, useStopSharing } from '@/features/share/api';
import { shareTargets, shareText } from '@/features/share/share-text';
import { errorMessage } from '@/lib/api/client';
import type { Match, ShareCard } from '@/lib/api/types';

export function ShareDialog({
  match,
  open,
  onOpenChange,
}: {
  match: Match;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const gapsId = useId();
  const [showGaps, setShowGaps] = useState(false);
  const [card, setCard] = useState<ShareCard | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmingStop, setConfirmingStop] = useState(false);
  const share = useShareMatch(match.id);
  const stop = useStopSharing();
  const url = card ? shareUrl(card.slug) : null;

  function createLink(withGaps: boolean) {
    share.mutate({ show_gaps: withGaps }, { onSuccess: setCard });
  }

  function toggleGaps(next: boolean) {
    setShowGaps(next);
    // Once the link exists, the public card follows the choice straight away.
    if (card) createLink(next);
  }

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Could not copy. Select the link and copy it yourself.');
    }
  }

  async function shareNatively() {
    if (!url || !card) return;
    try {
      await navigator.share({ url, text: shareText(card) });
    } catch {
      // Closing the share sheet is not an error worth showing.
    }
  }

  function stopSharing() {
    if (!card) return;
    stop.mutate(card.slug, {
      onSuccess: () => {
        setCard(null);
        setConfirmingStop(false);
        toast.success('Link removed. Anyone opening it now sees that it was taken down.');
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  }

  const canShareNatively = typeof navigator !== 'undefined' && 'share' in navigator;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-3xl p-6 sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Share your score</DialogTitle>
          <DialogDescription>
            Anyone with the link sees the job, your score and the skills you matched. Your resume
            and name are never shown.
          </DialogDescription>
        </DialogHeader>

        <label htmlFor={gapsId} className="flex cursor-pointer items-start gap-3 text-sm">
          <input
            id={gapsId}
            type="checkbox"
            className="accent-foreground mt-0.5 size-4"
            checked={showGaps}
            disabled={share.isPending}
            onChange={(event) => toggleGaps(event.target.checked)}
          />
          <span>
            Also show the skills I&apos;m missing
            <span className="text-muted-foreground block text-xs">
              Honest cards get more replies, but it is your call.
            </span>
          </span>
        </label>

        {share.isError ? (
          <p role="alert" className="text-destructive text-sm">
            {errorMessage(share.error)}
          </p>
        ) : null}

        {!card || !url ? (
          <Button onClick={() => createLink(showGaps)} disabled={share.isPending}>
            <Share2 />
            {share.isPending ? 'Creating link…' : 'Create share link'}
          </Button>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex gap-2">
              <Input
                readOnly
                value={url}
                aria-label="Share link"
                onFocus={(e) => e.target.select()}
              />
              <Button variant="outline" onClick={copy} aria-label="Copy link">
                {copied ? <Check /> : <Copy />}
                {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {shareTargets(url, shareText(card)).map((target) => (
                <Button
                  key={target.name}
                  variant="secondary"
                  size="sm"
                  render={<a href={target.href} target="_blank" rel="noreferrer" />}
                  nativeButton={false}
                >
                  {target.name}
                </Button>
              ))}
              {canShareNatively ? (
                <Button variant="secondary" size="sm" onClick={shareNatively}>
                  More…
                </Button>
              ) : null}
            </div>
            {confirmingStop ? (
              <div className="bg-muted flex flex-wrap items-center gap-2 rounded-2xl p-3 text-sm">
                <span className="flex-1">Take this link down? It stops working for everyone.</span>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={stopSharing}
                  disabled={stop.isPending}
                >
                  {stop.isPending ? 'Removing…' : 'Take down'}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirmingStop(false)}>
                  Keep
                </Button>
              </div>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                className="self-start"
                onClick={() => setConfirmingStop(true)}
              >
                <Link2Off />
                Stop sharing
              </Button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
