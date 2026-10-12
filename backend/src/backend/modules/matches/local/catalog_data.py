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
Technical writing | documentation |
"""


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
"""
