import type { Faq } from '@/content/marketing';
import { absoluteUrl, SITE } from '@/lib/site';

const ORGANISATION_ID = `${SITE.url}/#organization`;
const WEBSITE_ID = `${SITE.url}/#website`;

export function organisationData() {
  return {
    '@type': 'Organization',
    '@id': ORGANISATION_ID,
    name: SITE.name,
    url: SITE.url,
    logo: absoluteUrl('/icon.png'),
    description: SITE.description,
  };
}

export function websiteData() {
  return {
    '@type': 'WebSite',
    '@id': WEBSITE_ID,
    name: SITE.name,
    alternateName: ['Role Setu', SITE.tagline],
    url: SITE.url,
    description: SITE.description,
    inLanguage: 'en',
    publisher: { '@id': ORGANISATION_ID },
  };
}

export function applicationData(features: string[]) {
  return {
    '@type': 'SoftwareApplication',
    '@id': `${SITE.url}/#application`,
    name: SITE.name,
    url: SITE.url,
    description: SITE.description,
    applicationCategory: 'BusinessApplication',
    applicationSubCategory: 'Job search',
    operatingSystem: 'Web, Chrome',
    installUrl: SITE.chromeExtensionUrl,
    downloadUrl: SITE.chromeExtensionUrl,
    featureList: features,
    isAccessibleForFree: true,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
    publisher: { '@id': ORGANISATION_ID },
  };
}

export function faqData(faqs: readonly Faq[]) {
  return {
    '@type': 'FAQPage',
    mainEntity: faqs.map((faq) => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: { '@type': 'Answer', text: faq.answer },
    })),
  };
}

export function breadcrumbData(trail: { name: string; path: string }[]) {
  return {
    '@type': 'BreadcrumbList',
    itemListElement: trail.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}

export function graph(...nodes: Record<string, unknown>[]) {
  return { '@context': 'https://schema.org', '@graph': nodes };
}
