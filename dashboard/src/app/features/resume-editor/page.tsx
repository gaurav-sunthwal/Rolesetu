import { featureMetadata, FeaturePageView } from '@/components/landing/feature-page';

const SLUG = 'resume-editor';

export const metadata = featureMetadata(SLUG);

export default function Page() {
  return <FeaturePageView slug={SLUG} />;
}
