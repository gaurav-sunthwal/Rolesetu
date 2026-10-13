"""Turns a job link into a job description.

safe_fetch      downloads a public web page, refusing anything unsafe
rendered_fetch  second attempt through Context.dev, for pages that block us
reader          tries safe_fetch, then rendered_fetch, and reads the job
job_page        reads the job out of the page's HTML
"""
