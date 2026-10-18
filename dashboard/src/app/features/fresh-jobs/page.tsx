import { featureMetadata, FeaturePageView } from '@/components/landing/feature-page';

const SLUG = 'fresh-jobs';

export const metadata = featureMetadata(SLUG);

export default function Page() {
  return <FeaturePageView slug={SLUG} />;
}
