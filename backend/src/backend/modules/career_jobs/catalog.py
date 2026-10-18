"""The companies read every morning, each checked by hand against its site.

Companies users add themselves are stored in the database; these are the
starting set. A company whose site cannot be read without a paid browser
(TCS, Infosys, Cognizant, SAP, Deloitte India),
or whose site lists no jobs in India (PwC, FIS, Broadcom), is left out until it can.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Company:
    slug: str
    name: str
    kind: str
    config: dict[str, str] = field(default_factory=dict)


def _workday(slug: str, name: str, host: str, site: str, families: str = "") -> Company:
    config = {"host": host, "tenant": host.split(".")[0], "site": site}
    return Company(slug, name, "workday", config | ({"families": families} if families else {}))


# Accenture lists ~35,000 jobs in India; reading every one each morning takes
# about 20 minutes. These families are the roles our users apply for.
_ACCENTURE_TECH = (
    "Software Engineering, AI & Data, Security, Information Technology Operations, "
    "Business & Technology Integration"
)


def _board(kind: str, slug: str, name: str, token: str) -> Company:
    key = "company" if kind == "smartrecruiters" else "token"
    return Company(slug, name, kind, {key: token})


COMPANIES: tuple[Company, ...] = (
    # IT services and consulting
    _workday(
        "accenture",
        "Accenture",
        "accenture.wd103.myworkdayjobs.com",
        "AccentureCareers",
        _ACCENTURE_TECH,
    ),
    Company("capgemini", "Capgemini", "capgemini"),
    Company("wipro", "Wipro", "successfactors", {"host": "careers.wipro.com"}),
    Company("ibm", "IBM", "ibm"),
    # Big tech
    Company("google", "Google", "google"),
    Company(
        "microsoft",
        "Microsoft",
        "eightfold",
        {"host": "apply.careers.microsoft.com", "domain": "microsoft.com"},
    ),
    Company("amazon", "Amazon", "amazon"),
    Company(
        "oracle",
        "Oracle",
        "oracle",
        {
            "host": "eeho.fa.us2.oraclecloud.com",
            "site": "CX_45001",
            "job_url": "https://careers.oracle.com/en/sites/jobsearch/job/{id}",
        },
    ),
    _workday("adobe", "Adobe", "adobe.wd5.myworkdayjobs.com", "external_experienced"),
    _workday(
        "salesforce", "Salesforce", "salesforce.wd12.myworkdayjobs.com", "External_Career_Site"
    ),
    _workday("nvidia", "NVIDIA", "nvidia.wd5.myworkdayjobs.com", "NVIDIAExternalCareerSite"),
    _workday("intel", "Intel", "intel.wd1.myworkdayjobs.com", "External"),
    _workday("hp", "HP", "hp.wd5.myworkdayjobs.com", "ExternalCareerSite"),
    _workday("autodesk", "Autodesk", "autodesk.wd1.myworkdayjobs.com", "Ext"),
    _workday("workday", "Workday", "workday.wd5.myworkdayjobs.com", "Workday"),
    _workday("redhat", "Red Hat", "redhat.wd5.myworkdayjobs.com", "jobs"),
    _workday(
        "crowdstrike", "CrowdStrike", "crowdstrike.wd5.myworkdayjobs.com", "crowdstrikecareers"
    ),
    Company("atlassian", "Atlassian", "atlassian"),
    _board("smartrecruiters", "servicenow", "ServiceNow", "ServiceNow"),
    # Chips and hardware
    _workday("micron", "Micron", "micron.wd1.myworkdayjobs.com", "External"),
    _workday("nxp", "NXP", "nxp.wd3.myworkdayjobs.com", "careers"),
    _workday("analog-devices", "Analog Devices", "analogdevices.wd1.myworkdayjobs.com", "External"),
    _workday("philips", "Philips", "philips.wd3.myworkdayjobs.com", "jobs-and-careers"),
    _board("smartrecruiters", "bosch", "Bosch", "BoschGroup"),
    # Banks, payments and finance
    _workday("mastercard", "Mastercard", "mastercard.wd1.myworkdayjobs.com", "CorporateCareers"),
    _workday("paypal", "PayPal", "paypal.wd1.myworkdayjobs.com", "jobs"),
    _workday("morgan-stanley", "Morgan Stanley", "ms.wd5.myworkdayjobs.com", "External"),
    _workday(
        "thomson-reuters",
        "Thomson Reuters",
        "thomsonreuters.wd5.myworkdayjobs.com",
        "External_Career_Site",
    ),
    _board("greenhouse", "stripe", "Stripe", "stripe"),
    _board("greenhouse", "coinbase", "Coinbase", "coinbase"),
    # Retail and media
    _workday("target", "Target", "target.wd5.myworkdayjobs.com", "targetcareers"),
    _workday("warner-bros", "Warner Bros. Discovery", "warnerbros.wd5.myworkdayjobs.com", "global"),
    _workday("baker-hughes", "Baker Hughes", "bakerhughes.wd5.myworkdayjobs.com", "BakerHughes"),
    # Software and cloud
    _board("greenhouse", "databricks", "Databricks", "databricks"),
    _board("greenhouse", "mongodb", "MongoDB", "mongodb"),
    _board("greenhouse", "okta", "Okta", "okta"),
    _board("greenhouse", "gitlab", "GitLab", "gitlab"),
    _board("greenhouse", "rubrik", "Rubrik", "rubrik"),
    _board("greenhouse", "elastic", "Elastic", "elastic"),
    _board("greenhouse", "twilio", "Twilio", "twilio"),
    _board("greenhouse", "druva", "Druva", "druva"),
    _board("greenhouse", "airbnb", "Airbnb", "airbnb"),
    _board("lever", "palantir", "Palantir", "palantir"),
    _board("lever", "spotify", "Spotify", "spotify"),
    _board("ashby", "openai", "OpenAI", "openai"),
    _board("ashby", "notion", "Notion", "notion"),
    _board("smartrecruiters", "freshworks", "Freshworks", "Freshworks"),
    # Indian startups
    _board("greenhouse", "razorpay", "Razorpay", "razorpaysoftwareprivatelimited"),
    _board("greenhouse", "groww", "Groww", "groww"),
    _board("greenhouse", "inmobi", "InMobi", "inmobi"),
    _board("lever", "cred", "CRED", "cred"),
    _board("lever", "meesho", "Meesho", "meesho"),
    _board("lever", "paytm", "Paytm", "paytm"),
    _board("lever", "zeta", "Zeta", "zeta"),
    _board("ashby", "sarvam", "Sarvam AI", "sarvam"),
    _board("smartrecruiters", "swiggy", "Swiggy", "Swiggy"),
)
