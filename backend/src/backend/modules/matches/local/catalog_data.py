"""The skills dictionary, one skill per line:

    Canonical name | alias, alias, ... | group

Aliases are other ways the same skill is written. A group ties together skills
that are close substitutes; having one earns partial credit for another.
A leading "!" marks a name that is also an ordinary English word ("Go",
"Express"), which is only recognised when written with that exact
capitalisation.
"""

CATALOG = """
# --- languages
JavaScript | JS, ECMAScript, ES6, ES6+, ES2015 | lang-js
TypeScript | TS | lang-js
Python | Python3, Python 3 |
Java | Java 8, Java 11, Java 17, Core Java | lang-jvm
Kotlin | | lang-jvm
Scala | | lang-jvm
!Go | Golang |
!Rust | |
C++ | CPP, C plus plus | lang-c
!C | | lang-c
C# | CSharp, C Sharp | lang-dotnet
!Swift | | lang-apple
Objective-C | ObjC, Objective C | lang-apple
PHP | |
!Ruby | |
!Dart | |
!R | R language, R programming |
MATLAB | |
Perl | |
Bash | Shell scripting, Shell script, Bash scripting, shell | scripting
PowerShell | | scripting
SQL | T-SQL, PL/SQL, PLSQL | sql
Solidity | |
!Elixir | |
Haskell | |
Lua | |
Groovy | | lang-jvm
VBA | |

# --- web frontend
HTML | HTML5 |
CSS | CSS3 |
!React | React.js, ReactJS, React JS | fe-framework
Next.js | NextJS, Next JS |
Vue | Vue.js, VueJS, Vue 3 | fe-framework
Nuxt | Nuxt.js, NuxtJS |
Angular | AngularJS, Angular 2+ | fe-framework
Svelte | SvelteKit | fe-framework
Remix | |
Astro | |
jQuery | |
Redux | Redux Toolkit, RTK | state
Zustand | | state
MobX | | state
Recoil | | state
React Query | TanStack Query | data-fetching
SWR | | data-fetching
Tailwind CSS | Tailwind, TailwindCSS | css-framework
Bootstrap | | css-framework
Material UI | MUI, Material-UI | ui-kit
Chakra UI | | ui-kit
shadcn/ui | shadcn | ui-kit
Ant Design | antd | ui-kit
Sass | SCSS | css-pre
Less | | css-pre
styled-components | Styled Components | css-in-js
Emotion | | css-in-js
Webpack | | bundler
Vite | | bundler
Rollup | | bundler
esbuild | | bundler
Babel | |
Storybook | |
Web Components | |
WebSockets | WebSocket, Socket.IO, Socket IO |
WebRTC | |
GraphQL | Apollo, Apollo Client, Apollo Server |
REST APIs | REST API, RESTful APIs, RESTful API, RESTful, REST, RESTful services |
gRPC | |
tRPC | |
Responsive design | responsive web design, responsive layouts, responsive UI, mobile-first |
Accessibility | a11y, WCAG, web accessibility |
SEO | search engine optimization |
PWA | Progressive Web Apps, Progressive Web App |
Three.js | ThreeJS |
D3.js | D3 |

# --- mobile
React Native | RN | mobile-cross
Expo | | mobile-cross
Flutter | | mobile-cross
Android | Android SDK, Android development |
iOS | iOS development |
SwiftUI | | apple-ui
UIKit | | apple-ui
Jetpack Compose | | android-ui
Xcode | |
Android Studio | |
Ionic | | mobile-cross
Firebase | Firebase Auth, Firestore, Firebase Authentication, FCM, Firebase Cloud Messaging | baas
Supabase | | baas
Push notifications | push notification |
Deep linking | deep links |
App Store | App Store Connect, TestFlight |
Google Play | Google Play Console, Play Store |
RevenueCat | |

# --- backend
Node.js | NodeJS, Node JS, Node | be-js
!Express | Express.js, ExpressJS | be-js
NestJS | Nest.js | be-js
Fastify | | be-js
Django | Django REST Framework, DRF | be-python
!Flask | | be-python
FastAPI | | be-python
!Spring | Spring Boot, SpringBoot, Spring Framework, Spring MVC | be-jvm
Hibernate | JPA | orm
Ruby on Rails | Rails, RoR | be-ruby
Laravel | | be-php
Symfony | | be-php
ASP.NET | .NET, .NET Core, dotnet, ASP.NET Core, .NET Framework | be-dotnet
Gin | | be-go
Phoenix | | be-elixir
Microservices | microservice architecture, micro-services |
Serverless | AWS Lambda, Lambda, Cloud Functions, Azure Functions |
OAuth | OAuth2, OAuth 2.0, OpenID Connect, OIDC |
JWT | JSON Web Tokens |
Prisma | | orm
Drizzle | Drizzle ORM | orm
Sequelize | | orm
TypeORM | | orm
SQLAlchemy | | orm
Celery | | job-queue
RabbitMQ | | message-queue
Kafka | Apache Kafka | message-queue
Redis | | cache
Memcached | | cache
Nginx | | web-server
Apache | Apache HTTP Server | web-server
Stripe | | payments
Razorpay | | payments
PayPal | | payments

# --- databases
PostgreSQL | Postgres, PostGIS, Postgresql | sql-db
MySQL | MariaDB | sql-db
SQL Server | MSSQL, Microsoft SQL Server | sql-db
Oracle | Oracle Database, Oracle DB | sql-db
SQLite | | sql-db
MongoDB | Mongo, Mongoose | nosql-doc
DynamoDB | | nosql-doc
Cassandra | | nosql-wide
Elasticsearch | Elastic Search, OpenSearch, ELK | search
Neo4j | | graph-db
Snowflake | | warehouse
BigQuery | | warehouse
Redshift | | warehouse
Databricks | | lakehouse
ClickHouse | | warehouse
Database design | data modeling, data modelling, schema design |

# --- cloud and devops
AWS | Amazon Web Services, EC2, S3, AWS S3, RDS, CloudFront, ECS, EKS, SQS, SNS | cloud
GCP | Google Cloud, Google Cloud Platform | cloud
Azure | Microsoft Azure | cloud
Vercel | | paas
Netlify | | paas
Heroku | | paas
Cloudflare | Cloudflare Workers, Cloudflare R2 |
Docker | Docker Compose, containerization, containers, containerisation | container
Kubernetes | K8s, Helm | orchestration
Terraform | | iac
Ansible | | iac
Pulumi | | iac
CloudFormation | | iac
CI/CD | CI CD, continuous integration, continuous delivery, continuous deployment, CICD | ci
GitHub Actions | | ci-tool
Jenkins | | ci-tool
GitLab CI | GitLab CI/CD | ci-tool
CircleCI | | ci-tool
Git | version control | vcs
GitHub | | vcs-host
GitLab | | vcs-host
Bitbucket | | vcs-host
Linux | Unix, Ubuntu |
Prometheus | | monitoring
Grafana | | monitoring
Datadog | | monitoring
Sentry | | monitoring
New Relic | | monitoring
Observability | monitoring and alerting, logging and monitoring |

# --- testing
Jest | | js-test
Vitest | | js-test
Mocha | | js-test
Cypress | | e2e-test
Playwright | | e2e-test
Selenium | | e2e-test
React Testing Library | Testing Library, RTL, React Native Testing Library | js-test
Pytest | | py-test
JUnit | | jvm-test
Unit testing | unit tests, automated testing, automated tests, test automation, TDD, test-driven development |
Postman | | api-tool

# --- data and ML
pandas | | py-data
NumPy | | py-data
scikit-learn | sklearn, scikit learn |
PyTorch | | dl-lib
TensorFlow | Keras | dl-lib
Machine learning | ML |
Deep learning | neural networks |
NLP | natural language processing |
Computer vision | OpenCV |
LLMs | LLM, large language models, generative AI, GenAI, OpenAI API, prompt engineering |
LangChain | LangGraph, LlamaIndex |
RAG | retrieval augmented generation, retrieval-augmented generation, vector databases, vector database, embeddings |
Hugging Face | Transformers |
!Spark | Apache Spark, PySpark |
Hadoop | |
Airflow | Apache Airflow | orchestrator
dbt | | transform
ETL | ELT, data pipelines, data pipeline |
Tableau | | bi
Power BI | PowerBI | bi
Looker | Looker Studio | bi
!Excel | Microsoft Excel, MS Excel, spreadsheets | spreadsheet
Google Sheets | | spreadsheet
Statistics | statistical analysis, statistical modeling |
A/B testing | AB testing, experimentation |
Data analysis | data analytics, analytics |
Data visualization | data visualisation, dashboards |
MLflow | | mlops
SageMaker | AWS SageMaker | mlops
Jupyter | Jupyter Notebook | notebook

# --- design and product
Figma | | design-tool
!Sketch | | design-tool
Adobe XD | | design-tool
Photoshop | Adobe Photoshop | adobe
Illustrator | Adobe Illustrator | adobe
Prototyping | prototypes, wireframing, wireframes |
User research | usability testing, user interviews, UX research |
Design systems | design system |
UI/UX | UX design, UI design, UX/UI, user experience design |
Jira | | tracker
Confluence | |
!Notion | |
Agile | Scrum, Kanban, Agile/Scrum, agile methodologies |
Product management | product roadmap, roadmapping |

# --- practices
System design | distributed systems, software architecture, scalable systems, system architecture |
Data structures | algorithms, DSA, data structures and algorithms |
OOP | object-oriented programming, object oriented programming, OOPS |
Design patterns | |
Performance optimization | performance tuning, performance optimisation, web performance |
Code review | code reviews |
API design | API development |
Security | application security, OWASP, cybersecurity |
Technical writing | technical documentation, docs writing |
Software development | software engineering, software engineering principles, software development principles, software development life cycle, SDLC, application development, software solutions, coding |
Debugging | troubleshooting code |
Project management | project planning, project coordination, PMP |
Stakeholder management | stakeholder communication |

# --- office tools
Microsoft Office | MS Office, Microsoft Office Suite, Office 365, Microsoft 365 | office
PowerPoint | MS PowerPoint, Microsoft PowerPoint | office
Microsoft Word | MS Word | office

# --- electrical and automation
Electrical design | electrical drawings, electrical systems design, electrical systems, designing electrical systems | elec-design
Power distribution | power distribution systems, electrical distribution, medium voltage, low voltage, high voltage | elec-power
Load calculations | load calculation, load flow, load flow analysis | elec-study
Short circuit analysis | short circuit studies, short circuit study, short circuit | elec-study
Arc flash studies | arc flash, arc flash study, arc flash analysis | elec-study
One-line diagrams | single line diagrams, single-line diagrams, one line diagrams, one-line diagram |
ETAP | | elec-tool
SKM PowerTools | SKM | elec-tool
!NEC | National Electrical Code |
AutoCAD | AutoCAD Electrical, AutoCAD MEP, Auto CAD | cad-2d
Revit | Revit MEP | bim
MEP coordination | MEP, MEP teams, mechanical electrical and plumbing |
PLC programming | PLC, PLCs, programmable logic controllers, programmable logic controller | automation
SCADA | | automation
DCS | distributed control system, distributed control systems | automation
Embedded systems | embedded C, embedded software, firmware, microcontrollers, microcontroller, RTOS | embedded
PCB design | PCB layout, Altium, KiCad |
Circuit design | circuit analysis |

# --- mechanical and manufacturing
SolidWorks | Solid Works | cad-3d
CATIA | | cad-3d
Creo | PTC Creo, Pro/E, Pro Engineer | cad-3d
Siemens NX | Unigraphics, NX CAD | cad-3d
Fusion 360 | | cad-3d
GD&T | geometric dimensioning and tolerancing |
Tolerance analysis | tolerance stack-up, tolerance stack up, stack-up analysis, tolerance stack-up analysis |
FEA | finite element analysis, ANSYS, Abaqus | simulation
CFD | computational fluid dynamics | simulation
DFM | design for manufacturing, design for manufacturability, DFMA, design for assembly |
Sheet metal design | sheet metal |
Casting design | castings, cast parts |
BOM | bill of materials, BOMs |
Mechanical design | product design, designing parts, part design |
HVAC | |
Lean manufacturing | Six Sigma, Lean Six Sigma, Kaizen |

# --- construction and civil
Construction management | construction projects, commercial construction, construction schedules |
Primavera P6 | Primavera | scheduling
Microsoft Project | MS Project | scheduling
RFIs | RFI, requests for information |
Submittals | submittal |
Change orders | change order |
Subcontractor management | subcontractors, subcontractor |
Site management | site meetings, site supervision, site execution |
OSHA | OSHA 30, OSHA 10 |
Quantity surveying | quantity takeoff, BOQ, bill of quantities |
Structural analysis | STAAD Pro, STAAD, ETABS |
Cost control | cost management, budget management, budget control |

# --- healthcare
Patient care | patient monitoring, patient assessment, bedside care |
Critical care | ICU, intensive care, critical care nursing |
Ventilator management | ventilators, ventilated patients, mechanical ventilation |
Medication administration | administering medications, administered medications, administer medications, medication management |
BLS | Basic Life Support | life-support
ACLS | Advanced Cardiac Life Support | life-support
!Epic | Epic EMR | emr
EMR | EHR, electronic medical records, electronic health records | emr
Infection control | |
Wound care | |
Phlebotomy | |

# --- accounting and finance
General ledger | general ledger accounting, ledger |
Month-end close | month end close, month-end closing, financial close, books closing |
Account reconciliation | account reconciliations, reconciliations, bank reconciliation, reconciliation |
Financial statements | financial reporting, financial statement preparation, balance sheet |
Accounts payable | | ap-ar
Accounts receivable | | ap-ar
GAAP | US GAAP, Ind AS | acct-standard
IFRS | | acct-standard
GST | GST filing, GST filings, GST returns, goods and services tax | tax
Taxation | tax filings, tax filing, income tax, TDS, direct tax, indirect tax, tax returns | tax
Auditing | statutory audit, statutory audits, internal audit, external audit |
Tally | Tally ERP, Tally Prime, TallyPrime | accounting-software
QuickBooks | | accounting-software
Zoho Books | | accounting-software
SAP | SAP FICO, SAP FI, SAP MM, SAP ERP, SAP S/4HANA | erp
Financial modeling | financial modelling, financial models |
Budgeting | budgeting and forecasting, FP&A |
Forecasting | forecasts, sales forecasting, demand forecasting |
Payroll | payroll processing |
Bookkeeping | |

# --- marketing
SEO | search engine optimization, search engine optimisation |
SEM | search engine marketing, PPC, pay per click |
Google Ads | Google AdWords, AdWords | paid-ads
Meta Ads | Facebook Ads, Instagram Ads | paid-ads
Paid campaigns | performance marketing, paid marketing, paid media, paid acquisition |
Content marketing | content strategy, content creation |
Social media marketing | social media, SMM |
Email marketing | Mailchimp, email campaigns |
Google Analytics | GA4, Google Analytics 4 | web-analytics
Digital marketing | online marketing |
Conversion rate optimization | CRO, landing pages, landing page optimization |
Brand management | branding, brand strategy |
Copywriting | copy writing |
Market research | competitor analysis, competitive analysis |
HubSpot | | crm
Salesforce | Salesforce CRM, SFDC | crm
CRM | CRM software, Zoho CRM, customer relationship management | crm

# --- sales
B2B sales | enterprise sales, inside sales, field sales, solution selling, B2B enterprise sales | sales
Lead generation | prospecting, cold calling, cold outreach, outbound sales |
Sales cycle | full sales cycle, closing deals, deal closing, contract closing |
Negotiation | negotiating, negotiations |
Account management | key account management, client relationships, relationship management |
Quota attainment | quota, sales targets, revenue targets |

# --- HR
Recruitment | recruiting, talent acquisition, end-to-end recruitment, sourcing candidates |
Employee onboarding | onboarding new hires, onboarding, employee induction, induction, joiner process | hr-onboarding
HRIS | Workday, SuccessFactors, BambooHR |
Employee relations | |
Performance management | performance appraisals, appraisals |
Labour law | labor law, employment law, statutory compliance, labor compliance |
HR Operations | HR administration, human resources operations, HR admin, people operations |
HR Policies | company policies, HR compliance |
Documentation | records management, employee records, document management |

# --- operations
Supply chain management | supply chain, SCM |
Procurement | purchasing |
Vendor management | vendor relations, supplier management, suppliers |
Inventory management | inventory control, stock management |
Logistics | warehousing, warehouse management |
"""

# Lines of work that show a skill without the profile naming it: someone whose
# role title is in the field on the left has done the skills on the right.
# The field keys are the ones in `fields.FIELDS`.
FIELD_SHOWS = {
    "software": ("Software development", "Debugging"),
    "electrical": ("Electrical design",),
    "mechanical": ("Mechanical design",),
    "construction": ("Construction management",),
    "healthcare": ("Patient care",),
    "marketing": ("Digital marketing",),
    "sales": ("B2B sales",),
    "hr": ("Recruitment", "Employee onboarding", "HR Operations"),
    "operations": ("Supply chain management",),
}


# Using the skill on the left is using the skill on the right: someone who
# built with Tailwind CSS has written CSS. One line per skill:
#     Skill -> implied, implied
IMPLIES = """
Tailwind CSS -> CSS
Sass -> CSS
Bootstrap -> CSS
styled-components -> CSS
Next.js -> React, JavaScript
Remix -> React, JavaScript
React Native -> React, JavaScript
Expo -> React Native, React, JavaScript
React -> JavaScript
Vue -> JavaScript
Nuxt -> Vue, JavaScript
Angular -> TypeScript, JavaScript
Svelte -> JavaScript
TypeScript -> JavaScript
Redux -> React
Zustand -> React
React Query -> React
Node.js -> JavaScript
Express -> Node.js, JavaScript
NestJS -> Node.js, TypeScript, JavaScript
Fastify -> Node.js, JavaScript
Jest -> Unit testing
Vitest -> Unit testing
Mocha -> Unit testing
Pytest -> Unit testing, Python
JUnit -> Unit testing, Java
React Testing Library -> Unit testing
Django -> Python
Flask -> Python
FastAPI -> Python, REST APIs
pandas -> Python
NumPy -> Python
scikit-learn -> Python, Machine learning
PyTorch -> Python, Deep learning, Machine learning
TensorFlow -> Deep learning, Machine learning
Spring -> Java
Hibernate -> Java
Ruby on Rails -> Ruby
Laravel -> PHP
Symfony -> PHP
ASP.NET -> C#
Flutter -> Dart
SwiftUI -> Swift, iOS
UIKit -> Swift, iOS
Jetpack Compose -> Kotlin, Android
PostgreSQL -> SQL
MySQL -> SQL
SQL Server -> SQL
SQLite -> SQL
Oracle -> SQL
Kubernetes -> Docker
GitHub Actions -> CI/CD
Jenkins -> CI/CD
GitLab CI -> CI/CD
CircleCI -> CI/CD
GitHub -> Git
GitLab -> Git
Bitbucket -> Git
LangChain -> LLMs
RAG -> LLMs
Prisma -> SQL
Drizzle -> SQL
SQLAlchemy -> SQL, Python
Sequelize -> SQL
dbt -> SQL
Epic -> EMR
Salesforce -> CRM
HubSpot -> CRM
Google Ads -> Paid campaigns
Meta Ads -> Paid campaigns
SEM -> Paid campaigns
"""
