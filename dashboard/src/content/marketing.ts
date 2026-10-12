/**
 * The words on the public pages. Kept as data so the page a visitor reads, the
 * structured data a search engine reads and the summary an AI assistant reads
 * (/llms.txt) always say the same thing.
 */

export type Faq = { question: string; answer: string };

export type FeaturePage = {
  slug: string;
  /** Short name, used in menus and cards. */
  name: string;
  /** One line for cards and link lists. */
  summary: string;
  /** Browser tab and search result title. */
  title: string;
  /** Search result description. */
  description: string;
  heading: string;
  intro: string;
  steps: { title: string; body: string }[];
  details: { title: string; body: string }[];
  faqs: Faq[];
};

export const FEATURE_PAGES: FeaturePage[] = [
  {
    slug: 'job-match-score',
    name: 'Job match score',
    summary: 'Check your resume against any job description and see your fit skill by skill.',
    title: 'Job match score: check your resume against any job description',
    description:
      'Paste a job link or description and get a match score out of 100. Every required skill is marked strong, partial or missing, with the line from your resume that proves it.',
    heading: 'A job match score you can check line by line',
    intro:
      'Rolesetu compares a job description with your resume and gives you a score out of 100. It is not a black box: every skill the job asks for is listed with a verdict and the exact part of your profile it came from, so you know whether a job is worth applying to before you spend an hour on it.',
    steps: [
      {
        title: 'Upload your resume once',
        body: 'A PDF up to 5 MB. Rolesetu reads it into a profile of your skills, experience, education and projects, which you can review and correct.',
      },
      {
        title: 'Paste a job link or the description',
        body: 'Give the link to the listing, or paste the full job description. The role, company, location and salary are read from the page when they are there.',
      },
      {
        title: 'Read your score and your gaps',
        body: 'You get the score, a verdict for each skill, the years of experience the job asks for against what you have, and the skills you are missing.',
      },
    ],
    details: [
      {
        title: 'Strong, partial or missing',
        body: 'Each skill is judged against your profile. Strong means a role or project of yours uses it. Partial means you show a close substitute. Missing means nothing on your profile supports it.',
      },
      {
        title: 'The number is arithmetic',
        body: 'Required skills count double, nice-to-have skills count once, and a partial match earns half. The score is those points added up, so you can work it out yourself.',
      },
      {
        title: 'Experience is checked too',
        body: 'If a job asks for more years than your resume shows, the score is capped and the result says how far short you are, instead of hiding it behind a good skills match.',
      },
      {
        title: 'Results in seconds',
        body: 'Job checks do not wait on an AI model, so the score is ready almost as soon as you ask for it. The same job is not scored twice unless your profile changes.',
      },
    ],
    faqs: [
      {
        question: 'How is the job match score calculated?',
        answer:
          'Every skill in the job description is marked strong, partial or missing against your profile. A required skill is worth 2 points and a nice-to-have skill 1 point; a partial match earns half. The score is the points you earned divided by the points available, as a number out of 100.',
      },
      {
        question: 'Is the score the same thing as an ATS score?',
        answer:
          'No. Each applicant tracking system is set up differently by the employer and none of them publish a score. Rolesetu shows how well the experience on your resume covers what the job asks for, which is the thing a recruiter or a keyword filter is looking for.',
      },
      {
        question: 'Can I check a job without the browser extension?',
        answer:
          'Yes. Paste the link to the job or the full description in the dashboard. The extension only saves you that step by showing the score on the job page itself.',
      },
    ],
  },
  {
    slug: 'resume-keyword-match',
    name: 'Resume keyword match',
    summary: 'Put the job’s wording into your own resume PDF. Fonts and layout stay as they were.',
    title: 'Tailor your resume to a job description without changing its design',
    description:
      'See which keywords from a job description are missing from your resume or written differently. Tick the ones that are true and Rolesetu edits your own PDF in place, in the same fonts and layout.',
    heading: 'Tailor your resume to the job, and keep it your resume',
    intro:
      'Recruiters and keyword filters look for the job’s own words. Rolesetu compares a job description with your resume, shows what is missing or spelled differently, and adds what you confirm to the PDF you uploaded. Nothing is rebuilt from a template, so the result looks exactly like the resume you made.',
    steps: [
      {
        title: 'Check a job',
        body: 'The job’s title and skills are compared with the words that are actually on your resume.',
      },
      {
        title: 'Tick what is true',
        body: 'Missing skills you really have, skills written differently from the job (“Postgres” and “PostgreSQL”), and a headline that matches the role.',
      },
      {
        title: 'Preview, then download',
        body: 'You see the original and the updated page side by side with every change listed. Download the copy for this job, or keep it as your saved resume.',
      },
    ],
    details: [
      {
        title: 'Your own file, edited in place',
        body: 'New skills continue the right row of your Skills section in that line’s own font, size and colour. If a line is full, the content below moves down by one line. Text is never shrunk or squeezed.',
      },
      {
        title: 'Only skills you confirm',
        body: 'Rolesetu never adds a skill by itself. It suggests the job’s keywords and you tick the ones you have. A skill that does not fit on the page is reported as not added.',
      },
      {
        title: 'Your history is never edited',
        body: 'Job titles you held, employers and dates are left alone. A suggested headline stays within the same kind of role and never adds seniority your resume does not already claim.',
      },
      {
        title: 'Still readable by job sites',
        body: 'After each change the file is read back the way a job site’s parser would read it, to confirm every added skill can be found.',
      },
    ],
    faqs: [
      {
        question: 'Will tailoring change how my resume looks?',
        answer:
          'No. Rolesetu edits the PDF you uploaded instead of generating a new document. Fonts, spacing, colours and layout stay the same, and only the words listed in the preview change.',
      },
      {
        question: 'Does Rolesetu invent skills or experience to match the job?',
        answer:
          'No. It only adds skills you tick yourself, and it never changes the job titles you held, your employers or your dates.',
      },
      {
        question: 'Which resumes can be edited?',
        answer:
          'Text PDFs with a Skills section that lists skills in rows, such as “Languages: Python, SQL”. Scanned resumes and Skills sections with one skill per line are not supported yet, and Rolesetu tells you when that is the case.',
      },
      {
        question: 'Is the tailored resume stored?',
        answer:
          'Not unless you choose to keep it. The updated file is handed back to your browser for you to download. “Save as my resume” replaces your stored resume with it.',
      },
    ],
  },
  {
    slug: 'autofill-job-applications',
    name: 'Autofill applications',
    summary: 'Fill application forms from your profile and saved answers. You press submit.',
    title: 'Autofill job applications from your resume profile',
    description:
      'The Rolesetu browser extension fills job application forms with your details, work history, education and saved answers. It only fills empty fields and never submits for you.',
    heading: 'Autofill job applications, and stay in control of them',
    intro:
      'Most application forms ask for the same things your resume already says. The Rolesetu extension recognises an application form, offers to fill it from your profile, and outlines every field it filled so you can check the form before you send it yourself.',
    steps: [
      {
        title: 'Open an application form',
        body: 'The extension notices the form and shows a small card saying how many fields it can fill.',
      },
      {
        title: 'Press Autofill',
        body: 'Your name, contact details, work history, education and saved answers are typed into the matching fields.',
      },
      {
        title: 'Check it and submit',
        body: 'Filled fields are outlined so you can review them. Add anything that is missing and press the site’s own Submit button.',
      },
    ],
    details: [
      {
        title: 'Saved answers',
        body: 'Answer the questions most forms repeat once: notice period, current and expected salary, relocation, work authorisation and why you are looking. They are reused on every form.',
      },
      {
        title: 'Only empty fields',
        body: 'Anything you have already typed is left alone. Autofill never replaces your own words.',
      },
      {
        title: 'Never submits',
        body: 'The extension never clicks a button on the page. Sending an application is always your own action.',
      },
      {
        title: 'Multi-step forms',
        body: 'When the next step of an application appears without a page reload, the form is read again and the offer to fill it comes back.',
      },
    ],
    faqs: [
      {
        question: 'Does Rolesetu apply to jobs automatically?',
        answer:
          'No. Rolesetu fills in forms and prepares your resume, but it never submits an application or sends an email. You review everything and press submit yourself.',
      },
      {
        question: 'Which fields can it fill?',
        answer:
          'Name, email, phone, location, links, each job’s title, employer, dates and description, education, total years of experience, and the saved answers you have written.',
      },
      {
        question: 'Which browsers are supported?',
        answer:
          'The extension is built for Chrome and other Chromium browsers. The dashboard works in any modern browser.',
      },
    ],
  },
  {
    slug: 'job-application-tracker',
    name: 'Application tracker',
    summary: 'Every job you apply to in one list that keeps itself up to date.',
    title: 'Job application tracker that updates itself',
    description:
      'Track every job application in one place. Rolesetu saves a job when you press Apply, marks it as applied when the site confirms, and moves it forward when a recruiter replies.',
    heading: 'A job application tracker you do not have to fill in',
    intro:
      'Spreadsheets go stale because updating them is a chore. Rolesetu keeps the list for you: the extension adds a job when you start applying and marks it as applied when the site says the application went through, with the match score it had at the time.',
    steps: [
      {
        title: 'Press Apply as usual',
        body: 'The job is saved to your tracker straight away, so it is not lost if you never finish the form.',
      },
      {
        title: 'The site confirms',
        body: 'When the page says your application was received, the job is marked as applied. If you applied on another site, Rolesetu asks you when you come back.',
      },
      {
        title: 'Follow it to the end',
        body: 'Each application moves through saved, applied, replied, interview, offer and rejected, by hand or from your job emails.',
      },
    ],
    details: [
      {
        title: 'Score kept with the job',
        body: 'Each tracked job keeps its match score and the skills it asked for, so you can see later which kinds of job moved forward.',
      },
      {
        title: 'Add jobs yourself',
        body: 'Applied by email or through a referral? Add the role, company, link, contact and notes in the dashboard.',
      },
      {
        title: 'A history for each application',
        body: 'Every status change is recorded with when it happened and whether you, the extension or an email made it.',
      },
      {
        title: 'Your data is yours',
        body: 'Download your profile, saved answers, applications and recent job checks as one file at any time.',
      },
    ],
    faqs: [
      {
        question: 'How does Rolesetu know I applied?',
        answer:
          'The browser extension watches the job page for the Apply or Submit button you press and for the site’s own confirmation message. It only watches; it never clicks anything for you.',
      },
      {
        question: 'Can I track jobs I applied to somewhere else?',
        answer:
          'Yes. Add any application by hand in the dashboard, or connect Gmail so that confirmation emails add it for you.',
      },
    ],
  },
  {
    slug: 'job-email-tracker',
    name: 'Gmail job tracking',
    summary: 'Interview invites, rejections and offers in Gmail update your tracker for you.',
    title: 'Track job application emails in Gmail: interviews, rejections and offers',
    description:
      'Connect Gmail with read-only access and Rolesetu finds your job emails, updates each application’s status, and lists upcoming interviews. Only the sender, subject and date are stored.',
    heading: 'Let your inbox update your job tracker',
    intro:
      'Replies to job applications arrive between everything else in your inbox. With read-only Gmail access, Rolesetu picks out the mails about your applications, works out what each one means, and updates the matching application so nothing goes quiet unnoticed.',
    steps: [
      {
        title: 'Connect Gmail',
        body: 'You grant read-only access through Google’s own sign-in screen. Rolesetu cannot send, delete or change mail.',
      },
      {
        title: 'Job mails are recognised',
        body: 'Each one is sorted as an application received, a rejection, an interview, an assessment or an offer, and linked to the application it belongs to.',
      },
      {
        title: 'Your tracker moves',
        body: 'The application’s status changes to match, and interviews appear in a list with their date and time.',
      },
    ],
    details: [
      {
        title: 'Only three facts are kept',
        body: 'The sender, the subject and the date. The body of a mail is read to decide what it is and then dropped; it is never stored.',
      },
      {
        title: 'Interviews with a time',
        body: 'The time is taken from the calendar invite attached to the mail, or from its wording. You can add it to Google Calendar or download it for Apple Calendar and Outlook.',
      },
      {
        title: 'What your rejections have in common',
        body: 'Rejection mails rarely say why. Rolesetu looks at what those jobs asked for that your profile did not show, and tells you which skills keep coming up missing.',
      },
      {
        title: 'Disconnect whenever you like',
        body: 'Disconnecting stops the reading and deletes the mail records that were kept. Your applications stay as they are.',
      },
    ],
    faqs: [
      {
        question: 'Does Rolesetu read all my email?',
        answer:
          'It looks for mail about job applications, from hiring systems and job boards and with hiring wording. For those mails it stores only the sender, subject, date and what kind of mail it is. Mail bodies are never stored.',
      },
      {
        question: 'Can Rolesetu send email from my account?',
        answer: 'No. The Gmail permission is read-only, and Rolesetu never sends an email for you.',
      },
    ],
  },
  {
    slug: 'job-search-extension',
    name: 'Browser extension',
    summary:
      'Your match score beside the Apply button on LinkedIn, Naukri, Indeed and career pages.',
    title: 'Job match score on LinkedIn, Naukri, Indeed and company career pages',
    description:
      'The Rolesetu Chrome extension shows how well you fit a job right on the job page, beside the Apply button, then helps you tailor your resume, autofill the form and track the application.',
    heading: 'See your match score on the job page itself',
    intro:
      'You should not have to copy a job description into another tab to know whether to apply. The Rolesetu extension reads the job you are looking at and puts your match score beside the Apply button, on the big job boards and on companies’ own career pages.',
    steps: [
      {
        title: 'Connect the extension',
        body: 'Install it, then press “Connect extension” in your Rolesetu settings. No password is typed into the extension.',
      },
      {
        title: 'Open any job',
        body: 'Your score appears beside the page’s Apply button, or in the corner when there is none.',
      },
      {
        title: 'Click the score',
        body: 'A side panel shows each skill’s verdict, the experience check, and the keywords to add to your resume for this job.',
      },
    ],
    details: [
      {
        title: 'Where it works',
        body: 'LinkedIn, Naukri and Indeed are read directly. Any other site that publishes standard job posting data, which most company career pages and hiring systems do, works as well.',
      },
      {
        title: 'Check a page it missed',
        body: 'If a job page was not recognised, open the extension and press “Check this page”.',
      },
      {
        title: 'Light on the page',
        body: 'One small script decides whether a page is a job. Nothing else loads and nothing is sent anywhere until a job is found.',
      },
      {
        title: 'Everything in one place',
        body: 'Tailor your resume, autofill the form and track the application without leaving the job page.',
      },
    ],
    faqs: [
      {
        question: 'Which job sites does the extension work on?',
        answer:
          'LinkedIn, Naukri and Indeed are supported directly, along with company career pages and hiring systems that publish standard job posting data. On any other page you can press “Check this page”, or paste the job link in the dashboard.',
      },
      {
        question: 'Why does the extension ask for access to every website?',
        answer:
          'A job can be posted on any company’s own website. The extension sends nothing from a page unless it has found a job there.',
      },
    ],
  },
];

export const HOME_FAQS: Faq[] = [
  {
    question: 'What is Rolesetu?',
    answer:
      'Rolesetu is a job application assistant. It scores a job description against your resume skill by skill, adds the job’s keywords to your own resume PDF, autofills application forms from your profile, and tracks every application, including the replies that arrive in Gmail.',
  },
  {
    question: 'How is the job match score calculated?',
    answer:
      'Each skill the job asks for is marked strong, partial or missing against your profile, with the line that proves it. Required skills count double and a partial match earns half. The score out of 100 is plain arithmetic on those verdicts, and it is capped when the job asks for more years of experience than you have.',
  },
  {
    question: 'Does Rolesetu apply to jobs for me?',
    answer:
      'No. Rolesetu never submits an application and never sends an email. It fills forms and prepares your resume, and you review and send everything yourself.',
  },
  {
    question: 'Will it add skills I do not have to my resume?',
    answer:
      'No. Rolesetu shows which of the job’s keywords are missing from your resume and you tick only the ones that are true. It never changes the job titles you held, your employers or your dates.',
  },
  {
    question: 'Which job sites does Rolesetu work with?',
    answer:
      'The browser extension reads jobs on LinkedIn, Naukri, Indeed and company career pages that publish standard job posting data. For a job anywhere else, paste its link or its description into the dashboard.',
  },
  {
    question: 'What happens to my resume and my data?',
    answer:
      'Your resume is stored privately and used only to build your profile and score jobs. A tailored resume is not stored unless you choose to keep it. Gmail access is read-only and only the sender, subject and date of job emails are kept. You can download everything Rolesetu holds about you as one file.',
  },
  {
    question: 'Do I need an AI subscription or an API key?',
    answer:
      'No. Reading your resume and checking jobs do not need an AI model, so there is no key to set up and no waiting.',
  },
  {
    question: 'Is Rolesetu free?',
    answer:
      'Yes. Rolesetu is free to use today: create an account, upload your resume and check a job.',
  },
];

export function featurePage(slug: string): FeaturePage {
  const page = FEATURE_PAGES.find((item) => item.slug === slug);
  if (!page) throw new Error(`No feature page called "${slug}"`);
  return page;
}

export function featurePath(slug: string): string {
  return `/features/${slug}`;
}
