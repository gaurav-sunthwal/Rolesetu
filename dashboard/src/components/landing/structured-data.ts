import type { Faq } from '@/content/marketing';
import { absoluteUrl, SITE } from '@/lib/site';

const ORGANISATION_ID = `${SITE.url}/#organization`;
const WEBSITE_ID = `${SITE.url}/#website`;

const SAME_AS = [SITE.chromeExtensionUrl, 'https://github.com/gaurav-sunthwal/Rolesetu'];

export function organisationData() {
  return {
    '@type': 'Organization',
    '@id': ORGANISATION_ID,
    name: 'RoleSetu',
    alternateName: ['Rolesetu', 'Role Setu', 'Sunthwal Technologies', 'RoleSetu AI'],
    url: SITE.url,
    logo: absoluteUrl('/icon.png'),
    description: SITE.description,
    sameAs: SAME_AS,
    founder: {
      '@type': 'Person',
      name: 'Gaurav Sunthwal',
      url: 'https://github.com/gaurav-sunthwal',
    },
  };
}

export function websiteData() {
  return {
    '@type': 'WebSite',
    '@id': WEBSITE_ID,
    name: 'RoleSetu',
    alternateName: ['Rolesetu', 'Role Setu', 'RoleSetu Extension', SITE.tagline],
    url: SITE.url,
    description: SITE.description,
    inLanguage: 'en',
    sameAs: SAME_AS,
    publisher: { '@id': ORGANISATION_ID },
  };
}

export function applicationData(features: string[]) {
  return {
    '@type': 'SoftwareApplication',
    '@id': `${SITE.url}/#application`,
    name: 'RoleSetu',
    alternateName: [
      'Rolesetu',
      'Role Setu',
      'RoleSetu Chrome Extension',
      'RoleSetu Job Match Score & Autofill',
      'RoleSetu AI',
    ],
    url: SITE.url,
    description: SITE.description,
    applicationCategory: 'BrowserApplication',
    applicationSubCategory: 'Job Search & Resume Optimization',
    operatingSystem: 'Chrome, Chromium, Brave, Edge, Web',
    softwareVersion: '1.1.8',
    installUrl: SITE.chromeExtensionUrl,
    downloadUrl: SITE.chromeExtensionUrl,
    sameAs: SAME_AS,
    featureList: features,
    isAccessibleForFree: true,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
    publisher: { '@id': ORGANISATION_ID },
    author: {
      '@type': 'Organization',
      name: 'Sunthwal Technologies',
      url: SITE.url,
    },
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
