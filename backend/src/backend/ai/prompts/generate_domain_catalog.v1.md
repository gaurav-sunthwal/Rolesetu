Write a skills dictionary for job matching in the `{field_label}` line of work.

Output:
- catalog_lines: 15-35 skills in this exact format, one per line:
  `Canonical name | alias, alias | group`
  Use short group slugs (e.g. hr-onboarding, crm, accounting-software).
  Include tools, methods, and competencies employers list in real job posts for this field.
  Do not repeat generic soft skills (communication, teamwork, problem-solving).
- core_skill_names: 12-18 canonical names from catalog_lines that best represent what a
  strong candidate in this field typically shows on a resume. These are used for onboarding
  fit checks, not as a job score.

The field key is `{field_key}`. Stay specific to this industry; do not list programming
languages unless they are commonly required in this field's job posts.
