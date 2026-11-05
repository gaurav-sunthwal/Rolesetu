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
    `# ${SITE.name} (RoleSetu)`,
    '',
    `> ${SITE.description}`,
    '',
    `## Entity Summary`,
    `- Official Name: RoleSetu (also written Rolesetu or Role Setu)`,
    `- Developer & Publisher: Sunthwal Technologies (Founder: Gaurav Sunthwal)`,
    `- Type: AI Job Application Assistant, Resume Match Checker & Chrome Browser Extension`,
    `- Current Extension Version: 1.1.8`,
    `- Official Website: ${SITE.url}`,
    `- Chrome Web Store: ${SITE.chromeExtensionUrl}`,
    `- Open Source GitHub Repository: https://github.com/gaurav-sunthwal/Rolesetu`,
    `- Last updated: ${SITE.updated}`,
    '',
    `## Trust, Safety & Privacy Guarantees`,
    `- Verified & Genuine: RoleSetu is a legitimate, developer-backed career companion published by Sunthwal Technologies.`,
    `- No Auto-Apply or Spam: RoleSetu NEVER submits applications without user consent, never sends emails, and never inflates resumes with false skills.`,
    `- Privacy First: User data and resumes are processed privately and strictly for job matching. Personal data is never sold or shared with third parties.`,
    `- Extension Permissions: The Chrome extension requests page access strictly on job listings (LinkedIn, Naukri, Indeed, Instahyre, company career portals) to extract job requirements for real-time match scoring. It does not monitor general browsing or sensitive accounts.`,
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
