'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

import { UserEmail } from '@/components/UserEmail';
import { Badge, Card, Empty, ErrorNote, Loading, PageHeader, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatBytes, formatDate, formatDateTime, timeAgo } from '@/lib/format';
import type { UserDetail } from '@/lib/types';

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">{label}</dt>
      <dd className="mt-1 text-sm">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <h2 className="border-b border-zinc-200 px-4 py-3 font-bold">{title}</h2>
      {children}
    </Card>
  );
}

function ProfileSection({ profile }: { profile: UserDetail['profile'] }) {
  if (!profile) {
    return (
      <Section title="Profile">
        <Empty>This person has not added a profile or resume yet.</Empty>
      </Section>
    );
  }
  return (
    <Section title="Profile">
      <dl className="grid gap-5 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Name">{profile.full_name ?? '—'}</Fact>
        <Fact label="Headline">{profile.headline ?? '—'}</Fact>
        <Fact label="Location">{profile.location ?? '—'}</Fact>
        <Fact label="Completeness">{profile.completeness}%</Fact>
      </dl>
      <div className="space-y-4 border-t border-zinc-200 p-4 text-sm">
        <div>
          <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">
            Skills ({profile.skills.length})
          </p>
          <p className="mt-1.5 flex flex-wrap gap-1.5">
            {profile.skills.length === 0
              ? '—'
              : profile.skills.map((skill) => <Badge key={skill.id}>{skill.name}</Badge>)}
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">
            Experience ({profile.experience.length})
          </p>
          <ul className="mt-1.5 space-y-1">
            {profile.experience.length === 0
              ? '—'
              : profile.experience.map((job) => (
                  <li key={job.id}>
                    <span className="font-semibold">{job.title}</span> at {job.company}
                    <span className="text-zinc-500">
                      {job.start ? ` · ${job.start} to ${job.end ?? 'present'}` : ''}
                    </span>
                  </li>
                ))}
          </ul>
        </div>
      </div>
    </Section>
  );
}

/** Deleting is final, so the admin has to type the account's email address first. */
function DeleteAccount({ id, email }: { id: string; email: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [typed, setTyped] = useState('');
  const remove = useMutation({
    mutationFn: () =>
      api<void>(`/admin/users/${id}`, { method: 'DELETE', params: { confirm_email: typed } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      router.replace('/users');
    },
  });
  const matches = typed.trim().toLowerCase() === email.toLowerCase();

  return (
    <Card className="p-4 ring-red-200">
      <h2 className="font-bold text-red-800">Delete this account</h2>
      <p className="mt-1 max-w-2xl text-sm text-zinc-600">
        Removes the profile, resume files, job checks, applications, saved answers and the Gmail
        connection. It cannot be undone. Their Google sign-in is not removed, so they could sign up
        again from nothing.
      </p>
      <form
        className="mt-4 flex flex-wrap items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (matches) remove.mutate();
        }}
      >
        <input
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          aria-label={`Type ${email} to confirm`}
          placeholder={`Type ${email} to confirm`}
          autoComplete="off"
          className="w-80 max-w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-red-700"
        />
        <button
          disabled={!matches || remove.isPending}
          className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 disabled:opacity-40"
        >
          {remove.isPending ? 'Deleting…' : 'Delete account'}
        </button>
      </form>
      {remove.isError && (
        <p role="alert" className="mt-2 text-sm font-medium text-red-700">
          {errorMessage(remove.error)}
        </p>
      )}
    </Card>
  );
}

export default function UserPage() {
  const { id } = useParams<{ id: string }>();
  const detail = useQuery({
    queryKey: ['admin', 'user', id],
    queryFn: () => api<UserDetail>(`/admin/users/${id}`),
    // Each read is written to the audit log, so it is not repeated in the background.
    staleTime: Infinity,
  });

  if (detail.isPending) {
    return (
      <Card>
        <Loading rows={8} />
      </Card>
    );
  }
  if (detail.isError) {
    return (
      <Card>
        <ErrorNote message={errorMessage(detail.error)} onRetry={() => detail.refetch()} />
      </Card>
    );
  }
  const { user, profile, job_checks, applications, resumes, gmail_last_synced_at } = detail.data;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/users" className="text-sm font-semibold text-zinc-500 hover:text-zinc-900">
          ← Users
        </Link>
        <PageHeader title={user.name ?? user.email} subtitle={user.name ? user.email : undefined} />
        <p className="-mt-3 text-xs text-zinc-500">
          Opening this page was recorded in the audit log.
        </p>
      </div>

      <Card>
        <dl className="grid gap-5 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label="Joined">{formatDate(user.created_at)}</Fact>
          <Fact label="Job checks">{user.job_checks}</Fact>
          <Fact label="Applications">{user.applications}</Fact>
          <Fact label="Gmail">
            {user.gmail_connected
              ? `Connected${gmail_last_synced_at ? `, synced ${timeAgo(gmail_last_synced_at)}` : ''}`
              : 'Not connected'}
          </Fact>
        </dl>
      </Card>

      <ProfileSection profile={profile} />

      <Section title={`Resume files (${resumes.length})`}>
        {resumes.length === 0 ? (
          <Empty>No resume uploaded.</Empty>
        ) : (
          <ul className="divide-y divide-zinc-100 text-sm">
            {resumes.map((resume) => (
              <li
                key={`${resume.filename}-${resume.created_at}`}
                className="flex flex-wrap gap-x-4 px-4 py-3"
              >
                <span className="font-semibold">{resume.filename}</span>
                <span className="text-zinc-500">{formatBytes(resume.size_bytes)}</span>
                <span className="text-zinc-500">{formatDateTime(resume.created_at)}</span>
                <Badge>{resume.status}</Badge>
              </li>
            ))}
          </ul>
        )}
        <p className="border-t border-zinc-200 px-4 py-2.5 text-xs text-zinc-500">
          Only details of the file are shown here. The resume itself is not opened from the panel.
        </p>
      </Section>

      <Section title="Recent job checks">
        {job_checks.length === 0 ? (
          <Empty>No job checks yet.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200">
                <tr>
                  <th className={th}>Role</th>
                  <th className={th}>Company</th>
                  <th className={th}>Score</th>
                  <th className={th}>Status</th>
                  <th className={th}>When</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {job_checks.map((check) => (
                  <tr key={check.id}>
                    <td className={td}>
                      {check.url ? (
                        <a
                          href={check.url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-semibold hover:underline"
                        >
                          {check.role ?? 'Untitled job'}
                        </a>
                      ) : (
                        <span className="font-semibold">{check.role ?? 'Untitled job'}</span>
                      )}
                    </td>
                    <td className={`${td} text-zinc-600`}>{check.company ?? '—'}</td>
                    <td className={`${td} font-semibold tabular-nums`}>{check.score ?? '—'}</td>
                    <td className={td}>
                      <Badge
                        tone={
                          check.status === 'completed'
                            ? 'green'
                            : check.status === 'failed'
                              ? 'red'
                              : 'amber'
                        }
                      >
                        {check.status}
                      </Badge>
                    </td>
                    <td className={`${td} text-zinc-600`}>{timeAgo(check.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Recent applications">
        {applications.length === 0 ? (
          <Empty>No applications tracked yet.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200">
                <tr>
                  <th className={th}>Role</th>
                  <th className={th}>Company</th>
                  <th className={th}>Status</th>
                  <th className={th}>Score</th>
                  <th className={th}>Added</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {applications.map((item) => (
                  <tr key={item.id}>
                    <td className={`${td} font-semibold`}>{item.role}</td>
                    <td className={`${td} text-zinc-600`}>{item.company}</td>
                    <td className={td}>
                      <Badge tone="blue">{item.status}</Badge>
                    </td>
                    <td className={`${td} tabular-nums`}>{item.match_score ?? '—'}</td>
                    <td className={`${td} text-zinc-600`}>{timeAgo(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <UserEmail
        userId={user.id}
        extensionConnected={user.extension_connected}
        sent={detail.data.panel_emails}
      />

      <DeleteAccount id={user.id} email={user.email} />
    </div>
  );
}
