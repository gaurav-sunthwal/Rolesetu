"""Labelled people and jobs for the matching eval (see `evals/matching.py`).

Eight profiles and eight job descriptions from different fields. Every profile
is checked against every job, and the expected outcome comes from the two
fields: the same field should score high, an unrelated field should score low,
and close fields (frontend and backend, say) are left open. The first job is
the one a user reported: a data architect was shown 100% for it.
"""

from typing import Any, Literal

Expect = Literal["high", "low", "any"]

FIELD_OF_PROFILE: dict[str, str] = {
    "data_architect": "data",
    "frontend_dev": "software",
    "backend_dev": "software",
    "electrical_engineer": "electrical",
    "nurse": "nursing",
    "accountant": "accounting",
    "marketer": "marketing",
    "mechanical_engineer": "mechanical",
}

FIELD_OF_JOB: dict[str, str] = {
    "electrical_design_manager": "electrical",
    "data_engineer": "data",
    "frontend_engineer": "software",
    "backend_engineer": "software",
    "icu_nurse": "nursing",
    "staff_accountant": "accounting",
    "marketing_manager": "marketing",
    "mechanical_design_engineer": "mechanical",
    "construction_project_manager": "construction",
    "sales_executive": "sales",
}

# Fields close enough that either a high or a low score can be right.
CLOSE_FIELDS = {
    frozenset({"software", "data"}),
    frozenset({"electrical", "mechanical"}),
    frozenset({"data", "marketing"}),
    frozenset({"construction", "electrical"}),
    frozenset({"construction", "mechanical"}),
    frozenset({"sales", "marketing"}),
}

# Profiles whose own job is a different kind of software job than the one listed.
SOFTWARE_PAIRS_OPEN = {("frontend_dev", "backend_engineer"), ("backend_dev", "frontend_engineer")}


def expected(profile: str, job: str) -> Expect:
    mine, theirs = FIELD_OF_PROFILE[profile], FIELD_OF_JOB[job]
    if (profile, job) in SOFTWARE_PAIRS_OPEN:
        return "any"
    if mine == theirs:
        return "high"
    if frozenset({mine, theirs}) in CLOSE_FIELDS:
        return "any"
    return "low"


def _profile(
    headline: str,
    skills: list[str],
    experience: list[tuple[str, str, str, str | None, str]],
    education: list[tuple[str, str, str]],
    projects: list[tuple[str, list[str], str]] | None = None,
) -> dict[str, Any]:
    return {
        "full_name": "Test Person",
        "headline": headline,
        "location": None,
        "phone": None,
        "links": {},
        "skills": [{"id": f"s{i}", "name": name} for i, name in enumerate(skills)],
        "experience": [
            {
                "id": f"e{i}",
                "title": title,
                "company": company,
                "start": start,
                "end": end,
                "description": description,
            }
            for i, (title, company, start, end, description) in enumerate(experience)
        ],
        "projects": [
            {"id": f"p{i}", "name": name, "tech": tech, "description": description}
            for i, (name, tech, description) in enumerate(projects or [])
        ],
        "education": [
            {"id": f"d{i}", "school": school, "degree": degree, "field": field}
            for i, (school, degree, field) in enumerate(education)
        ],
        "version": 1,
        "completeness": 90,
        "updated_at": None,
    }


PROFILES: dict[str, dict[str, Any]] = {
    "data_architect": _profile(
        "Senior Enterprise Data Architect, Data & AI",
        ["Data analysis", "SQL", "Python", "Snowflake", "Databricks", "Power BI", "Azure"],
        [
            (
                "Senior Technical Manager – Data & AI Leadership",
                "HCL Tech",
                "2019-01",
                None,
                "Led data analysis and data platform delivery for enterprise clients.\n"
                "Designed lakehouse architecture on Azure with Databricks and Snowflake.\n"
                "Built data models and governance for 40+ source systems using SQL and Python.\n"
                "Delivered machine learning use cases with Spark and MLflow.",
            ),
            (
                "Data Architect",
                "Infosys",
                "2014-01",
                "2018-12",
                "Designed data warehouses and ETL pipelines with Informatica and SQL Server.\n"
                "Built Power BI dashboards for finance and supply chain reporting.",
            ),
        ],
        [("Pune University", "B.E.", "Computer Engineering")],
    ),
    "frontend_dev": _profile(
        "Frontend developer",
        ["Git", "Figma"],
        [
            (
                "Frontend Developer",
                "Phenko",
                "2022-06",
                None,
                "Built the seller dashboard in React and TypeScript with Next.js.\n"
                "Consumed REST APIs and wrote responsive layouts with Tailwind CSS.\n"
                "Added Jest and Vitest unit tests for the checkout flow.",
            )
        ],
        [("VIT", "B.Tech", "Information Technology")],
        [("Video rooms", ["WebRTC", "Node.js"], "Peer to peer video with a signalling server.")],
    ),
    "backend_dev": _profile(
        "Backend engineer, Python",
        ["Python", "PostgreSQL", "Docker"],
        [
            (
                "Backend Engineer",
                "Razorpay",
                "2020-03",
                None,
                "Built payment microservices in Python with FastAPI and Django.\n"
                "Owned PostgreSQL schemas and Redis caching for 10k requests per second.\n"
                "Deployed services on AWS with Docker and Kubernetes; wrote Terraform.",
            )
        ],
        [("NIT Trichy", "B.Tech", "Computer Science")],
    ),
    "electrical_engineer": _profile(
        "Electrical design engineer, PE",
        ["AutoCAD", "Revit", "ETAP", "Power distribution", "NEC"],
        [
            (
                "Senior Electrical Engineer",
                "Jacobs",
                "2017-02",
                None,
                "Designed medium voltage power distribution for hyperscale data centers.\n"
                "Ran load calculations, short circuit and arc flash studies in ETAP.\n"
                "Produced electrical drawings in AutoCAD and Revit to NEC requirements.\n"
                "Coordinated with mechanical and plumbing (MEP) teams and site construction.",
            )
        ],
        [("Texas A&M", "B.S.", "Electrical Engineering")],
    ),
    "nurse": _profile(
        "Registered Nurse, ICU",
        ["Patient care", "BLS", "ACLS", "Epic"],
        [
            (
                "ICU Registered Nurse",
                "Apollo Hospitals",
                "2018-04",
                None,
                "Provided critical care to ventilated patients in a 24-bed ICU.\n"
                "Administered medications and titrated drips; charted in Epic.\n"
                "Responded to codes with ACLS and trained new nurses.",
            )
        ],
        [("Manipal College of Nursing", "B.Sc.", "Nursing")],
    ),
    "accountant": _profile(
        "Chartered accountant",
        ["Excel", "GAAP", "QuickBooks", "Tally"],
        [
            (
                "Senior Accountant",
                "Deloitte",
                "2019-07",
                None,
                "Prepared monthly financial statements and account reconciliations under GAAP.\n"
                "Managed accounts payable, accounts receivable and the general ledger.\n"
                "Supported statutory audits and GST and tax filings using Tally and Excel.",
            )
        ],
        [("ICAI", "CA", "Accounting")],
    ),
    "marketer": _profile(
        "Digital marketing manager",
        ["SEO", "Google Ads", "Google Analytics", "Content marketing"],
        [
            (
                "Digital Marketing Manager",
                "Nykaa",
                "2020-01",
                None,
                "Ran SEO and content marketing that doubled organic traffic.\n"
                "Managed a Google Ads and Meta Ads budget of 2 crore a month.\n"
                "Built reports in Google Analytics (GA4) and ran A/B tests on landing pages.",
            )
        ],
        [("Symbiosis", "MBA", "Marketing")],
    ),
    "mechanical_engineer": _profile(
        "Mechanical design engineer",
        ["SolidWorks", "GD&T", "ANSYS"],
        [
            (
                "Mechanical Design Engineer",
                "Tata Motors",
                "2019-01",
                None,
                "Designed sheet metal and cast parts in SolidWorks with GD&T.\n"
                "Ran FEA in ANSYS to validate brackets under load.\n"
                "Released drawings and BOMs and worked with suppliers on DFM.",
            )
        ],
        [("COEP", "B.Tech", "Mechanical Engineering")],
    ),
}

JOBS: dict[str, tuple[str, str]] = {
    "electrical_design_manager": (
        "Electrical Design Manager",
        """Electrical Design Manager
CloudHQ, LLC · Ashburn, VA · On-site · Full-time
About the job
CloudHQ is looking for an Electrical Design Manager to lead the electrical design of our
hyperscale data center campuses.
Responsibilities
- Lead the electrical design of medium voltage and low voltage power distribution systems.
- Review one-line diagrams, load calculations, short circuit and arc flash studies.
- Coordinate electrical design with mechanical, plumbing and fire protection (MEP) teams.
- Use data analysis to track design progress and equipment lead times.
- Review drawings and specifications for compliance with the NEC and local codes.
Qualifications
- Bachelor's degree in Electrical Engineering.
- 5+ years of experience designing electrical systems for data centers or critical facilities.
- Professional Engineer (PE) license required.
- Experience with AutoCAD and Revit.
""",
    ),
    "data_engineer": (
        "Senior Data Engineer",
        """Senior Data Engineer
We are hiring a Senior Data Engineer to build our lakehouse.
Requirements
- 6+ years of experience in data engineering.
- Strong SQL and Python.
- Experience with Snowflake or Databricks, and Apache Spark.
- Data modeling and data governance.
- Experience with Azure or AWS.
Nice to have
- Airflow, dbt and Power BI.
""",
    ),
    "frontend_engineer": (
        "Frontend Engineer",
        """Frontend Engineer at Northwind
We're looking for a frontend engineer with 2+ years of experience to build our dashboard.
Requirements: strong React and TypeScript, experience with REST APIs, solid CSS and
responsive design, writing unit tests with Jest or Vitest, and Git.
Nice to have: Next.js, GraphQL and familiarity with Figma.
""",
    ),
    "backend_engineer": (
        "Senior Backend Engineer",
        """Senior Backend Engineer
Responsibilities
- Design and build microservices in Python (FastAPI or Django)
- Own PostgreSQL schemas and Redis caching
Requirements
- 4+ years of backend experience
- Experience with a cloud provider such as AWS, GCP or Azure
- Docker and Kubernetes
Preferred qualifications
- Kafka and Terraform
""",
    ),
    "icu_nurse": (
        "ICU Staff Nurse",
        """ICU Staff Nurse
Fortis Hospital is hiring registered nurses for its intensive care unit.
Requirements
- B.Sc. Nursing and an active Registered Nurse (RN) license.
- 3+ years of ICU or critical care experience.
- BLS and ACLS certification.
- Ventilator management, medication administration and patient monitoring.
- Experience charting in Epic or a similar EMR.
""",
    ),
    "staff_accountant": (
        "Staff Accountant",
        """Staff Accountant
We are looking for a Staff Accountant to join our finance team.
Requirements
- Bachelor's degree in Accounting or Finance; CA or CPA preferred.
- 3+ years of experience in general ledger accounting and month-end close.
- Account reconciliations and financial statements under GAAP.
- Accounts payable and receivable, GST and tax filings.
- Advanced Excel; experience with Tally or QuickBooks.
""",
    ),
    "marketing_manager": (
        "Digital Marketing Manager",
        """Digital Marketing Manager
Join our growth team to lead performance and organic marketing.
Requirements
- 4+ years of digital marketing experience.
- Hands-on SEO and content marketing.
- Paid campaigns on Google Ads and Meta Ads.
- Reporting with Google Analytics (GA4).
- A/B testing landing pages and email marketing.
""",
    ),
    "mechanical_design_engineer": (
        "Mechanical Design Engineer",
        """Mechanical Design Engineer
We design electric two-wheelers and are hiring a mechanical design engineer.
Requirements
- B.Tech or B.E. in Mechanical Engineering.
- 3+ years designing parts in SolidWorks or CATIA.
- GD&T and tolerance stack-up analysis.
- FEA with ANSYS.
- Design for manufacturing (DFM) for sheet metal and castings.
""",
    ),
    # Jobs from fields no profile here is in, that still name common tools
    # (Excel, SQL, Power BI, data analysis). Nobody should look like a fit.
    "construction_project_manager": (
        "Construction Project Manager",
        """Construction Project Manager
We build commercial buildings and are hiring a Construction Project Manager.
Responsibilities
- Manage construction schedules, budgets and subcontractors from groundbreaking to handover.
- Run site meetings, RFIs, submittals and change orders.
- Use data analysis and Power BI to report cost and schedule progress.
- Read AutoCAD drawings and coordinate with architects and MEP engineers.
Requirements
- 7+ years managing commercial construction projects.
- Bachelor's degree in Construction Management or Civil Engineering.
- OSHA 30 certification.
- Advanced Excel and Primavera P6 scheduling.
""",
    ),
    "sales_executive": (
        "Enterprise Sales Executive",
        """Enterprise Sales Executive
Sell our SaaS platform to large enterprises in India.
Requirements
- 5+ years of B2B enterprise sales with a record of meeting quota.
- Prospecting, cold calling and running the full sales cycle to close.
- Managing your pipeline in Salesforce CRM.
- Building forecasts in Excel and using SQL reports from our data team.
- Negotiation and contract closing with CXOs.
""",
    ),
}
