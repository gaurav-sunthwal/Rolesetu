/**
 * The privacy policy, kept as data like the rest of the public pages. Every
 * statement here describes what the code does today: change the code and this
 * together, and bump SITE.updated.
 */

export type PolicySection = {
  title: string;
  paragraphs?: string[];
  items?: string[];
};

export const PRIVACY_INTRO =
  'Rolesetu is a web app and a Chrome extension that help you decide which jobs to apply to and apply to them faster. This page says what data they handle, why, where it is kept, and how you remove it.';

export const PRIVACY_SECTIONS: PolicySection[] = [
  {
    title: 'What you give us',
    items: [
      'Your account: the name and email address from your Google or email sign-in.',
      'Your resume: the PDF you upload, and the profile read from it (skills, experience, education, projects, links, location), which you can edit.',
      'Saved answers: what you choose to store for common application questions, such as notice period or expected salary.',
      'Job checks: the description, link, role and company of each job you check, with the score and the skill-by-skill result.',
      'Applications: the jobs you track, their status and your notes.',
    ],
  },
  {
    title: 'What the browser extension does',
    paragraphs: [
      'The extension asks for access to every website because a job can be posted on any company’s own pages. On each page a small script checks, inside your browser, whether the page is a job listing or an application form. On any other page it does nothing and sends nothing.',
    ],
    items: [
      'On a job listing, it sends the job’s title, company, description and page address to Rolesetu so the job can be scored against your profile.',
      'On an application form, it fetches your profile and saved answers from Rolesetu and fills the empty fields. What you type into a form is not sent to us, and the extension never presses Submit.',
      'When you apply to a job it scored, it records that job’s role, company and address in your tracker.',
      'It keeps one access key in the browser’s own storage so it can act for your account. Disconnecting the extension in Settings cancels that key.',
      'It does not collect your browsing history, does not read pages that are not job listings or application forms, and contains no analytics or advertising code.',
    ],
  },
  {
    title: 'Gmail, if you connect it',
    paragraphs: [
      'Connecting Gmail is optional. Rolesetu asks for read-only access and looks only at mail that matches a job-related search. A message is read in memory to work out whether it is a confirmation, a rejection, an interview or an offer. We store the sender, subject, date, that classification, and the company and role it refers to. We do not store message bodies, and mail that is not about a job application is not stored at all. You can disconnect Gmail in Settings at any time.',
      'Rolesetu’s use of information received from Google APIs adheres to the Google API Services User Data Policy, including the Limited Use requirements.',
    ],
  },
  {
    title: 'How your data is used',
    items: [
      'Only to provide the product: scoring jobs, preparing your resume, filling forms and keeping your tracker current.',
      'We do not sell your data or share it with advertisers or data brokers.',
      'We do not use it to decide creditworthiness or for lending.',
      'We do not use it for anything unrelated to helping you apply for jobs.',
    ],
  },
  {
    title: 'Who else handles it',
    paragraphs: ['Rolesetu runs on services from other companies, which process data for us:'],
    items: [
      'Google Firebase, for sign-in.',
      'Railway, which hosts the API, and a managed PostgreSQL database, which holds your account data.',
      'Cloudflare R2, which stores resume files privately. They are served only through short-lived links.',
      'Vercel, which hosts this website.',
      'Google Gemini, when a job check is read by an AI model. The job description and the parts of your profile needed to judge it are sent for that purpose. If you add your own Gemini key in Settings, it is stored encrypted.',
      'Microsoft Clarity, which records visits to this website to show us where pages are confusing. The signed-in area that shows your resume, profile and emails is masked from those recordings.',
    ],
  },
  {
    title: 'Security',
    items: [
      'All traffic between your browser, the extension and Rolesetu is encrypted in transit.',
      'Gmail tokens and API keys are encrypted before they are stored.',
      'Only a hash of the extension’s access key is kept on the server.',
      'Every record is tied to your account and can be read only by you.',
    ],
  },
  {
    title: 'Keeping, exporting and deleting',
    items: [
      'Your data is kept for as long as you have an account.',
      'You can download your profile, saved answers, applications and recent job checks as one file from Settings.',
      'You can delete your resume, saved answers and applications, and disconnect Gmail or the extension, from inside the app.',
      'To delete your account and everything held about you, write to the address below from the email you signed up with. We will delete it within 30 days.',
    ],
  },
  {
    title: 'Changes to this policy',
    paragraphs: [
      'If the way Rolesetu handles your data changes, this page changes first and the date at the top is updated.',
    ],
  },
];
