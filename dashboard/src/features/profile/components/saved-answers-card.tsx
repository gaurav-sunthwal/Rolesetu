'use client';

import { X } from 'lucide-react';
import { useForm, useWatch } from 'react-hook-form';
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

type Question = {
  key: string;
  label: string;
  placeholder?: string;
  type?: 'date';
  long?: boolean;
};

const QUESTIONS: Question[] = [
  { key: 'notice_period', label: 'Notice period', placeholder: '30 days' },
  { key: 'current_ctc', label: 'Current CTC', placeholder: '₹12 LPA' },
  { key: 'expected_ctc', label: 'Expected CTC', placeholder: '₹18 LPA' },
  { key: 'relocation', label: 'Willing to relocate?', placeholder: 'Yes, within India' },
  { key: 'work_authorization', label: 'Work authorization', placeholder: 'Indian citizen' },
  // Saved as YYYY-MM-DD; the extension writes it in each form's own format.
  { key: 'date_of_birth', label: 'Date of birth', type: 'date' },
  {
    key: 'why_this_role',
    label: 'Why are you looking for a new role?',
    placeholder: 'A short answer you can reuse and adjust',
    long: true,
  },
];

// Answers the extension can learn that are not asked above.
const LEARNED_NAMES: Record<string, string> = {
  gender: 'Gender',
  nationality: 'Nationality',
  postal_code: 'Postal code',
  heard_from: 'How you heard about the job',
};

/** A learned answer's question: "q_how_did_you_hear_about_us" reads "How did you hear about us". */
function learnedLabel(key: string): string {
  const words = LEARNED_NAMES[key] ?? key.replace(/^q_/, '').replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

type Values = Record<string, string>;

const RULES = { maxLength: { value: 2000, message: 'Keep this under 2,000 characters' } };

export function SavedAnswersCard() {
  const answers = useSavedAnswers();

  return (
    <SectionCard
      title="Saved answers"
      description="Questions most applications ask. Answer once and reuse them. When you answer a new question on an application form, the extension remembers it here too."
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
  const common = new Set(QUESTIONS.map((question) => question.key));
  const learned: Question[] = saved
    .filter((answer) => !common.has(answer.question_key))
    .map((answer) => ({ key: answer.question_key, label: learnedLabel(answer.question_key) }));
  const questions = [...QUESTIONS, ...learned];
  const defaultValues: Values = Object.fromEntries(
    questions.map((question) => [question.key, stored.get(question.key) ?? '']),
  );
  const {
    register,
    handleSubmit,
    setValue,
    control,
    formState: { isDirty, errors },
  } = useForm<Values>({ defaultValues });
  const current = useWatch({ control });
  const pending = setAnswer.isPending || deleteAnswer.isPending;

  async function onSubmit(values: Values) {
    const changes = questions
      .map((question) => ({
        key: question.key,
        next: (values[question.key] ?? '').trim(),
        previous: stored.get(question.key) ?? '',
      }))
      .filter((change) => change.next !== change.previous);

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
          const message = errors[question.key]?.message;
          return (
            <Field
              key={question.key}
              id={id}
              label={question.label}
              error={typeof message === 'string' ? message : undefined}
              className={question.long ? 'sm:col-span-2' : undefined}
            >
              {question.long ? (
                <Textarea
                  id={id}
                  rows={3}
                  className="px-3.5 py-2.5"
                  placeholder={question.placeholder}
                  {...register(question.key, RULES)}
                />
              ) : (
                <Input
                  id={id}
                  type={question.type ?? 'text'}
                  className={inputClass}
                  placeholder={question.placeholder}
                  {...register(question.key, RULES)}
                />
              )}
            </Field>
          );
        })}
      </div>
      {learned.length > 0 ? (
        <div className="flex flex-col gap-3 border-t pt-4">
          <div>
            <h3 className="text-sm font-medium">Learned from your applications</h3>
            <p className="text-muted-foreground text-sm">
              Fix an answer here, or remove one you do not want filled in again.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {learned.map((question) => {
              const id = `answer-${question.key}`;
              const message = errors[question.key]?.message;
              const removed = current[question.key] === '';
              return (
                <Field
                  key={question.key}
                  id={id}
                  label={question.label}
                  error={typeof message === 'string' ? message : undefined}
                >
                  <div className="flex gap-2">
                    <Input
                      id={id}
                      className={inputClass}
                      placeholder={removed ? 'Removed when you save' : undefined}
                      {...register(question.key, RULES)}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove the answer to ${question.label}`}
                      disabled={removed}
                      onClick={() => setValue(question.key, '', { shouldDirty: true })}
                    >
                      <X aria-hidden />
                    </Button>
                  </div>
                </Field>
              );
            })}
          </div>
        </div>
      ) : null}
      <div>
        <Button type="submit" disabled={!isDirty || pending}>
          {pending ? 'Saving…' : 'Save answers'}
        </Button>
      </div>
    </form>
  );
}
