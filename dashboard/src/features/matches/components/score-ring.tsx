import { bandOf } from '@/features/matches/score';
import { cn } from '@/lib/utils';

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function ScoreRing({
  score,
  className,
  draw = false,
}: {
  score: number;
  className?: string;
  /** Draws the ring from empty when it first appears. */
  draw?: boolean;
}) {
  const band = bandOf(score);
  return (
    <div
      className={cn('relative size-36 shrink-0', className)}
      role="img"
      aria-label={`Match score ${score} out of 100: ${band.label}`}
    >
      <svg viewBox="0 0 120 120" className="size-full -rotate-90">
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          fill="none"
          strokeWidth="10"
          className="stroke-secondary"
        />
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - score / 100)}
          style={{ '--ring-length': CIRCUMFERENCE } as React.CSSProperties}
          className={cn(
            draw && 'ring-draw',
            'transition-[stroke-dashoffset] duration-700 motion-reduce:transition-none',
            band.stroke,
          )}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-bold tracking-tight tabular-nums">{score}</span>
        <span className="text-muted-foreground text-xs">out of 100</span>
      </div>
    </div>
  );
}
