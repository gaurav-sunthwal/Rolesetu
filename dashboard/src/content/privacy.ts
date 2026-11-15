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
    title: 'The free job check on the home page',
    paragraphs: [
      'You can paste a job link on the home page without an account. We fetch that page and show what the job asks for. We keep the job we read, and a scrambled form of your IP address that cannot be turned back into the address, for one day. The first lets the same link be answered without fetching it again; the second limits how many links one visitor can look up. Both are then deleted.',
    ],
  },
  {
    title: 'The extension waiting list',
    paragraphs: [
      'If you ask to be told when the browser extension is released, we keep the email address you give us. We use it to confirm that you are on the list, and to send that one announcement. It is not added to any other list. To be taken off, write to the address below. A video on the home page is hosted by YouTube; nothing is loaded from YouTube until you press play.',
    ],
  },
  {
    title: 'What the browser extension does',
    paragraphs: [
      'The extension asks for access to every website because a job can be posted on any company’s own pages. On each page a small script checks, inside your browser, whether the page is a job listing or an application form. On any other page it does nothing and sends nothing.',
    ],
    items: [
      'On a job listing, it sends the job’s title, company, description and page address to Rolesetu so the job can be scored against your profile.',
      'On an application form, it fetches your profile and saved answers from Rolesetu and fills the empty fields. The extension never presses Submit.',
      'When you answer an application question we had no answer for, such as your notice period, expected salary, how you heard about the job, or a written question like “Why do you want to join us?”, the extension saves that answer to your saved answers so the next form that asks it, however it is worded, can be filled with it. In a written answer, the company’s and role’s names are replaced with placeholders so the next company’s names go in their place. It tells you each time and offers Undo, and you can change or delete these answers in your profile. It never saves passwords, identity or bank numbers, card details, or answers about race, ethnicity, religion, disability, health, veteran status, marital status or criminal record. Nothing else you type into a form is sent to us.',
      'When you press “Write with AI” or “Improve with AI” on a question, the question, the job you are applying to, the parts of your profile that matter for it, and (to improve it) what is in the box are sent to Rolesetu and to Google Gemini to write a draft. It only happens when you press the button. The draft is put in the box for you to read and change; the extension never submits it.',
      'When you apply to a job it scored, it records that job’s role, company and address in your tracker.',
      'It keeps one access key in the browser’s own storage so it can act for your account. Disconnecting the extension in Settings cancels that key.',
      'It records how it is used, so we can see what works and fix what does not: which features are used (for example “autofill filled 7 fields”, “an answer was saved”, “AI was asked”), on which site’s hostname (never the full address), the extension’s version, and its own errors. These records never contain page content, what you type, your answers or the jobs’ text, and are deleted after 90 days. You can switch this off in the extension’s popup, under Settings (the gear icon).',
      'Before you sign in, these records are kept under a random id the extension makes when it is installed, not under your name, so we can see where setting up goes wrong. With them we keep what the browser says about itself (its name and version, the operating system, its language and time zone) and whether it reports being run by automation. The setup pages on this website add which step you reached (page opened, sign-up started, signed in) and, if signing in failed, the error’s code; never your email or anything you type. Your IP address is not stored: only a one-way hash of it, used to limit how many installs one address can register. When you connect your account, these records join it. When the extension is removed, the browser opens a page that counts the removal and asks, optionally, why. Records not joined to an account are deleted 90 days after they were last updated. Switching analytics off (popup, then Settings) stops all of this.',
      'It does not collect your browsing history, does not read pages that are not job listings or application forms, and contains no advertising code.',
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
      'We may email the address on your account about Rolesetu itself, such as a new feature like the browser extension. Not often, and never on behalf of anyone else. Reply “stop” to any of these emails and we will not send you another.',
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
      'Vercel, which hosts this website and counts page visits for us (Vercel Analytics). It uses no cookies and does not identify you.',
      'Google Gemini, when a job check is read by an AI model, or when you ask the extension to write or improve an answer. The job description, the question and the parts of your profile needed are sent for that purpose.',
      'Context.dev, which loads a job page for us when the site does not let our own reader in. Only the job’s link is sent, never anything about you.',
      'Razorpay, when you buy Pro. Your card, UPI or bank details go to Razorpay only; Rolesetu keeps the order and payment ids, the amount, and the dates your Pro covers.',
      'Microsoft Clarity, which records visits to this website to show us where pages are confusing. The signed-in area that shows your resume, profile and emails is masked from those recordings.',
    ],
  },
  {
    title: 'Security',
    items: [
      'All traffic between your browser, the extension and Rolesetu is encrypted in transit.',
      'Gmail tokens are encrypted before they are stored.',
      'Only a hash of the extension’s access key is kept on the server.',
      'Every record is tied to your account, and no other user can read it.',
      'Rolesetu staff can open an account’s profile, job checks, applications and uploaded resume file when that is needed to give support or to act on a deletion request. Only the few accounts on Rolesetu’s admin list can do this. Nothing read from your Gmail is shown to them.',
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
