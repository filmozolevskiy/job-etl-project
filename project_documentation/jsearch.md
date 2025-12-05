REQUEST EXAMPLE

requests.get(
    "https://api.openwebninja.com/jsearch/search",
    headers={
      "x-api-key": "YOUR_SECRET_TOKEN"
    },
    params={
      "query": "developer jobs in chicago",
      "page": "1",
      "num_pages": "1",
      "country": "ca",
      "language": "en",
      "date_posted": "today",
      "work_from_home": "false",
      "employment_types": "FULLTIME",
      "job_requirements": "no_experience",
      "radius": "1",
      "exclude_job_publishers": "BeeBe,Dice",
      "fields": "employer_name,job_publisher,job_title,job_country"
    }
)

RESPONSE EXAMPLE 
{
  "status": "OK",
  "request_id": "56d73fd4-9998-48ac-8f6e-8f88e8eea803",
  "parameters": {
    "query": "BI Developer",
    "page": 1,
    "num_pages": 1,
    "date_posted": "week",
    "country": "ca",
    "language": "en"
  },
  "data": [
    {
      "job_id": "rtUypcS3WeRmIQr0AAAAAA==",
      "job_title": "Power BI Developer (PowerShell & DevOps)",
      "employer_name": "Synechron",
      "employer_logo": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSA3hiHoRCZRCtQwKF7dtsux2Z2eYGJNivFxGSr&s=0",
      "employer_website": "https://www.synechron.com",
      "job_publisher": "LinkedIn",
      "job_employment_type": "Full-time",
      "job_employment_types": [
        "FULLTIME"
      ],
      "job_apply_link": "https://ca.linkedin.com/jobs/view/power-bi-developer-powershell-devops-at-synechron-4347694204?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
      "job_apply_is_direct": false,
      "apply_options": [
        {
          "publisher": "LinkedIn",
          "apply_link": "https://ca.linkedin.com/jobs/view/power-bi-developer-powershell-devops-at-synechron-4347694204?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
          "is_direct": false
        },
        {
          "publisher": "BeBee CA",
          "apply_link": "https://ca.bebee.com/job/5e07fcf8f44aaf65cfcde8a6dff4d260?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
          "is_direct": false
        },
        {
          "publisher": "The BIG Jobsite",
          "apply_link": "https://ca.thebigjobsite.com/details/604B8FE46EDF753DF6D3DC58ED7DFA00/power-bi-developer---devops--snowflake---python?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
          "is_direct": false
        }
      ],
      "job_description": "We are\n\nAt Synechron, we believe in the power of digital to transform businesses for the better. Our global consulting firm combines creativity and innovative technology to deliver industry-leading digital solutions. Synechron’s progressive technologies and optimization strategies span end-to-end Artificial Intelligence, Consulting, Digital, Cloud & DevOps, Data, and Software Engineering, servicing an array of noteworthy financial services and technology firms. Through research and development initiatives in our FinLabs we develop solutions for modernization, from Artificial Intelligence and Blockchain to Data Science models, Digital Underwriting, mobile-first applications and more. Over the last 20+ years, our company has been honored with multiple employer awards, recognizing our commitment to our talented teams. With top clients to boast about, Synechron has a global workforce of 14,500+, and has 58 offices in 21 countries within key global markets.\n\nOur challenge\n\nWe are seeking an experienced Power BI Developer skilled in building dynamic dashboards and reports, coupled with expertise in PowerShell and DevOps practices to automate deployment and streamline data workflows. The ideal candidate will design scalable data solutions, optimize reporting performance, and integrate systems effectively within a cloud-based environment.\n\nAdditional Information\n\nThe base salary for this position will vary based on geography and other factors. In accordance with law, the base salary for this role if filled within Mississauga, ON is CAD $130k – CAD $135k/year & benefits (see below).\n\nRequirements:\n• 8+ years in BI, data warehousing, and analytics\n• Strong SQL skills; experience with Snowflake\n• Proficient in Python and PowerShell scripting\n• Experience with CI/CD tools (e.g., Jenkins, Azure DevOps, Git)\n• Familiar with cloud data solutions and API integration\n• Knowledge of Cube development and performance tuning\n• Excellent problem-solving and communication skills\n• Relevant certifications (Snowflake, Power BI, PowerShell, DevOps) a plus\n• Experience with containers (Docker, Kubernetes) and IaC is beneficial\n\nResponsibilities:\n• Develop and optimize data warehouses (Snowflake) and ETL processes\n• Create complex SQL queries and data models\n• Automate deployment and operations with PowerShell\n• Build and maintain Power BI dashboards\n• Collaborate with teams to integrate systems and develop APIs\n• Design OLAP cubes, monitor data pipelines, and ensure system reliability\n• Support DevOps practices and version control\n\nPreferred:\n• Detail-oriented with quick turnaround capacity\n• Strong analytical and multitasking skills\n• Industry experience in financial services\n• Fast learner and adaptable in a dynamic environment\n• Ability to prioritize and manage multiple tasks efficiently\n\nWe offer:\n• A multinational organization with 58 offices in 21 countries and the possibility to work abroad.\n• 15 days (3 weeks) of paid annual leave plus an additional 10 days of personal leave (floating days and sick days).\n• A comprehensive insurance plan including medical, dental, vision, life insurance, and long-term disability.\n• Flexible hybrid policy.\n• RRSP with employer’s contribution up to 4%.\n• A higher education certification policy.\n• On-demand Udemy for Business for all Synechron employees with free access to more than 5000 curated courses.\n• Coaching opportunities with experienced colleagues from our Financial Innovation Labs (FinLabs) and Center of Excellences (CoE) groups.\n• Cutting edge projects at the world’s leading tier-one banks, financial institutions and insurance firms.\n• A truly diverse, fun-loving and global work culture.\n\nSYNECHRON’S DIVERSITY & INCLUSION STATEMENT\n\nDiversity & Inclusion are fundamental to our culture, and Synechron is proud to be an equal opportunity workplace and is an affirmative action employer. Our Diversity, Equity, and Inclusion (DEI) initiative ‘Same Difference’ is committed to fostering an inclusive culture – promoting equality, diversity and an environment that is respectful to all. We strongly believe that a diverse workforce helps build stronger, successful businesses as a global company. We encourage applicants from across diverse backgrounds, race, ethnicities, religion, age, marital status, gender, sexual orientations, or disabilities to apply. We empower our global workforce by offering flexible workplace arrangements, mentoring, internal mobility, learning and development programs, and more.\n\nAll employment decisions at Synechron are based on business needs, job requirements and individual qualifications, without regard to the applicant’s gender, gender identity, sexual orientation, race, ethnicity, disabled or veteran status, or any other characteristic protected by law.\n\nNous sommes\n\nChez Synechron, nous croyons en la puissance du numérique pour transformer les entreprises pour le mieux. Notre cabinet de conseil mondial combine créativité et technologie innovante pour fournir des solutions numériques de premier plan. Nos technologies avancées et stratégies d’optimisation couvrent l’Intelligence Artificielle, le Conseil, le Digital, le Cloud & DevOps, la Data et l’Ingénierie Logicielle, au service de nombreuses entreprises renommées dans les secteurs financier et technologique. Via nos initiatives de recherche et développement dans nos FinLabs, nous créons des solutions pour la modernisation, allant de l’Intelligence Artificielle et la Blockchain aux modèles de Data Science, l’Underwriting Digital, les applications mobiles-first, et plus encore. Au cours des 20 dernières années, notre société a reçu plusieurs récompenses en tant qu’employeur, témoignant de notre engagement envers nos équipes talentueuses. Avec des clients de premier plan, Synechron compte plus de 14 500 collaborateurs dans 58 bureaux répartis dans 21 pays clés à l’échelle mondiale.\n\nNotre défi\n\nNous recherchons un Développeur Power BI expérimenté, capable de créer des tableaux de bord et des rapports dynamiques, avec une expertise en PowerShell et en pratiques DevOps pour automatiser le déploiement et optimiser les flux de données. Le candidat idéal concevra des solutions de données évolutives, améliorera la performance des rapports et intégrera efficacement les systèmes dans un environnement cloud\n\nInformations complémentaires\n\nLe salaire de base pour ce poste variera selon la localisation et d’autres facteurs. Conformément à la législation, le salaire de base pour ce poste à Mississauga, ON, est entre 130 000 et 135 000 CAD par an, plus avantages (voir ci-dessous)\n\nExigences :\n• Plus de 8 ans d’expérience en BI, entreposage de données et analytique\n• Solides compétences en SQL, expérience avec Snowflake\n• Maîtrise de Python et PowerShell\n• Expérience avec des outils CI/CD (Jenkins, Azure DevOps, Git)\n• Connaissance des solutions cloud et de l’intégration API\n• Connaissance du développement de cubes OLAP et optimisation des performances\n• Excellentes compétences en résolution de problèmes et communication\n• Certifications pertinentes (Snowflake, Power BI, PowerShell, DevOps) appréciées\n• Expérience avec les conteneurs (Docker, Kubernetes) et l’IaC est un plus\n\nResponsabilités :\n• Développer et optimiser les entrepôts de données (Snowflake) et processus ETL\n• Créer des requêtes SQL complexes et des modèles de données\n• Automatiser les déploiements et opérations avec PowerShell\n• Concevoir et maintenir des tableaux de bord Power BI\n• Collaborer pour intégrer des systèmes et développer des API\n• Concevoir des cubes OLAP, surveiller les pipelines de données et assurer la fiabilité des systèmes\n• Soutenir les pratiques DevOps et la gestion de version\n\nPréféré mais pas obligatoire :\n• Attention aux détails, capacité à travailler rapidement avec précision\n• Solides compétences analytiques et capacité à gérer plusieurs tâches\n• Expérience dans le secteur des services financiers\n• Apprenant rapide, adaptable et flexible dans un environnement dynamique\n• Capacités à prioriser et gérer efficacement plusieurs projets\n\nNous offrons :\n• Une organisation multinationale avec 58 bureaux dans 21 pays, possibilité de travailler à l’étranger\n• 15 jours (3 semaines) de congés payés + 10 jours de congés personnels (jours flottants et maladie)\n• Assurance globale : médicale, dentaire, optique, vie, invalidité longue durée\n• Politique hybride flexible\n• REER avec contribution de l’employeur jusqu’à 4%\n• Politique de formation continue avec certifications de troisième cycle\n• Accès gratuit à plus de 5000 cours via Udemy pour tous nos employés\n• Opportunités de coaching avec des collègues expérimentés dans nos FinLabs et CoE\n• Projets innovants auprès des principales banques, institutions financières et compagnies d’assurance mondiales\n• Une culture de travail véritablement diversifiée, ludique et internationale\n\nDiversity & Inclusion chez Synechron\n\nLa diversité et l’inclusion sont fondamentales pour notre culture. Synechron est fier d’être un employeur offrant l’égalité des chances et un employeur qui agit positivement en faveur de l’égalité. Notre initiative DEI, ‘Same Difference’, vise à favoriser une culture inclusive, promouvoir l’égalité et respecter tous. Nous croyons qu’une main-d'œuvre diversifiée permet de bâtir des entreprises plus solides. Nous encourageons les candidatures de tous horizons, quelles que soient race, ethnie, religion, âge, statut marital, genre, orientation sexuelle ou handicap. Nous soutenons notre équipe mondiale avec des aménagements flexibles, du mentorat, des mobilités internes, des programmes de formation, et plus encore.\n\nToutes nos décisions d’embauche se basent sur les besoins de l’entreprise, les exigences du poste et la qualification individuelle, sans distinction de genre, d’identité de genre, d’orientation sexuelle, de race, d’ethnie, de statut de handicap ou de vétéran, ou toute autre caractéristique protégée par la loi.",
      "job_is_remote": false,
      "job_posted_at": "4 days ago",
      "job_posted_at_timestamp": 1764201600,
      "job_posted_at_datetime_utc": "2025-11-27T00:00:00.000Z",
      "job_location": "Canada",
      "job_city": null,
      "job_state": null,
      "job_country": "CA",
      "job_latitude": 56.130365999999995,
      "job_longitude": -106.34677099999999,
      "job_benefits": null,
      "job_google_link": "https://www.google.com/search?q=jobs&gl=ca&hl=en&udm=8#vhid=vt%3D20/docid%3DrtUypcS3WeRmIQr0AAAAAA%3D%3D&vssid=jobs-detail-viewer",
      "job_salary": null,
      "job_min_salary": null,
      "job_max_salary": null,
      "job_salary_period": null,
      "job_highlights": {},
      "job_onet_soc": "15113200",
      "job_onet_job_zone": "4"
    }
  ]
}