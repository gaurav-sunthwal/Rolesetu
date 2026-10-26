'use client';

import { useId, useState } from 'react';

import { Badge, Card, Empty, ErrorNote, Loading, LoadMore, button } from '@/components/ui';
import { errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PLATFORM_NAMES,
  useDeletePost,
  usePostAction,
  useSchedulePost,
  useSocialPosts,
} from '@/lib/social';
import type { SocialPost } from '@/lib/types';

const STATUS: Record<
  SocialPost['status'],
  { label: string; tone: 'zinc' | 'blue' | 'amber' | 'green' | 'red' }
> = {
  draft: { label: 'Draft', tone: 'zinc' },
  scheduled: { label: 'Scheduled', tone: 'blue' },
  publishing: { label: 'Publishing', tone: 'amber' },
  posted: { label: 'Posted', tone: 'green' },
  partly_posted: { label: 'Partly posted', tone: 'amber' },
  failed: { label: 'Failed', tone: 'red' },
};

const primary =
  'rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-50';

/** A datetime-local value for an hour from now, in the admin's own timezone. */
function inAnHour(): string {
  const date = new Date(Date.now() + 3_600_000);
  date.setSeconds(0, 0);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function ApproveControls({ post, onClose }: { post: SocialPost; onClose: () => void }) {
  const timeId = useId();
  const [when, setWhen] = useState(inAnHour);
  const [confirmNow, setConfirmNow] = useState(false);
  const schedule = useSchedulePost();

  function approve(at: string | null) {
    schedule.mutate({ id: post.id, at }, { onSuccess: onClose });
  }

  return (
    <div className="mt-3 space-y-3 rounded-lg bg-zinc-50 p-3 ring-1 ring-zinc-200">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label htmlFor={timeId} className="block text-xs font-semibold text-zinc-500">
            Post at (your time)
          </label>
          <input
            id={timeId}
            type="datetime-local"
            value={when}
            onChange={(event) => setWhen(event.target.value)}
            className="mt-1 rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
          />
        </div>
        <button
          onClick={() => approve(new Date(when).toISOString())}
          disabled={!when || schedule.isPending}
          className={primary}
        >
          Approve for this time
        </button>
        {confirmNow ? (
          <span className="flex items-center gap-2 text-sm">
            Publish to {post.targets.length} {post.targets.length === 1 ? 'account' : 'accounts'}{' '}
            now?
            <button onClick={() => approve(null)} disabled={schedule.isPending} className={primary}>
              {schedule.isPending ? 'Approving…' : 'Yes, post now'}
            </button>
          </span>
        ) : (
          <button onClick={() => setConfirmNow(true)} className={button}>
            Post now…
          </button>
        )}
        <button onClick={onClose} className={button}>
          Cancel
        </button>
      </div>
      {schedule.isError && (
        <p role="alert" className="text-sm text-red-700">
          {errorMessage(schedule.error)}
        </p>
      )}
    </div>
  );
}

function PostItem({ post, onEdit }: { post: SocialPost; onEdit: (post: SocialPost) => void }) {
  const [approving, setApproving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const action = usePostAction();
  const remove = useDeletePost();
  const status = STATUS[post.status];
  const error = action.error ?? remove.error;

  return (
    <li className="px-4 py-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
        <Badge tone={status.tone}>{status.label}</Badge>
        {post.status === 'scheduled' && post.scheduled_at && (
          <span>goes out {formatDateTime(post.scheduled_at)}</span>
        )}
        <span>
          · written by {post.created_by} {formatDateTime(post.created_at)}
          {post.approved_by && `, approved by ${post.approved_by}`}
        </span>
      </div>

      <div className="mt-2 flex gap-3">
        {post.image_url && (
          // eslint-disable-next-line @next/next/no-img-element -- any host, shown as uploaded
          <img
            src={post.image_url}
            alt=""
            className="h-16 w-16 shrink-0 rounded-lg object-cover ring-1 ring-zinc-200"
          />
        )}
        <p className="line-clamp-4 text-sm whitespace-pre-wrap">{post.text}</p>
      </div>

      <ul className="mt-3 space-y-1">
        {post.targets.map((target) => (
          <li key={target.id} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-semibold">{target.account_name}</span>
            <span className="text-zinc-500">{PLATFORM_NAMES[target.platform]}</span>
            {target.status === 'posted' ? (
              target.external_url ? (
                <a
                  href={target.external_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-semibold text-blue-700 underline-offset-2 hover:underline"
                >
                  View post
                </a>
              ) : (
                <span className="text-emerald-700">Posted</span>
              )
            ) : target.status === 'failed' ? (
              <span className="text-red-700">{target.error ?? 'Failed'}</span>
            ) : target.status === 'publishing' ? (
              <span className="text-amber-700">Publishing…</span>
            ) : target.error ? (
              <span className="text-amber-700">Will try again: {target.error}</span>
            ) : null}
          </li>
        ))}
      </ul>

      <div className="mt-3 flex flex-wrap gap-2">
        {post.status === 'draft' && !approving && (
          <>
            <button onClick={() => setApproving(true)} className={primary}>
              Approve…
            </button>
            <button onClick={() => onEdit(post)} className={button}>
              Edit
            </button>
          </>
        )}
        {post.status === 'scheduled' && (
          <button
            onClick={() => action.mutate({ id: post.id, action: 'unschedule' })}
            disabled={action.isPending}
            className={button}
          >
            Move back to drafts
          </button>
        )}
        {(post.status === 'failed' || post.status === 'partly_posted') && (
          <button
            onClick={() => action.mutate({ id: post.id, action: 'retry' })}
            disabled={action.isPending}
            className={button}
          >
            Retry where it failed
          </button>
        )}
        {post.status !== 'publishing' &&
          (confirmDelete ? (
            <span className="flex items-center gap-2 text-sm">
              {post.status === 'posted' || post.status === 'partly_posted'
                ? 'Remove from this list? It stays up on the platforms.'
                : 'Delete this post?'}
              <button
                onClick={() => remove.mutate(post.id)}
                disabled={remove.isPending}
                className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
              >
                {remove.isPending ? 'Deleting…' : 'Delete'}
              </button>
              <button onClick={() => setConfirmDelete(false)} className={button}>
                Keep
              </button>
            </span>
          ) : (
            <button onClick={() => setConfirmDelete(true)} className={button}>
              Delete
            </button>
          ))}
      </div>
      {approving && <ApproveControls post={post} onClose={() => setApproving(false)} />}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {errorMessage(error)}
        </p>
      )}
    </li>
  );
}

export function PostQueue({ onEdit }: { onEdit: (post: SocialPost) => void }) {
  const posts = useSocialPosts();
  const rows = posts.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <div className="border-b border-zinc-200 px-4 py-3">
        <h2 className="font-bold">Queue</h2>
        <p className="text-sm text-zinc-500">
          Approve a draft to schedule it. Scheduled posts go out within a minute of their time.
        </p>
      </div>
      {posts.isPending ? (
        <Loading />
      ) : posts.isError ? (
        <ErrorNote message={errorMessage(posts.error)} onRetry={() => posts.refetch()} />
      ) : rows.length === 0 ? (
        <Empty>No posts yet. Write one above and save it as a draft.</Empty>
      ) : (
        <ul className="divide-y divide-zinc-100">
          {rows.map((post) => (
            <PostItem key={post.id} post={post} onEdit={onEdit} />
          ))}
        </ul>
      )}
      <LoadMore
        show={posts.hasNextPage}
        busy={posts.isFetchingNextPage}
        onClick={() => posts.fetchNextPage()}
      />
    </Card>
  );
}
