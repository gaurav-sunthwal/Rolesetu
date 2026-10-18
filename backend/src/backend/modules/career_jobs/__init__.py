"""Jobs read straight from company careers sites, once a day, for every user.

Each company's site runs on some hiring platform (Workday, Greenhouse, ...) or
on its own search. A reader per platform turns that site into `Posting`s, so
adding a company is a line in the catalog, not new code.
"""
