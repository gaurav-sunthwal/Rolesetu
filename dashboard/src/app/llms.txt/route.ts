import { FEATURE_PAGES, featurePath, HOME_FAQS } from '@/content/marketing';
import { absoluteUrl, SITE } from '@/lib/site';

/**
 * A plain-text summary of the product for AI assistants (the llms.txt
 * convention), written from the same content as the public pages.
 */
function body(): string {
  const features = FEATURE_PAGES.map(
    (page) => `- [${page.name}](${absoluteUrl(featurePath(page.slug))}): ${page.description}`,
  );
  const facts = FEATURE_PAGES.flatMap((page) => [
    `### ${page.name}`,
    '',
    page.intro,
    '',
    ...page.details.map((detail) => `- ${detail.title}: ${detail.body}`),
    '',
  ]);
  const questions = HOME_FAQS.flatMap((faq) => [`### ${faq.question}`, '', faq.answer, '']);

  return [
    `# ${SITE.name}`,
    '',
    `> ${SITE.description}`,
    '',
    `${SITE.name} is a web app with a Chrome extension for people applying to jobs. It is an assistant, not an auto-apply bot: it never submits an application, never sends an email, and never adds a skill to a resume that the user did not confirm.`,
    '',
    `Website: ${SITE.url}`,
    `Last updated: ${SITE.updated}`,
    '',
    '## Features',
    '',
    ...features,
    '',
    '## How each feature works',
    '',
    ...facts,
    '## Frequently asked questions',
    '',
    ...questions,
  ].join('\n');
}

export function GET() {
  return new Response(body(), {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=86400',
    },
  });
}
