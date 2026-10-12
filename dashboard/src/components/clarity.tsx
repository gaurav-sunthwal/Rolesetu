import Script from 'next/script';
import { z } from 'zod';

// Letters and digits only, so the value is safe to place inside the script below.
const projectId = z
  .string()
  .regex(/^[a-z0-9]+$/)
  .optional()
  .parse(process.env.NEXT_PUBLIC_CLARITY_PROJECT_ID || undefined);

/**
 * Microsoft Clarity (visit recordings and heatmaps). Loaded only where a
 * project id is set, so local development is not recorded.
 */
export function Clarity() {
  if (!projectId) return null;
  return (
    // Not id="clarity": a browser exposes an element's id as a global of the same
    // name, which would put this <script> where Clarity expects its own function.
    <Script id="ms-clarity-loader" strategy="afterInteractive">
      {`(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","${projectId}");`}
    </Script>
  );
}
