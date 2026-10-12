"""Job scoring with no model call.

    catalog   the skills dictionary: names, aliases and groups of related skills
    jd        reads a job description into required / nice-to-have skills
    judge     decides strong / partial / missing for each skill from the profile
    engine    runs the three and returns a result ready to score

Every step is a lookup or a regular expression, so a check takes milliseconds
and gives the same answer every time.
"""
