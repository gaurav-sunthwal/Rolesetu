"""Local resume parsing: PDF in, structured data out, no model call.

    pdf_lines   reads the PDF into ordered lines with font size, bold and links
    sections    splits those lines into Experience / Education / Skills / ...
    contact, skills, experience, projects, education
                each turn one section's lines into fields
    parser      runs the pipeline

Everything after `pdf_lines` is plain functions over `Line` objects, which is
what makes the rules testable without a PDF.
"""
