import { featureMetadata, FeaturePageView } from '@/components/landing/feature-page';

const SLUG = 'job-application-tracker';

export const metadata = featureMetadata(SLUG);

export default function Page() {
  return <FeaturePageView slug={SLUG} />;
}
