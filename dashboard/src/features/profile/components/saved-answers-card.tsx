'use client';

import { useForm } from 'react-hook-form';
import { toast } from 'sonner';

import { Field, inputClass } from '@/components/app/field';
import { SectionCard } from '@/components/app/section-card';
import { ErrorState } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useDeleteSavedAnswer, useSavedAnswers, useSetSavedAnswer } from '@/features/profile/hooks';
import { errorMessage } from '@/lib/api/client';
import type { SavedAnswer } from '@/lib/api/types';

const QUESTIONS = [
  { key: 'notice_period', label: 'Notice period', placeholder: '30 days' },
  { key: 'current_ctc', label: 'Current CTC', placeholder: '₹12 LPA' },
  { key: 'expected_ctc', label: 'Expected CTC', placeholder: '₹18 LPA' },
  { key: 'relocation', label: 'Willing to relocate?', placeholder: 'Yes, within India' },
  { key: 'work_authorization', label: 'Work authorization', placeholder: 'Indian citizen' },
  {
    key: 'why_this_role',
    label: 'Why are you looking for a new role?',
    placeholder: 'A short answer you can reuse and adjust',
    long: true,
  },
] as const;

type Values = Record<string, string>;

export function SavedAnswersCard() {
  const answers = useSavedAnswers();

  return (
    <SectionCard
      title="Saved answers"
      description="Questions most applications ask. Answer once and reuse them."
    >
      {answers.isPending ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-10" />
          ))}
        </div>
      ) : answers.isError ? (
        <ErrorState error={answers.error} onRetry={() => answers.refetch()} className="py-6" />
      ) : (
        <AnswersForm key={answers.dataUpdatedAt} saved={answers.data} />
      )}
    </SectionCard>
  );
}

function AnswersForm({ saved }: { saved: SavedAnswer[] }) {
  const setAnswer = useSetSavedAnswer();
  const deleteAnswer = useDeleteSavedAnswer();
  const stored = new Map(saved.map((answer) => [answer.question_key, answer.answer]));
  const defaultValues: Values = Object.fromEntries(
    QUESTIONS.map((question) => [question.key, stored.get(question.key) ?? '']),
  );
  const {
    register,
    handleSubmit,
    formState: { isDirty, errors },
  } = useForm<Values>({ defaultValues });
  const pending = setAnswer.isPending || deleteAnswer.isPending;

  async function onSubmit(values: Values) {
    const changes = QUESTIONS.map((question) => ({
      key: question.key,
      next: (values[question.key] ?? '').trim(),
      previous: stored.get(question.key) ?? '',
    })).filter((change) => change.next !== change.previous);

    try {
      await Promise.all(
        changes.map((change) =>
          change.next
            ? setAnswer.mutateAsync({ key: change.key, answer: change.next })
            : deleteAnswer.mutateAsync(change.key),
        ),
      );
      toast.success('Answers saved');
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {QUESTIONS.map((question) => {
          const id = `answer-${question.key}`;
          const rules = { maxLength: { value: 2000, message: 'Keep this under 2,000 characters' } };
          const message = errors[question.key]?.message;
          return (
            <Field
              key={question.key}
              id={id}
              label={question.label}
              error={typeof message === 'string' ? message : undefined}
              className={'long' in question ? 'sm:col-span-2' : undefined}
            >
              {'long' in question ? (
                <Textarea
                  id={id}
                  rows={3}
                  className="px-3.5 py-2.5"
                  placeholder={question.placeholder}
                  {...register(question.key, rules)}
                />
              ) : (
                <Input
                  id={id}
                  className={inputClass}
                  placeholder={question.placeholder}
                  {...register(question.key, rules)}
                />
              )}
            </Field>
          );
        })}
      </div>
      <div>
        <Button type="submit" disabled={!isDirty || pending}>
          {pending ? 'Saving…' : 'Save answers'}
        </Button>
      </div>
    </form>
  );
}
