import { useEffect, useState } from 'react';

import { ask } from '@/lib/messages';
import { CHROME_REVIEW_URL, FEEDBACK_MAIL, type ReviewAnswer } from '@/lib/review-ask';

type Step = { name: 'hidden' } | { name: 'ask'; applications: number } | { name: 'better' } | { name: 'thanks' };

/**
 * A small card under the score asking for a Chrome Web Store review, once the
 * background worker says Rolesetu has earned it (see review-ask.ts). The store
 * link is offered to everyone; "Could be better" asks what to fix instead.
 */
export function ReviewAsk() {
  const [step, setStep] = useState<Step>({ name: 'hidden' });

  useEffect(() => {
    let current = true;
    void ask({ type: 'review-ask', action: 'check' }).then((result) => {
      if (!current || !result.ok || !result.data.ask) return;
      setStep({ name: 'ask', applications: result.data.applications });
      void ask({ type: 'review-ask', action: 'shown' });
    });
    return () => {
      current = false;
    };
  }, []);

  function answer(choice: ReviewAnswer, next: Step) {
    void ask({ type: 'review-ask', action: 'answer', answer: choice });
    setStep(next);
  }

  if (step.name === 'hidden') return null;

  if (step.name === 'thanks') {
    return (
      <section className="review" aria-live="polite">
        <p className="review-title">Thank you!</p>
        <p className="muted small">It really helps other job seekers find Rolesetu.</p>
      </section>
    );
  }

  if (step.name === 'better') {
    return (
      <section className="review" aria-label="Tell us what to improve">
        <p className="review-title">What should be better?</p>
        <p className="muted small">
          Thanks for being honest. Rolesetu is built by one person who reads every note.
        </p>
        <div className="review-actions">
          <a
            className="btn primary"
            href={FEEDBACK_MAIL}
            target="_blank"
            rel="noreferrer"
            onClick={() => setStep({ name: 'thanks' })}
          >
            Tell the founder
          </a>
          <button type="button" className="btn" onClick={() => setStep({ name: 'hidden' })}>
            Close
          </button>
        </div>
      </section>
    );
  }

  const helped =
    step.applications >= 2 ? `You've used Rolesetu on ${step.applications} applications.` : 'Thanks for using Rolesetu.';
  return (
    <section className="review" aria-label="Rate Rolesetu">
      <button
        type="button"
        className="icon review-close"
        aria-label="Not now"
        title="Not now"
        onClick={() => answer('later', { name: 'hidden' })}
      >
        ×
      </button>
      <p className="review-title">Enjoying Rolesetu?</p>
      <p className="muted small">
        {helped} A quick rating on the Chrome Web Store helps other job seekers find it.
      </p>
      <div className="review-actions">
        <a
          className="btn primary"
          href={CHROME_REVIEW_URL}
          target="_blank"
          rel="noreferrer"
          onClick={() => answer('review', { name: 'thanks' })}
        >
          Rate Rolesetu
        </a>
        <button type="button" className="btn" onClick={() => answer('feedback', { name: 'better' })}>
          Could be better
        </button>
      </div>
      <button type="button" className="review-never" onClick={() => answer('never', { name: 'hidden' })}>
        Don't ask again
      </button>
    </section>
  );
}
