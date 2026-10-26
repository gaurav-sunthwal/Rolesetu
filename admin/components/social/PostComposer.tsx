'use client';

import { useId, useState, type ChangeEvent } from 'react';

import { Card, button } from '@/components/ui';
import { errorMessage } from '@/lib/api';
import { PLATFORM_NAMES, TEXT_LIMITS, uploadImage, useSavePost } from '@/lib/social';
import type { SocialAccount, SocialPost } from '@/lib/types';

const field =
  'w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-900';
const label = 'text-xs font-semibold tracking-wide text-zinc-500 uppercase';

/**
 * Writes a post, or edits a draft. Saving never publishes: a saved post waits
 * in the queue as a draft until someone approves it there.
 */
export function PostComposer({
  accounts,
  editing,
  onDone,
}: {
  accounts: SocialAccount[];
  editing: SocialPost | null;
  onDone: () => void;
}) {
  const textId = useId();
  const imageLinkId = useId();
  const [text, setText] = useState(editing?.text ?? '');
  const [imageUrl, setImageUrl] = useState(editing?.image_url ?? '');
  const [chosen, setChosen] = useState<string[]>(
    editing?.targets.map((target) => target.account_id) ?? [],
  );
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const save = useSavePost();

  const active = accounts.filter((account) => account.status === 'active');
  const chosenAccounts = active.filter((account) => chosen.includes(account.id));
  const platforms = [...new Set(chosenAccounts.map((account) => account.platform))];
  const limit = platforms.length
    ? Math.min(...platforms.map((platform) => TEXT_LIMITS[platform]))
    : TEXT_LIMITS.linkedin;
  const tightest = platforms.find((platform) => TEXT_LIMITS[platform] === limit) ?? 'linkedin';
  const tooLong = text.trim().length > limit;
  const needsImage = platforms.includes('instagram') && !imageUrl.trim();
  const ready = text.trim().length > 0 && chosen.length > 0 && !tooLong && !needsImage;

  function toggle(id: string) {
    setChosen((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      setImageUrl(await uploadImage(file));
    } catch (error) {
      setUploadError(errorMessage(error));
    } finally {
      setUploading(false);
    }
  }

  function submit() {
    save.mutate(
      {
        id: editing?.id ?? null,
        body: { text: text.trim(), image_url: imageUrl.trim() || null, account_ids: chosen },
      },
      {
        onSuccess: () => {
          setText('');
          setImageUrl('');
          setChosen([]);
          onDone();
        },
      },
    );
  }

  return (
    <Card>
      <div className="border-b border-zinc-200 px-4 py-3">
        <h2 className="font-bold">{editing ? 'Edit draft' : 'New post'}</h2>
        <p className="text-sm text-zinc-500">
          Saved posts wait as drafts. Nothing goes out until you approve it in the queue below.
        </p>
      </div>
      <form
        className="space-y-4 p-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) submit();
        }}
      >
        <div>
          <label htmlFor={textId} className={label}>
            Text
          </label>
          <textarea
            id={textId}
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={7}
            className={`${field} mt-1 leading-relaxed`}
            placeholder="What do you want to say? #hashtags work on every platform."
          />
          <p className={`mt-1 text-xs ${tooLong ? 'font-semibold text-red-700' : 'text-zinc-500'}`}>
            {text.trim().length.toLocaleString()} / {limit.toLocaleString()} characters
            {platforms.length > 0 && ` (${PLATFORM_NAMES[tightest]} limit)`}
          </p>
        </div>

        <div>
          <p className={label}>Image</p>
          {imageUrl ? (
            <div className="mt-2 flex items-start gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element -- any host, shown as uploaded */}
              <img
                src={imageUrl}
                alt="The post's image"
                className="h-24 w-24 rounded-lg object-cover ring-1 ring-zinc-200"
              />
              <button type="button" onClick={() => setImageUrl('')} className={button}>
                Remove image
              </button>
            </div>
          ) : (
            <div className="mt-2 space-y-2">
              <label className={`${button} inline-block cursor-pointer`}>
                {uploading ? 'Uploading…' : 'Upload an image'}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="sr-only"
                  disabled={uploading}
                  onChange={onFile}
                />
              </label>
              <div>
                <label htmlFor={imageLinkId} className="text-xs text-zinc-500">
                  or paste an https link to an image (a shared score card works too)
                </label>
                <input
                  id={imageLinkId}
                  type="url"
                  value={imageUrl}
                  onChange={(event) => setImageUrl(event.target.value)}
                  placeholder="https://…"
                  className={`${field} mt-1`}
                />
              </div>
            </div>
          )}
          {uploadError && (
            <p role="alert" className="mt-1 text-sm text-red-700">
              {uploadError}
            </p>
          )}
          {needsImage && (
            <p className="mt-1 text-xs font-semibold text-amber-700">
              Instagram needs an image on every post.
            </p>
          )}
        </div>

        <fieldset>
          <legend className={label}>Post to</legend>
          {active.length === 0 ? (
            <p className="mt-1 text-sm text-zinc-500">Connect an account above first.</p>
          ) : (
            <div className="mt-2 flex flex-wrap gap-2">
              {active.map((account) => (
                <label
                  key={account.id}
                  className={`flex cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-sm ring-1 focus-within:outline-2 focus-within:outline-blue-500 ${chosen.includes(account.id) ? 'bg-zinc-900 text-white ring-zinc-900' : 'bg-white ring-zinc-200 hover:bg-zinc-50'}`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={chosen.includes(account.id)}
                    onChange={() => toggle(account.id)}
                  />
                  {account.name}
                  <span className="opacity-70">· {PLATFORM_NAMES[account.platform]}</span>
                </label>
              ))}
            </div>
          )}
        </fieldset>

        {save.isError && (
          <p role="alert" className="text-sm text-red-700">
            {errorMessage(save.error)}
          </p>
        )}

        <div className="flex gap-2">
          <button
            type="submit"
            disabled={!ready || save.isPending || uploading}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
          >
            {save.isPending ? 'Saving…' : editing ? 'Save changes' : 'Save draft'}
          </button>
          {editing && (
            <button type="button" onClick={onDone} className={button}>
              Cancel
            </button>
          )}
        </div>
      </form>
    </Card>
  );
}
