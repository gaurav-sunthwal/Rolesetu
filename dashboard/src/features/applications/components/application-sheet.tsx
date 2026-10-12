'use client';

import { ExternalLink, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/app/confirm-dialog';
import { ErrorState } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ApplicationForm,
  type ApplicationFormValues,
  defaultsFrom,
  toRequestBody,
} from '@/features/applications/components/application-form';
import { StatusDot } from '@/features/applications/components/status-badge';
import {
  useApplication,
  useDeleteApplication,
  useUpdateApplication,
} from '@/features/applications/hooks';
import { STATUS_META } from '@/features/applications/status';
import { ApplicationEmails } from '@/features/inbox/components/application-emails';
import { errorMessage } from '@/lib/api/client';
import type { ApplicationDetail, ApplicationStatus } from '@/lib/api/types';
import { formatDate, timeAgo } from '@/lib/format';

const FORM_ID = 'edit-application';

export function ApplicationSheet({
  applicationId,
  onClose,
}: {
  applicationId: string | null;
  onClose: () => void;
}) {
  const query = useApplication(applicationId);

  return (
    <Sheet open={applicationId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full gap-0 overflow-y-auto p-0 sm:max-w-md">
        {query.isPending ? (
          <div className="flex flex-col gap-4 p-6">
            <SheetHeader className="p-0">
              <SheetTitle>Loading application</SheetTitle>
              <SheetDescription>Fetching the details.</SheetDescription>
            </SheetHeader>
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : query.isError ? (
          <>
            <SheetHeader>
              <SheetTitle>Application</SheetTitle>
              <SheetDescription>Something went wrong loading it.</SheetDescription>
            </SheetHeader>
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          </>
        ) : (
          <ApplicationEditor
            key={`${query.data.id}:${query.data.updated_at}`}
            application={query.data}
            onClose={onClose}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

function ApplicationEditor({
  application,
  onClose,
}: {
  application: ApplicationDetail;
  onClose: () => void;
}) {
  const update = useUpdateApplication();
  const remove = useDeleteApplication();
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  function handleSubmit(values: ApplicationFormValues) {
    update.mutate(
      { id: application.id, body: toRequestBody(values) },
      {
        onSuccess: () => toast.success('Changes saved'),
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }

  function handleDelete() {
    remove.mutate(application.id, {
      onSuccess: () => {
        toast.success('Application removed');
        setConfirmingDelete(false);
        onClose();
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  }

  return (
    <>
      <SheetHeader className="border-b p-6 pr-12">
        <SheetTitle className="text-lg leading-snug">{application.role}</SheetTitle>
        <SheetDescription>
          {application.company}
          {application.match_score !== null ? ` · Match score ${application.match_score}` : ''}
        </SheetDescription>
        {application.url ? (
          <a
            href={application.url}
            target="_blank"
            rel="noreferrer"
            className="text-primary inline-flex w-fit items-center gap-1 text-sm font-medium underline-offset-4 hover:underline"
          >
            Open job posting
            <ExternalLink className="size-3.5" />
          </a>
        ) : null}
      </SheetHeader>

      <div className="flex flex-col gap-8 p-6">
        {application.needs_follow_up ? (
          <p className="bg-warning/15 rounded-2xl px-4 py-3 text-sm">
            No reply in over a week. It may be worth sending a short follow-up.
          </p>
        ) : null}

        <ApplicationForm
          formId={FORM_ID}
          defaultValues={defaultsFrom(application)}
          onSubmit={handleSubmit}
        />

        <ApplicationEmails applicationId={application.id} />

        <section>
          <h3 className="text-sm font-semibold">Timeline</h3>
          <ol className="mt-3 flex flex-col gap-3">
            {application.events.map((event) => {
              const known = event.type in STATUS_META;
              return (
                <li key={event.id} className="flex items-center gap-3 text-sm">
                  {known ? (
                    <StatusDot status={event.type as ApplicationStatus} />
                  ) : (
                    <span className="bg-muted-foreground/60 size-2 rounded-full" />
                  )}
                  <span className="font-medium">
                    {known ? STATUS_META[event.type as ApplicationStatus].label : event.type}
                  </span>
                  {event.source === 'gmail' ? (
                    <span className="bg-secondary text-muted-foreground rounded-full px-2 py-0.5 text-xs">
                      from Gmail
                    </span>
                  ) : null}
                  <span
                    className="text-muted-foreground ml-auto"
                    title={formatDate(event.occurred_at)}
                  >
                    {timeAgo(event.occurred_at)}
                  </span>
                </li>
              );
            })}
          </ol>
        </section>
      </div>

      <div className="bg-popover sticky bottom-0 mt-auto flex items-center gap-2 border-t p-4">
        <Button
          variant="ghost"
          className="text-destructive hover:bg-destructive/10 hover:text-destructive"
          onClick={() => setConfirmingDelete(true)}
        >
          <Trash2 />
          Delete
        </Button>
        <Button type="submit" form={FORM_ID} className="ml-auto" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save changes'}
        </Button>
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        title="Delete this application?"
        description={`${application.role} at ${application.company} and its timeline will be removed. This cannot be undone.`}
        confirmLabel={remove.isPending ? 'Deleting…' : 'Delete'}
        pending={remove.isPending}
        onConfirm={handleDelete}
      />
    </>
  );
}
