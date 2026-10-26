import { ImageResponse } from 'next/og';

import { bandOf } from '@/features/matches/score';
import { getPublicShare, jobLine } from '@/features/share/public-share';
import { SITE } from '@/lib/site';

export const CARD_SIZE = { width: 1200, height: 630 };

// The brand colors from globals.css, as hex: the image renderer cannot read CSS variables.
const INK = '#14161d';
const MUTED = '#5b6070';
const LINE = '#e6e8ee';
const BAND_COLOR = { 'Strong fit': '#1f9254', 'Worth a shot': '#2f5bea', 'A stretch': '#c98a12' };
const RING = 260;
const STROKE = 26;

function Ring({ score, color }: { score: number; color: string }) {
  const radius = (RING - STROKE) / 2;
  const circumference = 2 * Math.PI * radius;
  return (
    <div style={{ position: 'relative', display: 'flex', width: RING, height: RING }}>
      <svg width={RING} height={RING} viewBox={`0 0 ${RING} ${RING}`}>
        <circle
          cx={RING / 2}
          cy={RING / 2}
          r={radius}
          fill="none"
          stroke={LINE}
          strokeWidth={STROKE}
        />
        <circle
          cx={RING / 2}
          cy={RING / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * circumference} ${circumference}`}
          transform={`rotate(-90 ${RING / 2} ${RING / 2})`}
        />
      </svg>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 84,
          fontWeight: 700,
          color: INK,
        }}
      >
        {score}
      </div>
    </div>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#ffffff',
        padding: '56px 72px',
        fontFamily: 'sans-serif',
      }}
    >
      <div style={{ display: 'flex', fontSize: 30, fontWeight: 700, color: INK }}>{SITE.name}</div>
      {children}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          borderTop: `2px solid ${LINE}`,
          paddingTop: 24,
          fontSize: 26,
          color: MUTED,
        }}
      >
        <span>Check your own fit for any job, free</span>
        <span style={{ color: INK, fontWeight: 600 }}>{new URL(SITE.url).host}</span>
      </div>
    </div>
  );
}

/** The picture shown when a shared score link is posted on a social network. */
export async function renderCardImage(slug: string): Promise<ImageResponse> {
  const lookup = await getPublicShare(slug);
  if (lookup.state !== 'found') {
    return new ImageResponse(
      <Frame>
        <div
          style={{
            display: 'flex',
            flex: 1,
            alignItems: 'center',
            fontSize: 72,
            fontWeight: 700,
            color: INK,
          }}
        >
          {SITE.tagline}
        </div>
      </Frame>,
      CARD_SIZE,
    );
  }

  const { card } = lookup;
  const band = bandOf(card.score);
  const color = BAND_COLOR[band.label as keyof typeof BAND_COLOR] ?? BAND_COLOR['Worth a shot'];
  const job = jobLine(card);
  return new ImageResponse(
    <Frame>
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', gap: 56 }}>
        <Ring score={card.score} color={color} />
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
          <div style={{ display: 'flex', fontSize: 30, fontWeight: 700, color }}>{band.label}</div>
          <div
            style={{
              display: 'flex',
              marginTop: 8,
              fontSize: job.length > 40 ? 48 : 58,
              fontWeight: 700,
              color: INK,
              lineHeight: 1.1,
            }}
          >
            {`${card.score}% match for ${job.length > 70 ? `${job.slice(0, 67)}…` : job}`}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 28 }}>
            {card.matched.slice(0, 5).map((skill) => (
              <div
                key={skill}
                style={{
                  display: 'flex',
                  padding: '8px 20px',
                  borderRadius: 999,
                  background: '#e3f4ea',
                  color: INK,
                  fontSize: 26,
                  fontWeight: 600,
                }}
              >
                {skill}
              </div>
            ))}
          </div>
        </div>
      </div>
    </Frame>,
    CARD_SIZE,
  );
}
