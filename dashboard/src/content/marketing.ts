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
    title: 'Job match score: compare your resume to any job',
    description:
      'Paste a job link and get a match score out of 100. Each skill is marked strong, partial or missing, with the resume line that proves it.',
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
    title: 'Tailor your resume to a job description',
    description:
      'See which job keywords your resume is missing. Tick the ones that are true and Rolesetu edits your own PDF in place, in the same fonts and layout.',
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
    slug: 'resume-editor',
    name: 'Resume editor and AI',
    summary: 'Change any line of your resume, or ask the AI in plain words. Your design stays.',
    title: 'Edit your resume PDF online, with AI help',
    description:
      'Edit any line of your resume PDF and see it redrawn live in its own fonts and layout. Or ask the AI assistant, which never makes things up.',
    heading: 'Edit any line of your resume, or just ask',
    intro:
      'Most resume editors make you start again in their template. Rolesetu edits the PDF you already have. Change a bullet, fix a date, add a project or remove an old role, and the page is redrawn in its own fonts as you type. Or tell the assistant what you want in plain words and it makes the edits for you, using only what is in your resume and profile.',
    steps: [
      {
        title: 'Open the editor',
        body: 'Your resume is shown as its own page, with every line grouped under its heading: name and contact, experience, projects, education, skills.',
      },
      {
        title: 'Edit, or ask',
        body: 'Click any line to change it, press Enter to add a line below, or ask the assistant: “Add my Rolesetu project”, “Put Docker in my skills”, “Remove my school”.',
      },
      {
        title: 'Check the page, then save',
        body: 'The preview is your own PDF, redrawn after every change. Download it, or save it as your resume so job checks and autofill use it.',
      },
    ],
    details: [
      {
        title: 'Your design, untouched',
        body: 'Changed words are written in the line’s own font, size and colour. A new bullet copies the bullets around it; a new project title looks like your other titles. Removing a line closes the gap, as a word processor would.',
      },
      {
        title: 'Links keep working',
        body: 'Your LinkedIn, GitHub and project links are shown under their lines and can be changed. When you edit a link’s words, the link moves with them, and an address you type into a new line becomes a link.',
      },
      {
        title: 'An assistant that does not make things up',
        body: 'It reads your resume and profile and edits only the lines you ask about. A skill, number or address in its wording that you never gave is held back until you say it is true. It asks when it does not know.',
      },
      {
        title: 'Nothing changes until you save',
        body: 'Every edit, yours or the assistant’s, is a draft you can undo. Your saved resume is replaced only when you press Save and confirm.',
      },
    ],
    faqs: [
      {
        question: 'Will editing change how my resume looks?',
        answer:
          'No. Rolesetu edits the PDF you uploaded instead of rebuilding it from a template. Only the words you change are different; fonts, spacing, colours and links stay as they were.',
      },
      {
        question: 'Does the AI assistant need my own AI key?',
        answer:
          'No. It works without one. If you add your own Gemini key in Settings, the assistant uses your key first and Rolesetu’s only if yours cannot answer.',
      },
      {
        question: 'Can the AI add experience I do not have?',
        answer:
          'It is told never to, and the edits are checked: a skill, number or link that appears nowhere in your messages, resume or profile is held back and shown to you, not added. When you ask for something it knows nothing about, it asks you for the details.',
      },
      {
        question: 'Which resumes can be edited?',
        answer:
          'Resumes saved as text PDFs, which is what most resume tools and word processors export. Scanned resumes cannot be edited. On pages laid out in two columns you can change and remove lines, but not add new ones yet.',
      },
    ],
  },
  {
    slug: 'fresh-jobs',
    name: 'Fresh jobs',
    summary: 'Jobs in India posted this week on top companies’ own careers sites, picked for you.',
    title: 'Fresh jobs in India from company career pages',
    description:
      'Jobs in India posted in the last 7 days on careers sites like Google, Microsoft and Atlassian, matched to your experience and scored against your resume.',
    heading: 'This week’s jobs, straight from company careers sites',
    intro:
      'Job boards are full of reposts and listings that closed weeks ago. Rolesetu reads companies’ own careers sites every morning and shows the jobs in India posted in the last 7 days: only the ones that fit your experience, each with a match score.',
    steps: [
      {
        title: 'Read every morning',
        body: 'Each company’s careers site is read where the company publishes its jobs: Workday, Greenhouse, Lever, Ashby, SmartRecruiters or the company’s own site.',
      },
      {
        title: 'Picked for your experience',
        body: 'A job that asks for what you have is marked as a fit. One that asks for a year more is shown as a stretch. Roles far above or below your level are left out.',
      },
      {
        title: 'Scored, then one click to apply',
        body: 'Each job gets the same skill-by-skill match score as any job check. Open it on the company’s own site to apply, with the extension there to help.',
      },
    ],
    details: [
      {
        title: 'Only the last 7 days',
        body: 'Every job shows when it was posted. Nothing older than a week is listed.',
      },
      {
        title: 'Companies you choose',
        body: 'Follow all of them, or pick the companies and cities you care about. The choice stays on your device.',
      },
      {
        title: 'Honest about experience',
        body: 'A stretch is always labelled as one. A job that asks for much more than you have is not shown.',
      },
      {
        title: 'No AI key needed',
        body: 'Picking and scoring jobs runs without an AI model, so the list is ready the moment you open it.',
      },
    ],
    faqs: [
      {
        question: 'Where do the fresh jobs come from?',
        answer:
          'From each company’s own careers site, read every morning: more than 50 companies today, including Google, Microsoft, Amazon, Atlassian, NVIDIA and Freshworks. Only jobs in India are listed for now.',
      },
      {
        question: 'Why am I not shown some jobs?',
        answer:
          'Jobs that ask for well over your years of experience, or are aimed far below your level, are left out. A job asking for one year more than you have is shown, labelled as a stretch.',
      },
      {
        question: 'Do I need to upload a resume?',
        answer:
          'Yes. The list is picked for your experience and scored against your skills, so it needs your profile.',
      },
    ],
  },
  {
    slug: 'autofill-job-applications',
    name: 'Autofill applications',
    summary: 'Fill application forms from your profile and saved answers. You press submit.',
    title: 'Autofill job applications from your resume profile',
    description:
      'The Rolesetu extension fills job application forms with your details, work history and saved answers. It only fills empty fields and never submits.',
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
        title: 'Saved answers that learn',
        body: 'Answer the questions most forms repeat once: notice period, salary, relocation, work authorisation. When you type an answer autofill had nothing for, like your date of birth, it is saved for the next form, with dates in each form’s own format. You can change or remove any of them on your Profile.',
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
      'Track every job application in one place. Rolesetu saves a job when you press Apply and updates it when the site confirms or a recruiter replies.',
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
    title: 'Job application email tracker for Gmail',
    description:
      'Connect Gmail read-only and Rolesetu finds your job emails, updates each application’s status and lists interviews. Only sender, subject and date are kept.',
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
    title: 'Job match score on LinkedIn, Naukri and Indeed',
    description:
      'The Rolesetu Chrome extension shows your fit beside the Apply button, then helps you tailor your resume, autofill the form and track the application.',
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
      'Rolesetu is a job application assistant. It finds fresh jobs in India on company careers sites, scores any job against your resume skill by skill, lets you edit your own resume PDF directly or with an AI assistant, autofills application forms from your profile, and tracks every application, including the replies that arrive in Gmail.',
  },
  {
    question: 'Can I check a job without creating an account?',
    answer:
      'Yes. Paste a job link on the Rolesetu home page and it reads the listing and shows the role, the pay and every skill the job asks for, free and without signing in. To get your own match score you sign in and add your resume, because the score compares the job with your experience.',
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
    question: 'Can I edit my resume in Rolesetu?',
    answer:
      'Yes. The resume editor lets you change, remove or add any line of the PDF you uploaded and shows it redrawn live, in its own fonts and layout, with its links still working. You can also ask the AI assistant in plain words, such as “add my Rolesetu project”, and review its edits before you save.',
  },
  {
    question: 'Will it add skills I do not have to my resume?',
    answer:
      'No. Rolesetu shows which of the job’s keywords are missing from your resume and you tick only the ones that are true. The resume assistant holds back any skill, number or link you never gave until you confirm it, and nothing changes your job titles, employers or dates unless you ask.',
  },
  {
    question: 'Which job sites does Rolesetu work with?',
    answer:
      'The browser extension reads jobs on LinkedIn, Naukri, Indeed, Internshala and company career pages that publish standard job posting data, including jobs opened in a pop-up. Fresh jobs come straight from more than 50 companies’ careers sites. For a job anywhere else, paste its link or its description into the dashboard.',
  },
  {
    question: 'What happens to my resume and my data?',
    answer:
      'Your resume is stored privately and used only to build your profile and score jobs. A tailored resume is not stored unless you choose to keep it. Gmail access is read-only and only the sender, subject and date of job emails are kept. You can download everything Rolesetu holds about you as one file.',
  },
  {
    question: 'Do I need an AI subscription or an API key?',
    answer:
      'No. Reading your resume, checking jobs and fresh jobs run without an AI model, and the resume assistant works without a key of your own. If you add your own Gemini key in Settings, AI features use it first.',
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
