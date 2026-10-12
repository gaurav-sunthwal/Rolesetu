'use client';

import { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  ApplicationForm,
  type ApplicationFormValues,
  defaultsFrom,
  toRequestBody,
} from '@/features/applications/components/application-form';
import { useCreateApplication } from '@/features/applications/hooks';
import { errorMessage } from '@/lib/api/client';
import type { ApplicationStatus } from '@/lib/api/types';
import { newId } from '@/lib/format';

export type ApplicationPrefill = {
  role?: string | null;
  company?: string | null;
  url?: string | null;
  status?: ApplicationStatus;
  matchId?: string;
};

const FORM_ID = 'add-application';

export function AddApplicationDialog({
  open,
  onOpenChange,
  prefill,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prefill?: ApplicationPrefill;
  onCreated?: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92svh] overflow-y-auto rounded-3xl p-6 sm:max-w-lg">
        {/* Mounted per open, so each time gets a fresh form and idempotency key. */}
        {open ? (
          <AddApplicationBody
            prefill={prefill}
            onDone={() => {
              onOpenChange(false);
              onCreated?.();
            }}
            onCancel={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function AddApplicationBody({
  prefill,
  onDone,
  onCancel,
}: {
  prefill?: ApplicationPrefill;
  onDone: () => void;
  onCancel: () => void;
}) {
  const create = useCreateApplication();
  // One key per opened dialog: a double click or a retry cannot create a duplicate.
  const [idempotencyKey] = useState(newId);

  function handleSubmit(values: ApplicationFormValues) {
    create.mutate(
      { body: { ...toRequestBody(values), match_id: prefill?.matchId ?? null }, idempotencyKey },
      {
        onSuccess: (created) => {
          toast.success(`Tracking ${created.role} at ${created.company}`);
          onDone();
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle className="text-lg">Track an application</DialogTitle>
        <DialogDescription>
          Save a job you are interested in, or record one you have already applied to.
        </DialogDescription>
      </DialogHeader>
      <ApplicationForm
        formId={FORM_ID}
        defaultValues={defaultsFrom({
          role: prefill?.role ?? '',
          company: prefill?.company ?? '',
          url: prefill?.url ?? '',
          status: prefill?.status ?? 'saved',
        })}
        onSubmit={handleSubmit}
      />
      <DialogFooter>
        <Button variant="outline" onClick={onCancel} disabled={create.isPending}>
          Cancel
        </Button>
        <Button type="submit" form={FORM_ID} disabled={create.isPending}>
          {create.isPending ? 'Saving…' : 'Track application'}
        </Button>
      </DialogFooter>
    </>
  );
}
